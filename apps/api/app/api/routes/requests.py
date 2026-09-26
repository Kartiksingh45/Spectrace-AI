import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
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
from app.schemas.agent import (
    ChangeRequestCreate,
    ChangeRequestOut,
    ChangeRequestSummaryOut,
    ClarificationAnswer,
    RunOut,
    StepOut,
)
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


@router.get("/projects/{project_id}/requests", response_model=list[ChangeRequestSummaryOut])
def list_change_requests(
    project: Project = Depends(require_project_member), db: Session = Depends(get_db)
) -> list[ChangeRequestSummaryOut]:
    change_requests = (
        db.query(ChangeRequest)
        .filter(ChangeRequest.project_id == project.id)
        .order_by(ChangeRequest.created_at.desc())
        .all()
    )

    summaries = []
    for cr in change_requests:
        latest_run = (
            db.query(AgentRun)
            .filter(AgentRun.change_request_id == cr.id)
            .order_by(AgentRun.started_at.desc())
            .first()
        )
        plan = (
            db.query(GeneratedPlan)
            .filter(GeneratedPlan.change_request_id == cr.id)
            .order_by(GeneratedPlan.version.desc())
            .first()
        )
        summaries.append(
            ChangeRequestSummaryOut(
                id=cr.id,
                request_text=cr.request_text,
                request_type=cr.request_type,
                status=cr.status,
                created_at=cr.created_at,
                latest_run_id=latest_run.id if latest_run else None,
                plan_summary=plan.content.get("summary") if plan else None,
                confidence=plan.content.get("confidence") if plan else None,
            )
        )
    return summaries


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

    duration_ms = None
    if run.ended_at is not None:
        duration_ms = int((run.ended_at - run.started_at).total_seconds() * 1000)

    return RunOut(
        id=run.id,
        change_request_id=run.change_request_id,
        status=run.status.value,
        steps=[StepOut.model_validate(s) for s in steps],
        pending_question=pending_question,
        generated_plan=plan.content if plan else None,
        plan_id=plan.id if plan else None,
        started_at=run.started_at,
        ended_at=run.ended_at,
        duration_ms=duration_ms,
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

    if change_request.status not in (ChangeRequestStatus.pending, ChangeRequestStatus.failed):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This request has already been analysed")

    run = start_run(db, change_request, checkpointer, **agent_overrides)
    return _run_to_out(db, run)


_SSE_POLL_INTERVAL_SECONDS = 0.4
_SSE_MAX_SECONDS = 300  # safety cap so an abandoned connection can't hold a DB connection forever


@router.get("/requests/{request_id}/events")
async def stream_run_events(
    request_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> StreamingResponse:
    """Live progress via Server-Sent Events for this change request's most recent run: emits each
    agent step as it's actually persisted (see `_persist_partial_steps` in agent_runner.py) while
    a run is in flight, then a final `done` event once it pauses (clarification/approval) or
    finishes (completed/failed). Open this alongside (not instead of) the `analyse` /
    `clarification` / `decision` call that's actually driving the run - this endpoint only reads,
    it never starts or resumes anything itself. Anchored on the change request (known immediately
    after it's created) rather than the run id, since the run itself is only created once
    `analyse` begins - which, being a single blocking call for the whole run's duration, resolves
    too late for a frontend to have subscribed here first.
    """
    change_request = _get_change_request_for_member(db, request_id, user)

    async def event_source():
        sent = 0
        elapsed = 0.0
        while elapsed < _SSE_MAX_SECONDS:
            db.expire_all()
            run = (
                db.query(AgentRun)
                .filter(AgentRun.change_request_id == change_request.id)
                .order_by(AgentRun.started_at.desc())
                .first()
            )
            if run is not None:
                steps = (
                    db.query(AgentStep)
                    .filter(AgentStep.run_id == run.id)
                    .order_by(AgentStep.step_index.asc())
                    .all()
                )
                for step in steps[sent:]:
                    payload = {
                        "step_index": step.step_index,
                        "tool_name": step.tool_name,
                        "input_summary": step.input_summary,
                        "output_summary": step.output_summary,
                        "status": step.status.value,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                sent = len(steps)

                if run.status != AgentRunStatus.running:
                    yield f"event: done\ndata: {json.dumps({'status': run.status.value})}\n\n"
                    return

            await asyncio.sleep(_SSE_POLL_INTERVAL_SECONDS)
            elapsed += _SSE_POLL_INTERVAL_SECONDS

        yield f"event: done\ndata: {json.dumps({'status': 'timeout'})}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


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
