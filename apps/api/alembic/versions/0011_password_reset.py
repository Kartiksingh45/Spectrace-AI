"""add password reset token columns to users

Supports the forgot-password flow: a hashed, short-lived token tied to the user who requested a
reset, rather than reusing anything derived from their current password.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("reset_token_hash", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("reset_token_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "reset_token_expires_at")
    op.drop_column("users", "reset_token_hash")
