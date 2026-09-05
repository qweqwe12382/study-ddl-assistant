"""Traceable output contracts for seven-day learning-capacity checks."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CapacityTaskRead(BaseModel):
    id: int
    navigation_key: str | None = None
    name: str
    course_id: int | None
    due_at: datetime
    estimated_minutes: int | None
    remaining_minutes: int | None
    counted_minutes: int | None


class DeadlineDateGroupRead(BaseModel):
    local_date: str
    task_ids: list[int]
    task_count: int = Field(ge=2)
    known_workload_minutes: int = Field(ge=0)


class DailyRiskGroupRead(BaseModel):
    local_date: str
    task_ids: list[int]
    known_workload_minutes: int = Field(ge=0)
    missing_estimate_task_ids: list[int]
    risk_level: Literal["high", "medium", "unknown", "low"]
    overload_minutes: int = Field(ge=0)


class CapacityCalculationBasisRead(BaseModel):
    evaluated_at: datetime
    window_end: datetime
    task_filter: str
    workload_formula: str
    weekly_available_minutes: int = Field(ge=300)
    daily_limit_minutes: int = Field(ge=30)
    buffer_ratio: float = Field(ge=0, le=0.5)
    base_capacity_minutes: int = Field(ge=0)
    effective_capacity_minutes: int = Field(ge=0)
    effective_daily_capacity_minutes: int = Field(ge=0)
    timezone: str
    preference_snapshot: dict[str, object]


class CapacityRead(BaseModel):
    effective_capacity_minutes: int = Field(ge=0)
    known_workload_minutes: int = Field(ge=0)
    missing_estimate_task_ids: list[int]
    risk_level: Literal["high", "medium", "unknown", "low"]
    calculation_basis: CapacityCalculationBasisRead
    same_day_deadline_groups: list[DeadlineDateGroupRead]
    daily_risk_groups: list[DailyRiskGroupRead]
    tasks: list[CapacityTaskRead]
