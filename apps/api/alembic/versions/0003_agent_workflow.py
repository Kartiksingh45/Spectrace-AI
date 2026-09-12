"""agent workflow: change_requests, agent_runs, agent_steps, generated_plans, approvals

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

request_type = postgresql.ENUM(
    "feature", "bug", "refactor", "security", "performance", "documentation",
    name="request_type", create_type=False,
)
change_request_status = postgresql.ENUM(
    "pending", "analysing", "awaiting_clarification", "awaiting_approval", "approved", "rejected", "failed",
    name="change_request_status", create_type=False,
)
agent_run_status = postgresql.ENUM(
    "running", "awaiting_clarification", "awaiting_approval", "completed", "failed",
    name="agent_run_status", create_type=False,
)
agent_step_status = postgresql.ENUM("ok", "error", name="agent_step_status", create_type=False)
approval_decision = postgresql.ENUM(
    "approved", "edit_approved", "rejected", "regenerate_requested",
    name="approval_decision", create_type=False,
)


def upgrade() -> None:
    for enum in (request_type, change_request_status, agent_run_status, agent_step_status, approval_decision):
        enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "change_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_text", sa.Text(), nullable=False),
        sa.Column("request_type", request_type, nullable=True),
        sa.Column("status", change_request_status, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_change_requests_project_id", "change_requests", ["project_id"])

    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "change_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("change_requests.id"), nullable=False
        ),
        sa.Column("thread_id", sa.String(64), nullable=False, unique=True),
        sa.Column("status", agent_run_status, nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_runs_change_request_id", "agent_runs", ["change_request_id"])

    op.create_table(
        "agent_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(64), nullable=True),
        sa.Column("input_summary", sa.Text(), nullable=False),
        sa.Column("output_summary", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("status", agent_step_status, nullable=False, server_default="ok"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_steps_run_id", "agent_steps", ["run_id"])

    op.create_table(
        "generated_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "change_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("change_requests.id"), nullable=False
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_generated_plans_change_request_id", "generated_plans", ["change_request_id"])

    op.create_table(
        "approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generated_plans.id"), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision", approval_decision, nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("final_content", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_approvals_plan_id", "approvals", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_approvals_plan_id", table_name="approvals")
    op.drop_table("approvals")
    op.drop_index("ix_generated_plans_change_request_id", table_name="generated_plans")
    op.drop_table("generated_plans")
    op.drop_index("ix_agent_steps_run_id", table_name="agent_steps")
    op.drop_table("agent_steps")
    op.drop_index("ix_agent_runs_change_request_id", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ix_change_requests_project_id", table_name="change_requests")
    op.drop_table("change_requests")

    for enum in (approval_decision, agent_step_status, agent_run_status, change_request_status, request_type):
        enum.drop(op.get_bind(), checkfirst=True)
