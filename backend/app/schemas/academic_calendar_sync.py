from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from app.schemas.academic_calendar import ExamType, WeekPattern


class AcademicCalendarPreviewRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_type: Literal["ical"] = "ical"
    source_name: str = Field(min_length=1, max_length=120)
    semester_start: date
    semester_weeks: int = Field(default=18, ge=1, le=30)
    calendar_text: str = Field(min_length=1, max_length=1_000_000)


class AcademicCalendarImportItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    item_key: str = Field(pattern=r"^[0-9a-f]{24}$")
    external_uid: str = Field(min_length=1, max_length=255)
    kind: Literal["class_session", "exam"]
    course_name: str = Field(min_length=1, max_length=120)
    teacher: str | None = Field(default=None, max_length=120)
    weekday: int | None = Field(default=None, ge=1, le=7)
    start_time: time | None = None
    end_time: time | None = None
    start_week: int | None = Field(default=None, ge=1, le=30)
    end_week: int | None = Field(default=None, ge=1, le=30)
    week_pattern: WeekPattern | None = None
    title: str | None = Field(default=None, min_length=1, max_length=160)
    exam_type: ExamType | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    location: str | None = Field(default=None, max_length=120)
    seat_number: str | None = Field(default=None, max_length=50)
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_kind_fields(self):
        if self.kind == "class_session":
            required = (self.weekday, self.start_time, self.end_time, self.start_week, self.end_week, self.week_pattern)
            if any(value is None for value in required):
                raise ValueError("class session import fields are incomplete")
            if self.end_time <= self.start_time or self.end_week < self.start_week:
                raise ValueError("class session import range is invalid")
        else:
            if self.title is None or self.exam_type is None or self.starts_at is None:
                raise ValueError("exam import fields are incomplete")
            if self.ends_at is not None and self.ends_at <= self.starts_at:
                raise ValueError("exam import range is invalid")
        return self


class AcademicCalendarPreviewResponse(BaseModel):
    source_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_type: Literal["ical"]
    source_name: str
    credential_policy: Literal["not_collected", "ephemeral_memory"] = "not_collected"
    items: list[AcademicCalendarImportItem]
    class_count: int = Field(ge=0)
    exam_count: int = Field(ge=0)
    warnings: list[str]


class AcademicCalendarSyncRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_type: Literal["ical"] = "ical"
    source_name: str = Field(min_length=1, max_length=120)
    items: list[AcademicCalendarImportItem] = Field(min_length=1, max_length=300)


class AcademicCalendarSyncConflict(BaseModel):
    item_key: str
    course_name: str
    reason: Literal["schedule_conflict", "local_changed", "target_unavailable"]
    message: str


class AcademicCalendarSyncResponse(BaseModel):
    created: int = Field(ge=0)
    updated: int = Field(ge=0)
    unchanged: int = Field(ge=0)
    skipped: int = Field(ge=0)
    courses_created: int = Field(ge=0)
    conflicts: list[AcademicCalendarSyncConflict]


class NjustCaptchaResponse(BaseModel):
    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{32,96}$")
    image_data_uri: str
    expires_in_seconds: int = Field(ge=1, le=600)
    transport_warning: str


class NjustAcademicPreviewRequest(BaseModel):
    """One-shot NJUST login contract.

    The password is masked in model representations and is never part of the
    normalized preview response.  The API consumes the captcha session even
    when authentication fails, so callers must explicitly fetch a new one.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{32,96}$")
    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=128)
    captcha: str = Field(min_length=1, max_length=12, pattern=r"^[A-Za-z0-9]+$")
    term: str = Field(pattern=r"^\d{4}-\d{4}-[12]$")
    semester_start: date
    semester_weeks: int = Field(default=18, ge=1, le=30)
    acknowledge_insecure_transport: Literal[True]
