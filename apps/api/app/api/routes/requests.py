import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agent.checkpointer import get_checkpointer
from app.api.deps import get_agent_overrides, get_current_user, get_membership, require_project_member
from app.db.session import get_db
from app.models.agent_run import AgentRun
from app.models.agent_step import AgentStep
from app.models.change_request import ChangeRequest
from app.models.enums import AgentRunStatus, ChangeRequestStatus
from app.models.generated_plan import GeneratedPlan
from app.models.project import Project
from app.models.user import User
from app.schemas.agent import ChangeRequestCreate, ChangeRequestOut, ClarificationAnswer, RunOut, StepOut
from app.services.agent_runner import resume_clarification, start_run

router = APIRouter(tags=["requests"])


@router.post(
    "/projects/{project_id}/requests", response_model=ChangeRequestOut, status_code=status.HTTP_201_CREATED
)
def create_change_request(
    payload: ChangeRequestCreate,
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChangeRequest:
    change_request = ChangeRequest(project_id=project.id, created_by=user.id, request_text=payload.request_text)
    db.add(change_request)
    db.commit()
    db.refresh(change_request)
    return change_request


def _get_change_request_for_member(db: Session, request_id: uuid.UUID, user: User) -> ChangeRequest:
    change_request = db.get(ChangeRequest, request_id)
    if not change_request or not get_membership(db, change_request.project_id, user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Change request not found")
    return change_request


def _get_run_for_member(db: Session, run_id: uuid.UUID, user: User) -> tuple[AgentRun, ChangeRequest]:
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    change_request = db.get(ChangeRequest, run.change_request_id)
    if not change_request or not get_membership(db, change_request.project_id, user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run, change_request


def _run_to_out(db: Session, run: AgentRun) -> RunOut:
    steps = (
        db.query(AgentStep)
        .filter(AgentStep.run_id == run.id)
        .order_by(AgentStep.step_index.asc())
        .all()
    )
    pending_question = None
    if run.status == AgentRunStatus.awaiting_clarification and steps:
        last = steps[-1]
        if last.tool_name == "request_clarification" and last.output_summary == "(awaiting answer)":
            pending_question = last.input_summary

    plan = (
        db.query(GeneratedPlan)
        .filter(GeneratedPlan.change_request_id == run.change_request_id)
        .order_by(GeneratedPlan.version.desc())
        .first()
    )

    return RunOut(
        id=run.id,
        change_request_id=run.change_request_id,
        status=run.status.value,
        steps=[StepOut.model_validate(s) for s in steps],
        pending_question=pending_question,
        generated_plan=plan.content if plan else None,
        plan_id=plan.id if plan else None,
    )


@router.post("/requests/{request_id}/analyse", response_model=RunOut)
def analyse_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    checkpointer=Depends(get_checkpointer),
    agent_overrides: dict = Depends(get_agent_overrides),
) -> RunOut:
    change_request = _get_change_request_for_member(db, request_id, user)

    existing = (
        db.query(AgentRun)
        .filter(AgentRun.change_request_id == change_request.id)
        .order_by(AgentRun.started_at.desc())
        .first()
    )
    if existing and existing.status in (AgentRunStatus.running, AgentRunStatus.awaiting_clarification, AgentRunStatus.awaiting_approval):
        return _run_to_out(db, existing)

    if change_request.status not in (ChangeRequestStatus.pending,):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This request has already been analysed")

    run = start_run(db, change_request, checkpointer, **agent_overrides)
    return _run_to_out(db, run)


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> RunOut:
    run, _ = _get_run_for_member(db, run_id, user)
    return _run_to_out(db, run)


@router.post("/runs/{run_id}/clarification", response_model=RunOut)
def answer_clarification(
    run_id: uuid.UUID,
    payload: ClarificationAnswer,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    checkpointer=Depends(get_checkpointer),
    agent_overrides: dict = Depends(get_agent_overrides),
) -> RunOut:
    run, change_request = _get_run_for_member(db, run_id, user)
    if run.status != AgentRunStatus.awaiting_clarification:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This run is not awaiting clarification")

    run = resume_clarification(db, run, change_request, payload.answer, checkpointer, **agent_overrides)
    return _run_to_out(db, run)
