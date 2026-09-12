import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EvaluationCategory = Literal["clear", "cross_source", "ambiguous", "unsupported"]
EvaluationBehavior = Literal["direct_answer", "clarification", "insufficient_evidence", "failed"]


class EvaluationCaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    request_text: str = Field(min_length=1, max_length=5000)
    category: EvaluationCategory
    expected_behavior: EvaluationBehavior
    expected_sources: list[str] = Field(default_factory=list)
    expected_affected_files: list[str] = Field(default_factory=list)


class EvaluationCaseOut(BaseModel):
    id: uuid.UUID
    title: str
    request_text: str
    category: EvaluationCategory
    expected_behavior: EvaluationBehavior
    expected_sources: list[str]
    expected_affected_files: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluationResultOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    run_id: uuid.UUID | None
    actual_behavior: EvaluationBehavior
    retrieved_sources: list[str]
    affected_files: list[str]
    confidence: str | None
    passed: bool
    notes: str | None
    latency_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluationReportOut(BaseModel):
    total_cases: int
    total_results: int
    overall_pass_rate: float | None
    retrieval_hit_rate: float | None
    affected_file_precision: float | None
    citation_correctness: float | None
    clarification_accuracy: float | None
    unsupported_claim_rate: float | None
    reviewer_acceptance: float | None
    median_latency_ms: int | None
    max_latency_ms: int | None
