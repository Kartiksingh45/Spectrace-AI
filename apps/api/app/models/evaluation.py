import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import EvaluationBehavior, EvaluationCategory


class EvaluationCase(Base):
    """A single BRD Section 14.1 test-dataset entry: a change request with the behaviour and
    evidence a reviewer expects the agent to produce for it."""

    __tablename__ = "evaluation_cases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    request_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[EvaluationCategory] = mapped_column(
        Enum(EvaluationCategory, name="evaluation_category"), nullable=False
    )
    expected_behavior: Mapped[EvaluationBehavior] = mapped_column(
        Enum(EvaluationBehavior, name="evaluation_behavior"), nullable=False
    )
    expected_sources: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    expected_affected_files: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EvaluationResult(Base):
    """One run of an EvaluationCase through the real retrieval + agent pipeline, with the raw
    signals metrics are computed from (BRD 14.2) rather than pre-aggregated numbers, so the report
    can be recomputed as scoring logic evolves without re-running the agent."""

    __tablename__ = "evaluation_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("evaluation_cases.id"), nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("agent_runs.id"), nullable=True)
    actual_behavior: Mapped[EvaluationBehavior] = mapped_column(
        Enum(EvaluationBehavior, name="evaluation_behavior"), nullable=False
    )
    retrieved_sources: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    affected_files: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evidence_chunk_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
