"""Task-related business rules."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task import Task
from app.services.agent_feedback import create_plan_delta_candidates
from app.time import as_utc, utc_now


def sync_overdue_tasks(db: Session) -> int:
    """Mark unfinished tasks past their due time as overdue.

    The operation is intentionally idempotent and leaves completed tasks
    untouched, so a completed task cannot be made overdue by a later refresh.
    """

    now = utc_now()
    candidates = db.scalars(
        select(Task).where(
            Task.status.in_(["not_started", "in_progress"]),
            Task.due_at.is_not(None),
        )
    ).all()
    changed = 0
    for task in candidates:
        if task.due_at and as_utc(task.due_at) < now:
            task.status = "overdue"
            create_plan_delta_candidates(db, task, "task_overdue", now=now)
            changed += 1
    if changed:
        db.commit()
    return changed
