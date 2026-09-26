"""add document versioning (version, previous_version_id, full_text)

Supports the optional BRD feature "comparison of two requirement-document versions": re-uploading
a requirement document with the same filename links it to the prior version instead of being an
unrelated document, and full_text (independent of chunk boundaries) is what gets diffed.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column(
        "documents",
        sa.Column("previous_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
    )
    op.add_column("documents", sa.Column("full_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "full_text")
    op.drop_column("documents", "previous_version_id")
    op.drop_column("documents", "version")
