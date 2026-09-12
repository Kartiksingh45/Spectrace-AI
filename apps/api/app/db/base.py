from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Imported here so Alembic autogenerate can discover every model via Base.metadata.
from app.models import user, project, project_member  # noqa: E402,F401
