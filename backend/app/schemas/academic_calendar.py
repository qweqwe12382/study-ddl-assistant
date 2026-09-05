from datetime import datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.time import as_utc, deadline_to_utc


WeekPattern = Literal["all", "odd", "even"]
ExamType = Literal["quiz", "midterm", "final", "other"]


class ClassSessionBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    course_id: int = Field(gt=0)
    weekday: int = Field(ge=1, le=7)
    start_time: time
    end_time: time
    location: str | None = Field(default=None, max_length=120)
    start_week: int = Field(default=1, ge=1, le=30)
    end_week: int = Field(default=18, ge=1, le=30)
    week_pattern: WeekPattern = "all"
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        if self.end_week < self.start_week:
            raise ValueError("end_week must not be earlier than start_week")
        return self


class ClassSessionCreate(ClassSessionBase):
    pass


class ClassSessionUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    course_id: int | None = Field(default=None, gt=0)
    weekday: int | None = Field(default=None, ge=1, le=7)
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = Field(default=None, max_length=120)
    start_week: int | None = Field(default=None, ge=1, le=30)
    end_week: int | None = Field(default=None, ge=1, le=30)
    week_pattern: WeekPattern | None = None
    note: str | None = Field(default=None, max_length=500)


class ClassSessionRead(ClassSessionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    navigation_key: str = Field(pattern=r"^[0-9a-f]{32}$")
    revision: int = Field(ge=1)
    course_name: str
    course_color: str | None = None
    teacher: str | None = None
    created_at: datetime
    updated_at: datetime


class ExamBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    course_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=160)
    exam_type: ExamType = "final"
    starts_at: datetime
    ends_at: datetime | None = None
    location: str | None = Field(default=None, max_length=120)
    seat_number: str | None = Field(default=None, max_length=50)
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")
        return self


class ExamCreate(ExamBase):
    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        return deadline_to_utc(value) if value is not None else None


class ExamUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    course_id: int | None = Field(default=None, gt=0)
    title: str | None = Field(default=None, min_length=1, max_length=160)
    exam_type: ExamType | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    location: str | None = Field(default=None, max_length=120)
    seat_number: str | None = Field(default=None, max_length=50)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        return deadline_to_utc(value) if value is not None else None


class ExamRead(ExamBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    navigation_key: str = Field(pattern=r"^[0-9a-f]{32}$")
    revision: int = Field(ge=1)
    course_name: str
    course_color: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("starts_at", "ends_at")
    @classmethod
    def serialize_datetime(cls, value: datetime | None) -> datetime | None:
        return as_utc(value) if value is not None else None


class AcademicCalendarOverview(BaseModel):
    week: int = Field(ge=1, le=30)
    class_sessions: list[ClassSessionRead]
    exams: list[ExamRead]
