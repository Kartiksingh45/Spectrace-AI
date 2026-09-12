import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agent.checkpointer import get_checkpointer
from app.api.deps import get_agent_overrides, get_current_user, require_project_member
from app.db.session import get_db
from app.models.evaluation import EvaluationCase
from app.models.project import Project
from app.models.user import User
from app.schemas.evaluation import EvaluationCaseCreate, EvaluationCaseOut, EvaluationReportOut, EvaluationResultOut
from app.services.evaluation import compute_report, run_dataset

router = APIRouter(prefix="/projects/{project_id}/evaluation", tags=["evaluation"])


@router.post("/cases", response_model=EvaluationCaseOut, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: EvaluationCaseCreate,
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
) -> EvaluationCase:
    case = EvaluationCase(project_id=project.id, **payload.model_dump())
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


@router.get("/cases", response_model=list[EvaluationCaseOut])
def list_cases(
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
) -> list[EvaluationCase]:
    return (
        db.query(EvaluationCase)
        .filter(EvaluationCase.project_id == project.id)
        .order_by(EvaluationCase.created_at.asc())
        .all()
    )


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    case_id: uuid.UUID,
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
) -> None:
    case = db.get(EvaluationCase, case_id)
    if not case or case.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation case not found")
    db.delete(case)
    db.commit()


@router.post("/run", response_model=list[EvaluationResultOut])
def run_evaluation(
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    checkpointer=Depends(get_checkpointer),
    agent_overrides: dict = Depends(get_agent_overrides),
):
    if not db.query(EvaluationCase).filter(EvaluationCase.project_id == project.id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No evaluation cases to run")
    return run_dataset(db, project.id, checkpointer, created_by=user.id, **agent_overrides)


@router.get("/report", response_model=EvaluationReportOut)
def get_report(
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
) -> dict:
    return compute_report(db, project.id)
