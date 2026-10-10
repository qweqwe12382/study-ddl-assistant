"""Task-related business rules."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task import Task
from app.services.agent_feedback import create_plan_delta_candidates
from app.time import as_utc, utc_now


def reconcile_overdue_status(task: Task, *, now: datetime | None = None) -> bool:
    """Recompute only the overdue facet; terminal states stay terminal."""
    if task.status in {"completed", "canceled"}:
        return False
    previous = task.status
    if task.due_at is not None and as_utc(task.due_at) < (now or utc_now()):
        task.status = "overdue"
    elif task.status == "overdue":
        task.status = "not_started"
    return previous != task.status


def sync_overdue_tasks(db: Session) -> int:
    """Reconcile overdue status after time passes or a deadline changes.

    The operation is intentionally idempotent and leaves completed tasks
    untouched, so a completed task cannot be made overdue by a later refresh.
    """

    now = utc_now()
    candidates = db.scalars(
        select(Task).where(
            Task.status.in_(["not_started", "in_progress", "overdue"]),
        )
    ).all()
    changed = 0
    for task in candidates:
        if reconcile_overdue_status(task, now=now):
            trigger = "task_overdue" if task.status == "overdue" else "deadline_changed"
            create_plan_delta_candidates(db, task, trigger, now=now)
            changed += 1
    if changed:
        db.commit()
    return changed
