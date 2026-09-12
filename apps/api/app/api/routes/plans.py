import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agent.checkpointer import get_checkpointer
from app.api.deps import get_agent_overrides, get_current_user, get_membership
from app.api.routes.requests import _run_to_out
from app.db.session import get_db
from app.models.agent_run import AgentRun
from app.models.approval import Approval
from app.models.change_request import ChangeRequest
from app.models.enums import AgentRunStatus
from app.models.generated_plan import GeneratedPlan
from app.models.user import User
from app.schemas.agent import DecisionRequest, RunOut
from app.services.agent_runner import resume_decision

router = APIRouter(tags=["plans"])


@router.post("/plans/{plan_id}/decision", response_model=RunOut)
def submit_decision(
    plan_id: uuid.UUID,
    payload: DecisionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    checkpointer=Depends(get_checkpointer),
    agent_overrides: dict = Depends(get_agent_overrides),
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

    run = resume_decision(
        db,
        run,
        change_request,
        {"decision": payload.decision, "feedback": payload.feedback},
        checkpointer,
        **agent_overrides,
    )

    return _run_to_out(db, run)
