"""Explicit, additive focus recording with identity-bound retry receipts."""

from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import ActionReceipt, AgentEvent, AgentSuggestion
from app.models.task import Task
from app.services.agent_feedback import create_plan_delta_candidates, task_feedback_snapshot
from app.services.edit_concurrency import check_edit_precondition
from app.services.task_service import reconcile_overdue_status
from app.time import utc_now


RECORD_FOCUS_SESSION = "record_focus_session"


def record_focus_session(db: Session, task: Task, *, minutes: int, idempotency_key: str, if_match: str | None) -> Task:
    if if_match is None:
        raise HTTPException(status_code=428, detail={
            "code": "EDIT_PRECONDITION_REQUIRED", "message": "请刷新任务后再记录专注用时",
        })
    existing = db.scalar(select(AgentSuggestion).where(AgentSuggestion.idempotency_key == idempotency_key))
    if existing is not None:
        if (existing.action_type != RECORD_FOCUS_SESSION or existing.source_type != "task"
                or existing.source_id != task.id or existing.source_navigation_key != task.navigation_key
                or existing.proposed_payload.get("minutes") != minutes):
            raise HTTPException(status_code=409, detail={
                "code": "IDEMPOTENCY_KEY_CONFLICT", "message": "这条专注记录已用于另一项操作，请勿重复使用",
            })
        # A timed-out write retries the original version; a page refreshed
        # after success may instead carry the current version. Neither adds
        # the elapsed minutes twice or bypasses the immutable source identity.
        if if_match != existing.current_payload.get("request_if_match"):
            check_edit_precondition(db, task, if_match)
        return task

    check_edit_precondition(db, task, if_match)
    if task.status in {"completed", "canceled"}:
        raise HTTPException(status_code=409, detail={
            "code": "TASK_NOT_ACTIONABLE", "message": "已完成或已取消的任务需先恢复，才能继续记录专注用时",
        })
    actual_minutes = (task.actual_minutes or 0) + minutes
    if actual_minutes > 10080:
        raise HTTPException(status_code=422, detail={
            "code": "TASK_ACTUAL_MINUTES_LIMIT", "message": "累计实际用时不能超过 10080 分钟，请先核对任务记录",
        })
    now = utc_now()
    before = task_feedback_snapshot(task)
    remaining = task.remaining_minutes
    if remaining is None and task.estimated_minutes is not None:
        remaining = max(0, task.estimated_minutes - (task.actual_minutes or 0))
    task.actual_minutes = actual_minutes
    if remaining is not None:
        task.remaining_minutes = max(0, remaining - minutes)
    reconcile_overdue_status(task, now=now)
    if task.status != "overdue":
        task.status = "in_progress"
    after = task_feedback_snapshot(task)
    suggestion = AgentSuggestion(
        action_type=RECORD_FOCUS_SESSION, status="executed", source_type="task", source_id=task.id,
        source_navigation_key=task.navigation_key, source_name=task.name,
        title=f"记录“{task.name}”的专注用时", explanation="用户确认本次用时，累计记录并更新已知剩余时长。",
        reason_code="focus_session_recorded", current_payload={**before, "request_if_match": if_match},
        proposed_payload={"minutes": minutes}, risk_level="low", confidence=1.0,
        fingerprint=sha256(f"{RECORD_FOCUS_SESSION}:{task.navigation_key}:{idempotency_key}".encode()).hexdigest(),
        idempotency_key=idempotency_key, expires_at=now, created_at=now, updated_at=now,
        accepted_at=now, executed_at=now,
    )
    db.add(suggestion)
    db.flush()
    db.add(ActionReceipt(
        suggestion_id=suggestion.id, action_type=RECORD_FOCUS_SESSION, source_type="task", source_id=task.id,
        source_navigation_key=task.navigation_key, outcome="executed",
        applied_payload={"minutes": minutes, "actual_minutes": actual_minutes, "remaining_minutes": task.remaining_minutes},
        before_payload=before, after_payload=after, message=f"已记录本次专注 {minutes} 分钟，累计 {actual_minutes} 分钟",
        executed_at=now,
    ))
    db.add(AgentEvent(event_type="focus_session_recorded", entity_type="task", entity_id=task.id,
                      entity_navigation_key=task.navigation_key, suggestion_id=suggestion.id,
                      payload={"minutes": minutes, "before": before, "after": after}, created_at=now))
    create_plan_delta_candidates(db, task, "actual_minutes_changed", now=now)
    return task
