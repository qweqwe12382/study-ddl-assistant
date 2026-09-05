"""Single-user preference persistence and deterministic capacity arithmetic."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.study_preference import StudyPreference
from app.models.task import Task
from app.schemas.capacity import CapacityRead
from app.time import LOCAL_TIMEZONE, as_local, as_utc, utc_now


def get_or_create_preference(db: Session) -> StudyPreference:
    preference = db.get(StudyPreference, 1)
    if preference is not None:
        return preference
    preference = StudyPreference(id=1)
    db.add(preference)
    db.commit()
    db.refresh(preference)
    return preference


def build_capacity(db: Session, *, evaluated_at: datetime | None = None) -> CapacityRead:
    """Build capacity at one caller-supplied instant (or the current UTC time)."""

    preference = get_or_create_preference(db)
    evaluated_at = evaluated_at or utc_now()
    window_end = evaluated_at + timedelta(days=7)
    tasks = list(db.scalars(select(Task).where(Task.status != "completed", Task.due_at.is_not(None))).all())
    included = [
        task
        for task in tasks
        if task.due_at is not None and evaluated_at < as_utc(task.due_at) <= window_end
    ]
    included.sort(key=lambda task: (as_utc(task.due_at), -task.priority, task.id))

    known_workload = 0
    missing_estimates: list[int] = []
    task_payloads = []
    grouped: dict[str, list[tuple[Task, int | None]]] = {}
    for task in included:
        counted = task.remaining_minutes if task.remaining_minutes is not None else task.estimated_minutes
        if task.estimated_minutes is None:
            missing_estimates.append(task.id)
        if counted is not None:
            known_workload += counted
        task_payloads.append(
            {
                "id": task.id,
                "navigation_key": task.navigation_key,
                "name": task.name,
                "course_id": task.course_id,
                "due_at": as_utc(task.due_at),
                "estimated_minutes": task.estimated_minutes,
                "remaining_minutes": task.remaining_minutes,
                "counted_minutes": counted,
            }
        )
        grouped.setdefault(as_local(task.due_at).date().isoformat(), []).append((task, counted))

    base_capacity = min(preference.weekly_available_minutes, preference.daily_limit_minutes * 7)
    effective_capacity = round(base_capacity * (1 - preference.buffer_ratio))
    effective_daily_capacity = round(preference.daily_limit_minutes * (1 - preference.buffer_ratio))
    daily_risk_groups = []
    for local_date, entries in sorted(grouped.items()):
        daily_known = sum(counted or 0 for _task, counted in entries)
        daily_missing = [task.id for task, _counted in entries if task.estimated_minutes is None]
        if daily_known > effective_daily_capacity:
            daily_risk = "high"
        elif daily_missing:
            daily_risk = "unknown"
        elif daily_known >= effective_daily_capacity * 0.8:
            daily_risk = "medium"
        else:
            daily_risk = "low"
        daily_risk_groups.append(
            {
                "local_date": local_date,
                "task_ids": [task.id for task, _counted in entries],
                "known_workload_minutes": daily_known,
                "missing_estimate_task_ids": daily_missing,
                "risk_level": daily_risk,
                "overload_minutes": max(0, daily_known - effective_daily_capacity),
            }
        )

    if known_workload > effective_capacity or any(group["risk_level"] == "high" for group in daily_risk_groups):
        risk_level = "high"
    elif missing_estimates:
        risk_level = "unknown"
    elif known_workload >= effective_capacity * 0.8 or any(group["risk_level"] == "medium" for group in daily_risk_groups):
        risk_level = "medium"
    else:
        risk_level = "low"

    same_day_groups = [
        {
            "local_date": local_date,
            "task_ids": [task.id for task, _counted in entries],
            "task_count": len(entries),
            "known_workload_minutes": sum(counted or 0 for _task, counted in entries),
        }
        for local_date, entries in sorted(grouped.items())
        if len(entries) >= 2
    ]
    return CapacityRead(
        effective_capacity_minutes=effective_capacity,
        known_workload_minutes=known_workload,
        missing_estimate_task_ids=missing_estimates,
        risk_level=risk_level,
        calculation_basis={
            "evaluated_at": evaluated_at,
            "window_end": window_end,
            "task_filter": "未完成、有截止时间、截止时间在未来 7 天 UTC 窗口内",
            "workload_formula": "sum(remaining_minutes ?? estimated_minutes)",
            "weekly_available_minutes": preference.weekly_available_minutes,
            "daily_limit_minutes": preference.daily_limit_minutes,
            "buffer_ratio": preference.buffer_ratio,
            "base_capacity_minutes": base_capacity,
            "effective_capacity_minutes": effective_capacity,
            "effective_daily_capacity_minutes": effective_daily_capacity,
            "timezone": str(LOCAL_TIMEZONE),
            "preference_snapshot": {
                "weekly_available_minutes": preference.weekly_available_minutes,
                "daily_limit_minutes": preference.daily_limit_minutes,
                "buffer_ratio": preference.buffer_ratio,
                "preferred_time_slots": preference.preferred_time_slots,
                "course_weights": preference.course_weights,
            },
        },
        same_day_deadline_groups=same_day_groups,
        daily_risk_groups=daily_risk_groups,
        tasks=task_payloads,
    )
