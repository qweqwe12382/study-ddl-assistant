"""Bounded contracts for the DDL change radar."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent import ActionReceiptRead
from app.schemas.task import TaskRead

from app.schemas.timestamps import UtcDateTime


DeadlineChangeIntent = Literal["reschedule", "cancel"]
DeadlineChangeDirection = Literal["earlier", "later", "new_deadline", "removed"]
DeadlineRisk = Literal["low", "medium", "high", "unknown"]


class DeadlineRadarPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    task_id: int = Field(ge=1)
    task_navigation_key: str = Field(pattern=r"^[0-9a-f]{32}$")
    task_revision: int = Field(ge=1)
    notice_text: str = Field(min_length=4, max_length=4000)
    reference_time: datetime | None = None


class DeadlineRadarApplyRequest(DeadlineRadarPreviewRequest):
    idempotency_key: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$",
    )


class DeadlineRadarTaskRead(BaseModel):
    id: int
    navigation_key: str = Field(pattern=r"^[0-9a-f]{32}$")
    revision: int = Field(ge=1)
    name: str = Field(max_length=200)
    status: str
    current_due_at: UtcDateTime | None = None
    proposed_due_at: UtcDateTime | None = None


class DeadlineRadarEvidenceRead(BaseModel):
    quote: str = Field(max_length=360)
    marker: str = Field(max_length=24)
    detected_due_at: UtcDateTime | None = None
    warnings: list[str] = Field(default_factory=list, max_length=10)


class DeadlinePressureDayRead(BaseModel):
    local_date: date
    effective_capacity_minutes: int = Field(ge=0)
    before_minutes: int = Field(ge=0)
    after_minutes: int = Field(ge=0)
    before_overload_minutes: int = Field(ge=0)
    after_overload_minutes: int = Field(ge=0)
    before_risk: DeadlineRisk
    after_risk: DeadlineRisk
    before_task_count: int = Field(ge=0)
    after_task_count: int = Field(ge=0)
    affected: bool


class DeadlineRadarImpactRead(BaseModel):
    direction: DeadlineChangeDirection
    day_shift: int | None = None
    before_risk: DeadlineRisk
    after_risk: DeadlineRisk
    before_known_minutes: int = Field(ge=0)
    after_known_minutes: int = Field(ge=0)
    overload_delta_minutes: int
    summary: str = Field(max_length=300)


class DeadlineRadarPreviewRead(BaseModel):
    generated_at: UtcDateTime
    intent: DeadlineChangeIntent
    task: DeadlineRadarTaskRead
    evidence: DeadlineRadarEvidenceRead
    pressure_days: list[DeadlinePressureDayRead] = Field(min_length=7, max_length=7)
    impact: DeadlineRadarImpactRead
    action_label: str = Field(max_length=80)
    calculation_basis: dict[str, object]


class DeadlineRadarApplyRead(BaseModel):
    status: Literal["executed"] = "executed"
    intent: DeadlineChangeIntent
    task: TaskRead
    receipt: ActionReceiptRead
    plan_delta_count: int = Field(ge=0)
    message: str = Field(max_length=240)
