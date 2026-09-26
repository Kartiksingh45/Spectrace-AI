"""add documents.duration_ms

Records how long ingestion (parsing + chunking + embedding) took for a document, so it can be
surfaced alongside the existing agent_runs/agent_steps duration tracking rather than only living
in application logs.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("duration_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "duration_ms")
