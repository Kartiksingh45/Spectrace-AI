from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Imported here so Alembic autogenerate can discover every model via Base.metadata.
from app.models import (  # noqa: E402,F401
    user,
    project,
    project_member,
    document,
    content_chunk,
    change_request,
    agent_run,
    agent_step,
    generated_plan,
    approval,
)
