"""Read-only, bounded normalization for the learning-agent activity feed.

The persisted agent tables intentionally contain detailed internal payloads for
audit and execution.  This module is the *public projection* of that audit
trail: it never returns payload JSON, request data, paths, or exception text.
It also deliberately performs no refresh, reminder synchronization, or other
write while a user is merely reading their activity history.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, load_only

from app.models.agent import ActionReceipt, AgentEvent, AgentRun, AgentSuggestion
from app.services.source_identity import valid_navigation_key
from app.time import as_utc, utc_now


ACTIVITY_LIMIT = 50
_SUPPORTED_SOURCE_TYPES = frozenset({
    "task", "material", "study_plan", "study_plan_item", "action_receipt",
    "task_collection", "material_collection", "study_plan_collection", "capacity",
})

# These strings are product copy rather than persisted text.  In particular,
# neither a suggestion title/explanation nor an event payload becomes an API
# response because those fields can contain arbitrary historical input.
_SUGGESTION_ACTIONS: dict[str, str] = {
    "adjust_priority": "任务优先级调整建议",
    "set_task_estimate": "任务预计时长补充建议",
    "start_task": "任务开始建议",
    "apply_plan_delta": "复习计划调整建议",
    "complete_task": "任务完成反馈",
    "reset_course_calibration": "课程估时校准重置",
}
_EVENTS: dict[str, tuple[str, str, str, str]] = {
    "suggestion_created": ("suggestion_generated", "generated", "智能体建议已生成", "已生成一项需要人工确认的建议。"),
    "suggestion_accepted": ("suggestion_confirmed", "confirmed", "智能体建议已确认", "已确认该建议，正在按受控流程执行。"),
    "suggestion_executed": ("suggestion_executed", "executed", "智能体建议已执行", "该建议已完成受控执行并保留执行回执。"),
    "suggestion_failed": ("suggestion_failed", "failed", "智能体建议执行失败", "该建议未完成执行，未将内部错误信息展示在活动记录中。"),
    "suggestion_expired": ("suggestion_expired", "expired", "智能体建议已过期", "关联状态已变化或有效期已结束，建议不再执行。"),
    "suggestion_dismissed": ("suggestion_ignored", "ignored", "智能体建议已忽略", "该建议已被用户忽略，不会自动执行。"),
    "plan_delta_created": ("suggestion_generated", "generated", "复习计划调整建议已生成", "检测到可复核的计划变化，等待人工确认。"),
    "plan_delta_accepted": ("suggestion_confirmed", "confirmed", "复习计划调整已确认", "已确认该计划调整，正在按受控流程执行。"),
    "plan_delta_executed": ("suggestion_executed", "executed", "复习计划调整已执行", "计划调整已完成并保留执行回执。"),
    "plan_delta_expired": ("suggestion_expired", "expired", "复习计划调整已过期", "关联任务或计划已变化，原调整不再执行。"),
    "material_extraction_confirmed": (
        "material_extraction_confirmed", "recorded", "资料抽取已确认",
        "已确认资料抽取结果，并创建正式 DDL 任务。",
    ),
    "task_completed": ("task_recorded", "recorded", "任务完成已记录", "已记录任务完成状态，相关调整仍需单独确认。"),
    "task_feedback_updated": ("task_recorded", "recorded", "任务完成反馈已更新", "已记录用户主动提供的完成反馈。"),
    "task_overdue": ("task_recorded", "recorded", "任务逾期状态已记录", "已记录任务逾期状态，可在关联任务中继续处理。"),
    "actual_minutes_changed": ("task_recorded", "recorded", "实际用时已更新", "已记录任务实际用时变化。"),
    "plan_delta_evaluated": ("evaluation_recorded", "recorded", "计划差异已评估", "已完成受限的计划差异评估，未自动修改计划。"),
    "calibration_reset": ("calibration_recorded", "executed", "课程估时校准已重置", "已重置用于估时的校准窗口，历史任务记录未删除。"),
    "reminder_dismissed": ("reminder_ignored", "ignored", "学习提醒已忽略", "该提醒已被用户忽略。"),
}
_SUGGESTION_STATUS: dict[str, tuple[str, str, str]] = {
    "pending": ("suggestion_generated", "generated", "等待人工确认，不会自动执行。"),
    "accepted": ("suggestion_confirmed", "confirmed", "已确认，等待或正在按受控流程执行。"),
    "executed": ("suggestion_executed", "executed", "已完成受控执行。"),
    "failed": ("suggestion_failed", "failed", "未完成执行，未展示内部错误信息。"),
    "dismissed": ("suggestion_ignored", "ignored", "已被用户忽略，不会自动执行。"),
    "expired": ("suggestion_expired", "expired", "关联状态变化或有效期结束，已不再执行。"),
}


def _source(source_type: str | None, source_id: int | None, navigation_key: str | None = None) -> dict[str, Any]:
    """Return only a resolver-compatible source identity or an explicit gap."""

    if source_type in _SUPPORTED_SOURCE_TYPES and isinstance(source_id, int) and source_id > 0 and valid_navigation_key(navigation_key):
        return {
            "status": "available",
            "source_ref": {"source_type": source_type, "source_id": source_id, "navigation_key": navigation_key},
            "message": "可使用站内证据导航查看关联来源。",
        }
    return {
        "status": "unavailable",
        "source_ref": None,
        "message": "该历史记录没有可安全跳转的站内来源。",
    }


def _item(*, activity_id: str, kind: str, event: str, status: str, occurred_at: datetime,
          title: str, description: str, source: dict[str, Any], suggestion_id: int | None = None,
          receipt_id: int | None = None, run_id: int | None = None) -> dict[str, Any]:
    return {
        "activity_id": activity_id,
        "kind": kind,
        "event": event,
        "status": status,
        "occurred_at": occurred_at,
        "title": title,
        "description": description,
        "source": source,
        "suggestion_id": suggestion_id,
        "receipt_id": receipt_id,
        "run_id": run_id,
    }


def _suggestion_time(row: AgentSuggestion) -> datetime:
    if row.status == "executed" and row.executed_at is not None:
        return row.executed_at
    if row.status == "accepted" and row.accepted_at is not None:
        return row.accepted_at
    if row.status == "dismissed" and row.dismissed_at is not None:
        return row.dismissed_at
    return row.updated_at or row.created_at


def _event_row(row: AgentEvent, receipts_by_suggestion: dict[int, ActionReceipt]) -> dict[str, Any]:
    mapped = _EVENTS.get(row.event_type)
    if mapped is None:
        return _item(
            activity_id=f"event:{row.id}", kind="event", event="unavailable", status="unavailable",
            occurred_at=row.created_at, title="未识别的智能体记录",
            description="该历史记录格式当前无法安全展示具体内容。",
            source=_source(None, None), suggestion_id=row.suggestion_id, run_id=row.run_id,
        )
    event, status, title, description = mapped
    receipt = receipts_by_suggestion.get(row.suggestion_id) if row.suggestion_id is not None else None
    source = _source("action_receipt", receipt.id, receipt.navigation_key) if receipt is not None else _source(row.entity_type, row.entity_id, row.entity_navigation_key)
    return _item(
        activity_id=f"event:{row.id}", kind="event", event=event, status=status,
        occurred_at=row.created_at, title=title, description=description, source=source,
        suggestion_id=row.suggestion_id, receipt_id=receipt.id if receipt is not None else None, run_id=row.run_id,
    )


def _suggestion_row(row: AgentSuggestion, receipts_by_suggestion: dict[int, ActionReceipt]) -> dict[str, Any]:
    event, status, description = _SUGGESTION_STATUS.get(
        row.status, ("unavailable", "unavailable", "该建议状态当前无法安全展示。")
    )
    action_title = _SUGGESTION_ACTIONS.get(row.action_type, "智能体建议")
    receipt = receipts_by_suggestion.get(row.id)
    source = _source("action_receipt", receipt.id, receipt.navigation_key) if receipt is not None else _source(row.source_type, row.source_id, row.source_navigation_key)
    return _item(
        activity_id=f"suggestion:{row.id}", kind="suggestion", event=event, status=status,
        occurred_at=_suggestion_time(row), title=action_title, description=description, source=source,
        suggestion_id=row.id, receipt_id=receipt.id if receipt is not None else None, run_id=row.run_id,
    )


def _receipt_row(row: ActionReceipt) -> dict[str, Any]:
    action_title = _SUGGESTION_ACTIONS.get(row.action_type, "智能体操作")
    status = "executed" if row.outcome == "executed" else ("failed" if row.outcome == "failed" else "recorded")
    return _item(
        activity_id=f"receipt:{row.id}", kind="receipt", event="execution_receipt", status=status,
        occurred_at=row.executed_at, title=f"{action_title}执行回执",
        description="已保留受控执行回执；活动时间线不展示回执内部参数。",
        source=_source("action_receipt", row.id, row.navigation_key), suggestion_id=row.suggestion_id, receipt_id=row.id,
    )


def _run_row(row: AgentRun) -> dict[str, Any]:
    status = "completed" if row.status == "completed" else ("failed" if row.status == "failed" else "recorded")
    return _item(
        activity_id=f"run:{row.id}", kind="run", event="run_completed" if status == "completed" else "run_recorded",
        status=status, occurred_at=row.completed_at or row.created_at,
        title="智能体规则评估已完成" if status == "completed" else "智能体规则评估记录",
        description="已记录一次受限规则评估；活动时间线不展示内部输入快照。",
        source=_source(None, None), run_id=row.id,
    )


def build_activity(db: Session, *, limit: int = ACTIVITY_LIMIT) -> dict[str, Any]:
    """Build the newest bounded public activity projection without writes."""

    # Reading the newest 50 candidates from every source is sufficient for a
    # globally newest-50 merge: an omitted row has at least 50 newer rows in
    # its own source table.  Keep these ORM entities deliberately partial:
    # persisted payloads contain audit/execution detail which this projection
    # neither returns nor needs to read.  ``raiseload`` turns an accidental
    # future access to a deferred column into a local error instead of issuing
    # a hidden secondary SELECT for sensitive data.
    events = list(db.scalars(
        select(AgentEvent)
        .options(load_only(
            AgentEvent.id, AgentEvent.event_type, AgentEvent.entity_type,
            AgentEvent.entity_id, AgentEvent.entity_navigation_key, AgentEvent.run_id, AgentEvent.suggestion_id,
            AgentEvent.created_at, raiseload=True,
        ))
        .order_by(AgentEvent.created_at.desc(), AgentEvent.id.desc())
        .limit(ACTIVITY_LIMIT)
    ))
    suggestions = list(db.scalars(
        select(AgentSuggestion)
        .options(load_only(
            AgentSuggestion.id, AgentSuggestion.action_type, AgentSuggestion.status,
            AgentSuggestion.source_type, AgentSuggestion.source_id, AgentSuggestion.source_navigation_key, AgentSuggestion.run_id,
            AgentSuggestion.created_at, AgentSuggestion.updated_at,
            AgentSuggestion.accepted_at, AgentSuggestion.executed_at,
            AgentSuggestion.dismissed_at, raiseload=True,
        ))
        .order_by(AgentSuggestion.updated_at.desc(), AgentSuggestion.id.desc())
        .limit(ACTIVITY_LIMIT)
    ))
    receipts = list(db.scalars(
        select(ActionReceipt)
        .options(load_only(
            ActionReceipt.id, ActionReceipt.navigation_key, ActionReceipt.suggestion_id, ActionReceipt.action_type,
            ActionReceipt.outcome, ActionReceipt.executed_at, raiseload=True,
        ))
        .order_by(ActionReceipt.executed_at.desc(), ActionReceipt.id.desc())
        .limit(ACTIVITY_LIMIT)
    ))
    runs = list(db.scalars(
        select(AgentRun)
        .options(load_only(
            AgentRun.id, AgentRun.status, AgentRun.created_at, AgentRun.completed_at,
            raiseload=True,
        ))
        .order_by(AgentRun.completed_at.desc(), AgentRun.id.desc())
        .limit(ACTIVITY_LIMIT)
    ))
    receipts_by_suggestion = {row.suggestion_id: row for row in receipts}
    linked_suggestion_ids = {
        row.suggestion_id for row in events if row.suggestion_id is not None
    } | {row.id for row in suggestions}
    if linked_suggestion_ids:
        # An event can be more recent than its receipt.  Resolve that
        # relationship for the activity item even when the old receipt itself
        # is outside the separate newest-50 receipt slice.
        linked_receipts = db.scalars(
            select(ActionReceipt)
            .options(load_only(
                ActionReceipt.id, ActionReceipt.navigation_key, ActionReceipt.suggestion_id, ActionReceipt.action_type,
                ActionReceipt.outcome, ActionReceipt.executed_at, raiseload=True,
            ))
            .where(ActionReceipt.suggestion_id.in_(linked_suggestion_ids))
        )
        receipts_by_suggestion.update({row.suggestion_id: row for row in linked_receipts})

    items = [*(_event_row(row, receipts_by_suggestion) for row in events),
             *(_suggestion_row(row, receipts_by_suggestion) for row in suggestions),
             *(_receipt_row(row) for row in receipts), *(_run_row(row) for row in runs)]
    kind_rank = {"event": 0, "receipt": 1, "suggestion": 2, "run": 3}
    items.sort(key=lambda row: (as_utc(row["occurred_at"]), -kind_rank[row["kind"]], row["activity_id"]), reverse=True)
    return {
        "items": items[:limit],
        "limit": limit,
        "generated_at": utc_now(),
        "calculation_basis": {
            "ordering": "occurred_at descending, then stable activity identity",
            "scope": "agent events, suggestions, action receipts, and runs; newest bounded public projection",
            "safety": "payloads, input snapshots, storage paths, and internal exceptions are never returned",
            "read_only": True,
        },
    }
