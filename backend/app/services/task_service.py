"""Task-related business rules."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task import Task


def _as_utc(value: datetime) -> datetime:
    """Normalize naive SQLite timestamps and aware timestamps to UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def sync_overdue_tasks(db: Session) -> int:
    """Mark unfinished tasks past their due time as overdue.

    The operation is intentionally idempotent and leaves completed tasks
    untouched, so a completed task cannot be made overdue by a later refresh.
    """

    now = datetime.now(timezone.utc)
    candidates = db.scalars(
        select(Task).where(
            Task.status.in_(["not_started", "in_progress"]),
            Task.due_at.is_not(None),
        )
    ).all()
    changed = 0
    for task in candidates:
        if task.due_at and _as_utc(task.due_at) < now:
            task.status = "overdue"
            changed += 1
    if changed:
        db.commit()
    return changed
