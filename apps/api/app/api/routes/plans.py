import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agent.checkpointer import get_checkpointer
from app.agent.schemas import GeneratedPlan as GeneratedPlanSchema
from app.api.deps import get_agent_overrides, get_membership, require_reviewer
from app.api.routes.requests import _run_to_out
from app.db.session import get_db, get_session_factory
from app.models.agent_run import AgentRun
from app.models.approval import Approval
from app.models.change_request import ChangeRequest
from app.models.enums import AgentRunStatus
from app.models.generated_plan import GeneratedPlan
from app.models.user import User
from app.schemas.agent import DecisionRequest, RunOut
from app.services.agent_runner import execute_resume_decision, prepare_resume, run_in_background

router = APIRouter(tags=["plans"])


@router.post("/plans/{plan_id}/decision", response_model=RunOut)
def submit_decision(
    plan_id: uuid.UUID,
    payload: DecisionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    checkpointer=Depends(get_checkpointer),
    agent_overrides: dict = Depends(get_agent_overrides),
    session_factory=Depends(get_session_factory),
) -> RunOut:
    plan = db.get(GeneratedPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    change_request = db.get(ChangeRequest, plan.change_request_id)
    if not change_request or not get_membership(db, change_request.project_id, user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    run = db.get(AgentRun, plan.run_id)
    if not run or run.status != AgentRunStatus.awaiting_approval:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This plan is not awaiting a decision")

    if payload.decision == "edit_approved" and payload.final_content is not None:
        try:
            validated = GeneratedPlanSchema.model_validate(payload.final_content)
        except ValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid edited plan: {exc}") from exc
        # The edit becomes the plan of record from here on (run detail, exports) - without this,
        # "edit & approve" silently kept showing the original AI-generated text everywhere despite
        # the reviewer's changes.
        plan.content = validated.model_dump()

    db.add(
        Approval(
            plan_id=plan.id,
            reviewer_id=user.id,
            decision=payload.decision,
            feedback=payload.feedback,
            final_content=payload.final_content,
        )
    )
    db.commit()

    prepare_resume(db, run)
    background_tasks.add_task(
        run_in_background,
        session_factory,
        execute_resume_decision,
        run.id,
        change_request.id,
        {"decision": payload.decision, "feedback": payload.feedback},
        checkpointer,
        **agent_overrides,
    )

    return _run_to_out(db, run)
