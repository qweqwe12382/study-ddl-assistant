"""Deterministic, candidate-only learning-agent rules."""

from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.agent import AgentEvent, AgentRun, AgentSuggestion
from app.models.task import Task
from app.time import as_utc, utc_now

ADJUST_PRIORITY = "adjust_priority"
SET_TASK_ESTIMATE = "set_task_estimate"
START_TASK = "start_task"
DEADLINE_WITHIN_48H = "deadline_within_48h"
MISSING_ESTIMATE = "missing_estimate"
START_URGENT_TASK = "start_urgent_task"
PENDING = "pending"
UNFINISHED_TASK_STATUSES = ("not_started", "in_progress")
RULESET_VERSION = "m8.3"


def is_priority_candidate(task: Task, now: datetime) -> bool:
    if task.status not in UNFINISHED_TASK_STATUSES or task.priority > 3 or task.due_at is None:
        return False
    due_at = as_utc(task.due_at)
    return now < due_at <= now + timedelta(hours=48)


def task_snapshot_payload(task: Task) -> dict[str, object]:
    """Return the bounded Task state a suggestion is permitted to act on."""

    return {
        "priority": task.priority,
        "due_at": as_utc(task.due_at).isoformat() if task.due_at is not None else None,
        "status": task.status,
        "estimated_minutes": task.estimated_minutes,
        "remaining_minutes": task.remaining_minutes,
    }


def task_fingerprint(task: Task, action_type: str = ADJUST_PRIORITY) -> str:
    """Hash the bounded source snapshot for one server-defined action."""

    snapshot = {
        "action_type": action_type,
        "task_id": task.id,
        "navigation_key": task.navigation_key,
        "priority": task.priority,
        "due_at": as_utc(task.due_at).isoformat() if task.due_at is not None else None,
        "updated_at": as_utc(task.updated_at).isoformat(),
        "status": task.status,
        "estimated_minutes": task.estimated_minutes,
        "remaining_minutes": task.remaining_minutes,
    }
    serialized = json.dumps(snapshot, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def risk_level_for(task: Task, now: datetime) -> str:
    """Bound risk to the deadline window used by this deterministic rule."""

    hours_remaining = (as_utc(task.due_at) - now).total_seconds() / 3600  # candidate rule guarantees due_at
    return "high" if hours_remaining <= 24 else "medium"


def is_estimate_candidate(task: Task, now: datetime) -> bool:
    """Only future-seven-day unfinished work can request an estimate."""

    return (
        task.status in UNFINISHED_TASK_STATUSES
        and task.estimated_minutes is None
        and task.due_at is not None
        and now < as_utc(task.due_at) <= now + timedelta(days=7)
    )


def is_start_candidate(task: Task, now: datetime) -> bool:
    """Starting is intentionally bounded to imminent, not-yet-started tasks."""

    return (
        task.status == "not_started"
        and task.estimated_minutes is not None
        and task.due_at is not None
        and as_utc(task.due_at) > now
        and as_utc(task.due_at) <= now + timedelta(hours=48)
    )


def is_action_candidate(task: Task, action_type: str, now: datetime) -> bool:
    if action_type == ADJUST_PRIORITY:
        return is_priority_candidate(task, now)
    if action_type == SET_TASK_ESTIMATE:
        return is_estimate_candidate(task, now)
    if action_type == START_TASK:
        return is_start_candidate(task, now)
    return False


def _event(
    event_type: str,
    *,
    task: Task | None,
    suggestion_id: int | None = None,
    run_id: int | None = None,
    payload: dict[str, object] | None = None,
) -> AgentEvent:
    return AgentEvent(
        event_type=event_type,
        suggestion_id=suggestion_id,
        run_id=run_id,
        entity_type="task" if task is not None else None,
        entity_id=task.id if task is not None else None,
        entity_navigation_key=task.navigation_key if task is not None else None,
        payload=payload or {},
    )


def _new_suggestion(task: Task, action_type: str, evaluated_at: datetime, run_id: int) -> AgentSuggestion:
    due_at = as_utc(task.due_at) if task.due_at is not None else evaluated_at + timedelta(hours=1)
    current_payload = task_snapshot_payload(task)
    if action_type == ADJUST_PRIORITY:
        return AgentSuggestion(
            action_type=action_type, status=PENDING, source_type="task", source_id=task.id, source_navigation_key=task.navigation_key, source_name=task.name,
            title=f"提升“{task.name}”的优先级",
            explanation=f"任务将在 {(due_at - evaluated_at).total_seconds() / 3600:.1f} 小时内到期，建议提升优先级以便优先处理。",
            reason_code=DEADLINE_WITHIN_48H, current_payload=current_payload, proposed_payload={"priority": 4},
            risk_level=risk_level_for(task, evaluated_at), confidence=0.9, expires_at=due_at,
            fingerprint=task_fingerprint(task, action_type), run_id=run_id, created_at=evaluated_at, updated_at=evaluated_at,
        )
    if action_type == SET_TASK_ESTIMATE:
        return AgentSuggestion(
            action_type=action_type, status=PENDING, source_type="task", source_id=task.id, source_navigation_key=task.navigation_key, source_name=task.name,
            title=f"补充“{task.name}”的预计时长",
            explanation="该任务在容量计算窗口内但尚无预计时长，补充后才能得到可解释的负荷结论。",
            reason_code=MISSING_ESTIMATE, current_payload=current_payload,
            proposed_payload={"estimated_minutes": {"minimum": 15, "maximum": 10080}},
            risk_level="unknown", confidence=0.95, expires_at=due_at,
            fingerprint=task_fingerprint(task, action_type), run_id=run_id, created_at=evaluated_at, updated_at=evaluated_at,
        )
    return AgentSuggestion(
        action_type=action_type, status=PENDING, source_type="task", source_id=task.id, source_navigation_key=task.navigation_key, source_name=task.name,
        title=f"开始处理“{task.name}”", explanation="任务即将到期且尚未开始，可将其标记为进行中以反映真实进度。",
        reason_code=START_URGENT_TASK, current_payload=current_payload, proposed_payload={"status": "in_progress"},
        risk_level=risk_level_for(task, evaluated_at), confidence=0.8, expires_at=due_at,
        fingerprint=task_fingerprint(task, action_type), run_id=run_id, created_at=evaluated_at, updated_at=evaluated_at,
    )


def refresh_suggestions(db: Session, *, now: datetime | None = None) -> AgentRun:
    """Create/reuse only deterministic, server-whitelisted action suggestions."""

    evaluated_at = now or utc_now()
    run = AgentRun(
        trigger="manual_refresh",
        status="running",
        ruleset_version=RULESET_VERSION,
        input_snapshot={
            "evaluated_at": evaluated_at.isoformat(), "actions": [ADJUST_PRIORITY, SET_TASK_ESTIMATE, START_TASK],
            "priority_window_hours": 48, "capacity_window_days": 7,
        },
        created_at=evaluated_at,
        completed_at=evaluated_at,
    )
    db.add(run)
    db.flush()

    action_types = (ADJUST_PRIORITY, SET_TASK_ESTIMATE, START_TASK)
    pending = list(db.scalars(select(AgentSuggestion).where(
        AgentSuggestion.action_type.in_(action_types), AgentSuggestion.status == PENDING,
    )).all())
    protected_fingerprints = set(
        db.scalars(
            select(AgentSuggestion.fingerprint).where(
                AgentSuggestion.action_type.in_(action_types),
                AgentSuggestion.status.in_((PENDING, "dismissed", "executed")),
            )
        ).all()
    )
    expired_count = 0
    for suggestion in pending:
        task = db.get(Task, suggestion.source_id)
        if task is not None and task.navigation_key != suggestion.source_navigation_key:
            task = None
        if (
            task is None
            or as_utc(suggestion.expires_at) <= evaluated_at
            or not is_action_candidate(task, suggestion.action_type, evaluated_at)
            or suggestion.fingerprint != task_fingerprint(task, suggestion.action_type)
        ):
            suggestion.status = "expired"
            suggestion.updated_at = evaluated_at
            expired_count += 1
            db.add(
                _event(
                    "suggestion_expired",
                    task=task,
                    suggestion_id=suggestion.id,
                    run_id=run.id,
                    payload={"reason_code": "source_snapshot_changed" if task is not None else "source_missing"},
                )
            )

    generated_count = 0
    candidates = db.scalars(select(Task).where(Task.status.in_(UNFINISHED_TASK_STATUSES))).all()
    for task in candidates:
        for action_type in action_types:
            if not is_action_candidate(task, action_type, evaluated_at):
                continue
            fingerprint = task_fingerprint(task, action_type)
            # Do not recreate dismissed/executed work until the source snapshot changes.
            if fingerprint in protected_fingerprints:
                continue
            suggestion = _new_suggestion(task, action_type, evaluated_at, run.id)
            try:
                with db.begin_nested():
                    db.add(suggestion)
                    db.flush()
            except IntegrityError:
                db.expire_all()
                continue
            db.add(_event(
                "suggestion_created", task=task, suggestion_id=suggestion.id, run_id=run.id,
                payload={"reason_code": suggestion.reason_code, "source_id": task.id},
            ))
            protected_fingerprints.add(fingerprint)
            generated_count += 1

    run.generated_count = generated_count
    run.expired_count = expired_count
    run.status = "completed"
    run.completed_at = evaluated_at
    db.commit()
    return run
