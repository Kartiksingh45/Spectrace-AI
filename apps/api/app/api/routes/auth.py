import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_administrator
from app.core.config import settings
from app.core.security import COOKIE_NAME, create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UpdateUserRoleRequest,
    UserOut,
)
from app.services.email import send_password_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_MAX_AGE_SECONDS = settings.access_token_expire_minutes * 60


def _set_session_cookie(response: Response, user_id: str) -> None:
    token = create_access_token(user_id)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        max_age=COOKIE_MAX_AGE_SECONDS,
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> User:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    _set_session_cookie(response, str(user.id))
    return user


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    _set_session_cookie(response, str(user.id))
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(
        COOKIE_NAME, path="/", samesite=settings.cookie_samesite, secure=settings.cookie_secure
    )


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    user.password_hash = hash_password(payload.new_password)
    db.commit()


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> None:
    """Always responds 204 regardless of whether the email is registered - a different response
    for "no such account" would let anyone enumerate registered emails one guess at a time."""
    user = db.query(User).filter(User.email == payload.email).first()
    if user:
        token = secrets.token_urlsafe(32)
        user.reset_token_hash = hashlib.sha256(token.encode()).hexdigest()
        user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.password_reset_token_expire_minutes
        )
        db.commit()
        reset_url = f"{settings.frontend_origin}/reset-password?token={token}"
        send_password_reset_email(user.email, reset_url)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> None:
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    user = db.query(User).filter(User.reset_token_hash == token_hash).first()
    expires_at = user.reset_token_expires_at if user else None
    if expires_at is not None and expires_at.tzinfo is None:
        # SQLite (only used in tests - a real Postgres column always round-trips tz-aware) drops
        # tzinfo on read, which would otherwise make this comparison raise outright.
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not user or expires_at is None or expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This reset link is invalid or has expired")

    user.password_hash = hash_password(payload.new_password)
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    db.commit()


@router.get("/users", response_model=list[UserOut])
def list_users(
    admin: User = Depends(require_administrator), db: Session = Depends(get_db)
) -> list[User]:
    return db.query(User).order_by(User.created_at).all()


@router.patch("/users/{user_id}/role", response_model=UserOut)
def update_user_role(
    user_id: uuid.UUID,
    payload: UpdateUserRoleRequest,
    admin: User = Depends(require_administrator),
    db: Session = Depends(get_db),
) -> User:
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target.role = payload.role
    db.commit()
    db.refresh(target)
    return target
