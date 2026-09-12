import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GeneratedPlan(Base):
    __tablename__ = "generated_plans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    change_request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("change_requests.id"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
