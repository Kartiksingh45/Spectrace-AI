from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]


class EvidenceRef(BaseModel):
    chunk_id: str = Field(description="The id of a chunk actually returned by a search tool this run")
    note: str = Field(description="Why this evidence is relevant to the request")


class AffectedFile(BaseModel):
    file_path: str = Field(description="A file path that actually appeared in code search results this run")
    reason: str
    confidence: Confidence


class TaskItem(BaseModel):
    category: Literal["frontend", "backend", "database", "testing"]
    description: str


class TestCase(BaseModel):
    kind: Literal["positive", "negative", "boundary", "permission", "regression"]
    description: str


class GeneratedPlan(BaseModel):
    """Structured analysis output - the agent's final proposal for a change request."""

    summary: str
    request_type: Literal["feature", "bug", "refactor", "security", "performance", "documentation"]
    questions: list[str] = Field(default_factory=list, description="Open questions not resolved during the run")
    evidence: list[EvidenceRef]
    affected_files: list[AffectedFile]
    user_story: str
    acceptance_criteria: list[str]
    tasks: list[TaskItem]
    test_cases: list[TestCase]
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    confidence: Confidence
