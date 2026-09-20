"""Validated contracts for local learning-capacity preferences."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.timestamps import UtcDateTime

TimeSlot = Literal["morning", "afternoon", "evening"]


class StudyPreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekly_available_minutes: int | None = Field(default=None, ge=300, le=10080)
    daily_limit_minutes: int | None = Field(default=None, ge=30, le=1440)
    buffer_ratio: float | None = Field(default=None, ge=0, le=0.5)
    preferred_time_slots: list[TimeSlot] | None = None
    course_weights: dict[str, float] | None = None
    # The only clearable preference: a student removes the date between semesters.
    semester_start_date: date | None = None

    @field_validator(
        "weekly_available_minutes",
        "daily_limit_minutes",
        "buffer_ratio",
        "preferred_time_slots",
        "course_weights",
        mode="before",
    )
    @classmethod
    def reject_explicit_null(cls, value):
        if value is None:
            raise ValueError("preference fields cannot be null")
        return value

    @field_validator("preferred_time_slots")
    @classmethod
    def normalize_time_slots(cls, value: list[TimeSlot] | None) -> list[TimeSlot] | None:
        if value is None:
            return value
        deduplicated = list(dict.fromkeys(value))
        if not deduplicated:
            raise ValueError("preferred_time_slots must not be empty")
        return deduplicated

    @field_validator("course_weights")
    @classmethod
    def validate_course_weights(cls, value: dict[str, float] | None) -> dict[str, float] | None:
        if value is None:
            return value
        normalized: dict[str, float] = {}
        for course_id, weight in value.items():
            if not course_id.isdigit() or int(course_id) <= 0:
                raise ValueError("course_weights keys must be positive course-id strings")
            if not 0.5 <= weight <= 2.0:
                raise ValueError("course_weights values must be between 0.5 and 2.0")
            normalized[course_id] = weight
        return normalized


class StudyPreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    weekly_available_minutes: int
    daily_limit_minutes: int
    buffer_ratio: float
    preferred_time_slots: list[TimeSlot]
    course_weights: dict[str, float]
    semester_start_date: date | None = None
    created_at: UtcDateTime
    updated_at: UtcDateTime
