import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AgentStepStatus


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_summary: Mapped[str] = mapped_column(Text, nullable=False)
    output_summary: Mapped[str] = mapped_column(Text, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[AgentStepStatus] = mapped_column(
        Enum(AgentStepStatus, name="agent_step_status"), default=AgentStepStatus.ok, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
