import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ProjectUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


ProjectStatus = Literal["draft", "in_progress", "complete"]


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    status: ProjectStatus
    requirement_count: int | None

    model_config = {"from_attributes": True}
