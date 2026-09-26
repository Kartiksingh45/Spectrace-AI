"""remove evaluation harness: drop evaluation_cases, evaluation_results

The evaluation harness (added in 0004) was removed - cases are inherently
tied to a single project's own content, so a dataset didn't have a
meaningful home outside a project's own workspace, and the feature wasn't
proving useful enough to keep. This drops what 0004 created rather than
rewriting that migration, to keep migration history stable for anyone who
already applied it.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

evaluation_category = postgresql.ENUM(
    "clear", "cross_source", "ambiguous", "unsupported",
    name="evaluation_category", create_type=False,
)
evaluation_behavior = postgresql.ENUM(
    "direct_answer", "clarification", "insufficient_evidence", "failed",
    name="evaluation_behavior", create_type=False,
)


def upgrade() -> None:
    op.drop_index("ix_evaluation_results_case_id", table_name="evaluation_results")
    op.drop_table("evaluation_results")
    op.drop_index("ix_evaluation_cases_project_id", table_name="evaluation_cases")
    op.drop_table("evaluation_cases")

    for enum in (evaluation_behavior, evaluation_category):
        enum.drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    for enum in (evaluation_category, evaluation_behavior):
        enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "evaluation_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("request_text", sa.Text(), nullable=False),
        sa.Column("category", evaluation_category, nullable=False),
        sa.Column("expected_behavior", evaluation_behavior, nullable=False),
        sa.Column("expected_sources", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("expected_affected_files", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evaluation_cases_project_id", "evaluation_cases", ["project_id"])

    op.create_table(
        "evaluation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evaluation_cases.id"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=True),
        sa.Column("actual_behavior", evaluation_behavior, nullable=False),
        sa.Column("retrieved_sources", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("affected_files", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("evidence_chunk_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("confidence", sa.String(16), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evaluation_results_case_id", "evaluation_results", ["case_id"])
