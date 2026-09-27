import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_membership
from app.db.session import get_db
from app.models.agent_run import AgentRun
from app.models.agent_step import AgentStep
from app.models.approval import Approval
from app.models.brd_document import BrdDocument
from app.models.change_request import ChangeRequest
from app.models.content_chunk import ContentChunk
from app.models.document import Document
from app.models.generated_plan import GeneratedPlan
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


def _get_owned_project_or_404(db: Session, project_id: uuid.UUID, user: User) -> Project:
    project = db.get(Project, project_id)
    if not project or not get_membership(db, project_id, user.id):
        # 404 rather than 403 so a project a user cannot access is indistinguishable from one that does not exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the project owner can do this")
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Project]:
    return (
        db.query(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .filter(ProjectMember.user_id == user.id)
        .order_by(Project.created_at.desc())
        .all()
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Project:
    project = Project(name=payload.name, owner_id=user.id)
    db.add(project)
    db.flush()

    db.add(ProjectMember(project_id=project.id, user_id=user.id))
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Project:
    project = db.get(Project, project_id)
    if not project or not get_membership(db, project_id, user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    project = _get_owned_project_or_404(db, project_id, user)
    project.name = payload.name
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    """No FK is set up with ON DELETE CASCADE (nor is any SQLAlchemy relationship cascade
    configured on Project), so every table that hangs off a project - directly or transitively
    through a change_request/agent_run/generated_plan - has to be cleared in child-before-parent
    order, or Postgres rejects the final project delete with a foreign key violation."""
    project = _get_owned_project_or_404(db, project_id, user)

    change_request_ids = db.query(ChangeRequest.id).filter(ChangeRequest.project_id == project.id).scalar_subquery()
    run_ids = db.query(AgentRun.id).filter(AgentRun.change_request_id.in_(change_request_ids)).scalar_subquery()
    plan_ids = db.query(GeneratedPlan.id).filter(GeneratedPlan.change_request_id.in_(change_request_ids)).scalar_subquery()

    db.query(Approval).filter(Approval.plan_id.in_(plan_ids)).delete(synchronize_session=False)
    db.query(GeneratedPlan).filter(GeneratedPlan.change_request_id.in_(change_request_ids)).delete(synchronize_session=False)
    db.query(AgentStep).filter(AgentStep.run_id.in_(run_ids)).delete(synchronize_session=False)
    db.query(AgentRun).filter(AgentRun.change_request_id.in_(change_request_ids)).delete(synchronize_session=False)
    db.query(ChangeRequest).filter(ChangeRequest.project_id == project.id).delete(synchronize_session=False)
    db.query(ContentChunk).filter(ContentChunk.project_id == project.id).delete(synchronize_session=False)
    # Nulled first - a re-uploaded document's previous_version_id can point at another document in
    # this same project, which would otherwise trip the same FK violation as the rows above.
    db.query(Document).filter(Document.project_id == project.id).update(
        {"previous_version_id": None}, synchronize_session=False
    )
    db.query(Document).filter(Document.project_id == project.id).delete(synchronize_session=False)
    db.query(BrdDocument).filter(BrdDocument.project_id == project.id).delete(synchronize_session=False)
    db.query(ProjectMember).filter(ProjectMember.project_id == project.id).delete(synchronize_session=False)
    db.delete(project)
    db.commit()
