from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


StudyPlanStatus = Literal["draft", "active", "completed", "archived"]
StudyPlanItemStatus = Literal["not_started", "in_progress", "completed"]
StudyPlanUnscheduledReason = Literal[
    "deadline_passed",
    "daily_capacity",
    "daily_focus_limit",
    "daily_capacity_and_focus_limit",
]


class PlanSourceIdentity(BaseModel):
    """A current source identity retained inside a plan item snapshot."""

    source_id: int = Field(gt=0)
    navigation_key: str = Field(pattern=r"^[0-9a-f]{32}$")


class StudyPlanItem(BaseModel):
    """One editable daily review session stored inside a study plan snapshot."""

    id: str = Field(min_length=1, max_length=80)
    navigation_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    date: date
    phase: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=2000)
    minutes: int = Field(ge=1, le=1440)
    status: StudyPlanItemStatus = "not_started"
    knowledge_points: list[str] = Field(default_factory=list, max_length=20)
    source_material_ids: list[int] = Field(default_factory=list, max_length=50)
    source_task_ids: list[int] = Field(default_factory=list, max_length=50)
    source_material_refs: list[PlanSourceIdentity] = Field(default_factory=list, max_length=50)
    source_task_refs: list[PlanSourceIdentity] = Field(default_factory=list, max_length=50)


class StudyPlanUnscheduledItem(BaseModel):
    """Source work that could not be placed within the plan's hard bounds."""

    source_type: Literal["task", "material"]
    source_id: int = Field(gt=0)
    navigation_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    label: str = Field(min_length=1, max_length=255)
    requested_minutes: int = Field(ge=1, le=10080)
    scheduled_minutes: int = Field(ge=0, le=10080)
    unscheduled_minutes: int = Field(ge=1, le=10080)
    latest_date: date | None = None
    reason: StudyPlanUnscheduledReason
    message: str = Field(min_length=1, max_length=500)


class StudyPlanGenerate(BaseModel):
    course_id: int
    exam_date: date
    daily_minutes: int = Field(
        ge=15,
        le=1440,
        description="本计划每天可用于复习的分钟上限；不自动与其他计划或每周容量偏好共享",
    )
    title: str | None = Field(default=None, max_length=200)


class StudyPlanUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    exam_date: date | None = None
    daily_minutes: int | None = Field(
        default=None,
        ge=15,
        le=1440,
        description="本计划每天可用于复习的分钟上限；不自动与其他计划或每周容量偏好共享",
    )
    status: StudyPlanStatus | None = None
    items: list[StudyPlanItem] | None = Field(default=None, max_length=366)


class StudyPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    navigation_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    revision: int = Field(ge=1)
    course_id: int | None
    title: str
    exam_date: date | None
    daily_minutes: int | None = Field(
        description="本计划每天可用于复习的分钟上限；不自动与其他计划或每周容量偏好共享"
    )
    plan_content: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    items: list[StudyPlanItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unscheduled_items: list[StudyPlanUnscheduledItem] = Field(default_factory=list)
    material_count: int = 0
    task_count: int = 0
    completed_item_count: int = 0
    total_minutes: int = 0
    completed_minutes: int = 0
