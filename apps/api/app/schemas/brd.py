import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BrdInput(BaseModel):
    """What the coder actually fills in - plain-language project details, expanded by the LLM
    into the full structured document below."""

    project_name: str = Field(min_length=1, max_length=200)
    background: str = Field(min_length=1, max_length=3000, description="The business problem or context driving this project")
    objectives: str = Field(min_length=1, max_length=2000, description="What the project should achieve")
    target_users: str = Field(min_length=1, max_length=1000)
    key_features: str = Field(min_length=1, max_length=3000, description="Desired capabilities/features, in the coder's own words")
    constraints: str | None = Field(default=None, max_length=1000, description="Budget, timeline, technology, or regulatory constraints")


class BrdRequirement(BaseModel):
    description: str
    priority: Literal["must_have", "should_have", "could_have", "wont_have"]


class GeneratedBrd(BaseModel):
    """Structured LLM output - the full generated Business Requirements Document."""

    executive_summary: str
    business_objectives: list[str]
    in_scope: list[str]
    out_of_scope: list[str]
    stakeholders: list[str]
    functional_requirements: list[BrdRequirement]
    non_functional_requirements: list[BrdRequirement]
    assumptions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    success_criteria: list[str]


class BrdDocumentOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    inputs: BrdInput
    content: GeneratedBrd
    created_at: datetime

    model_config = {"from_attributes": True}
