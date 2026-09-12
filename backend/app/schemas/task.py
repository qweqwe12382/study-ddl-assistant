from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.time import as_utc, deadline_to_utc


TaskStatus = Literal["not_started", "in_progress", "completed", "overdue", "canceled"]


class TaskBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    course_id: int | None = None
    material_id: int | None = None
    name: str = Field(min_length=1, max_length=200)
    task_type: str | None = Field(default=None, max_length=50)
    description: str | None = None
    due_at: datetime | None = None
    priority: int = Field(default=3, ge=1, le=5)
    estimated_minutes: int | None = Field(default=None, ge=15, le=10080)
    remaining_minutes: int | None = Field(default=None, ge=0, le=10080)
    status: TaskStatus = "not_started"
    confidence: float | None = Field(default=None, ge=0, le=1)
    need_review: bool = False
    source_quote: str | None = None

    @model_validator(mode="after")
    def validate_remaining_minutes(self):
        if self.remaining_minutes is not None and self.estimated_minutes is None and self.status not in {"completed", "canceled"}:
            raise ValueError("remaining_minutes requires estimated_minutes")
        if (
            self.estimated_minutes is not None
            and self.remaining_minutes is not None
            and self.remaining_minutes > self.estimated_minutes
        ):
            raise ValueError("remaining_minutes cannot exceed estimated_minutes")
        return self


class TaskCreate(TaskBase):
    @field_validator("due_at")
    @classmethod
    def normalize_due_at(cls, value: datetime | None) -> datetime | None:
        return deadline_to_utc(value) if value is not None else None


class TaskUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    course_id: int | None = None
    material_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    task_type: str | None = Field(default=None, max_length=50)
    description: str | None = None
    due_at: datetime | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    estimated_minutes: int | None = Field(default=None, ge=15, le=10080)
    remaining_minutes: int | None = Field(default=None, ge=0, le=10080)
    status: TaskStatus | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    need_review: bool | None = None
    source_quote: str | None = None

    @field_validator("due_at")
    @classmethod
    def normalize_due_at(cls, value: datetime | None) -> datetime | None:
        return deadline_to_utc(value) if value is not None else None


class TaskRead(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    navigation_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    revision: int = Field(ge=1)
    material_navigation_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    source_material_name: str | None = None
    extraction_batch_id: str | None = None
    extraction_candidate_id: str | None = None
    actual_minutes: int | None = Field(default=None, ge=15, le=10080)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("due_at")
    @classmethod
    def serialize_persisted_due_at(cls, value: datetime | None) -> datetime | None:
        return as_utc(value) if value is not None else None
