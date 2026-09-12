import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.enums import ChangeRequestStatus, RequestType


class ChangeRequestCreate(BaseModel):
    request_text: str = Field(min_length=1, max_length=5000)


class ChangeRequestOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    request_text: str
    request_type: RequestType | None
    status: ChangeRequestStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class StepOut(BaseModel):
    step_index: int
    tool_name: str | None
    input_summary: str
    output_summary: str
    status: str

    model_config = {"from_attributes": True}


class RunOut(BaseModel):
    id: uuid.UUID
    change_request_id: uuid.UUID
    status: str
    steps: list[StepOut]
    pending_question: str | None
    generated_plan: dict[str, Any] | None
    plan_id: uuid.UUID | None


class ClarificationAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=2000)


class DecisionRequest(BaseModel):
    decision: Literal["approved", "edit_approved", "rejected", "regenerate_requested"]
    feedback: str | None = None
    final_content: dict[str, Any] | None = None
