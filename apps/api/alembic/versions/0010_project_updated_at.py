"""add projects.updated_at

Supports a genuine "last edited" timestamp on the dashboard's project cards, bumped whenever a
project is renamed - rather than mislabeling created_at as "edited".

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("projects", "updated_at")
