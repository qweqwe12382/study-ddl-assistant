from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


TaskStatus = Literal["not_started", "in_progress", "completed", "overdue"]


class TaskBase(BaseModel):
    course_id: int | None = None
    material_id: int | None = None
    name: str = Field(min_length=1, max_length=200)
    task_type: str | None = Field(default=None, max_length=50)
    description: str | None = None
    due_at: datetime | None = None
    priority: int = Field(default=3, ge=1, le=5)
    status: TaskStatus = "not_started"
    confidence: float | None = Field(default=None, ge=0, le=1)
    need_review: bool = False
    source_quote: str | None = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    course_id: int | None = None
    material_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    task_type: str | None = Field(default=None, max_length=50)
    description: str | None = None
    due_at: datetime | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    status: TaskStatus | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    need_review: bool | None = None
    source_quote: str | None = None


class TaskRead(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_material_name: str | None = None
    extraction_batch_id: str | None = None
    extraction_candidate_id: str | None = None
    created_at: datetime
    updated_at: datetime
