import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ApprovalDecision


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("generated_plans.id"), nullable=False)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    decision: Mapped[ApprovalDecision] = mapped_column(
        Enum(ApprovalDecision, name="approval_decision"), nullable=False
    )
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_content: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
