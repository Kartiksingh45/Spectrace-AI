import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import COOKIE_NAME, decode_access_token
from app.db.session import get_db
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User, UserRole


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    user_id = decode_access_token(token) if token else None
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user = db.get(User, uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def get_membership(db: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> ProjectMember | None:
    return (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        .first()
    )


def require_reviewer(user: User = Depends(get_current_user)) -> User:
    """Only a reviewer or administrator may approve, edit-approve, reject, or request
    regeneration of a plan - a contributor can submit requests but not decide on them."""
    if user.role not in (UserRole.reviewer, UserRole.administrator):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a reviewer or administrator can decide on a plan",
        )
    return user


def require_administrator(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.administrator:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required")
    return user


def require_project_member(
    project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Project:
    project = db.get(Project, project_id)
    if not project or not get_membership(db, project_id, user.id):
        # 404 rather than 403 so a project a user cannot access is indistinguishable from one that does not exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def get_agent_overrides() -> dict:
    """Extra kwargs forwarded to build_graph() (agent_model/classifier/plan_generator).

    Empty by default (the real Gemini model is used); tests override this dependency to inject a scripted
    fake model so the agent's tool-selection loop is deterministic and offline.
    """
    return {}


def get_brd_generator():
    """The real Gemini-backed generator by default; tests override this dependency to inject a
    deterministic fake so BRD generation is offline and free to run in the test suite."""
    from app.services.brd_generator import generate_brd

    return generate_brd
