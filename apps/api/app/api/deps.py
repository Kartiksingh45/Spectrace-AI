import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import COOKIE_NAME, decode_access_token
from app.db.session import get_db
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User


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


def require_project_member(
    project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Project:
    project = db.get(Project, project_id)
    if not project or not get_membership(db, project_id, user.id):
        # 404 rather than 403 so a project a user cannot access is indistinguishable from one that does not exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project
