"""add document embedding progress (chunks_total, chunks_embedded)

Ingestion embeds chunks in batches against Jina's rate-limited API, which can take minutes for a
large codebase - these columns let the client render a live percentage instead of an
indeterminate "processing" state with no sense of how much is left.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("chunks_total", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("chunks_embedded", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "chunks_embedded")
    op.drop_column("documents", "chunks_total")
