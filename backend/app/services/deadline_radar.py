"""Evidence-bound notice change detection and seven-day pressure previews."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import ActionReceipt, AgentEvent, AgentSuggestion
from app.models.task import Task
from app.schemas.deadline_radar import DeadlineRadarPreviewRead
from app.services.agent_feedback import create_plan_delta_candidates, task_feedback_snapshot
from app.services.llm_provider import parse_deadline_text
from app.services.study_preferences import build_capacity, build_capacity_with_overrides
from app.time import as_local, as_utc, deadline_to_utc, utc_now


UPDATE_DEADLINE_FROM_NOTICE = "update_deadline_from_notice"
CANCEL_TASK_FROM_NOTICE = "cancel_task_from_notice"

_RESCHEDULE_MARKER = re.compile(
    r"提前(?:到|至|为)?|延(?:期|后|长)(?:到|至|为)?|顺延(?:到|至|为)?|"
    r"(?:截止(?:日期|时间)?|提交(?:日期|时间)?)?\s*(?:改|调整)(?:到|至|为)",
    re.IGNORECASE,
)
_CANCEL_MARKER = re.compile(
    r"(?:取消|作废|撤销|不再(?:需要|要求)?|无需|不用|停止)"
    r"[^，。；;！？\r\n]{0,36}(?:提交|上传|填写|登记|作业|任务|报告|签到|报名)"
    r"|(?:提交|上传|填写|登记|作业|任务|报告|签到|报名)"
    r"[^，。；;！？\r\n]{0,36}(?:取消|作废|撤销|无需|不用)",
    re.IGNORECASE,
)
class DeadlineRadarError(ValueError):
    def __init__(self, code: str, message: str, *, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class DetectedDeadlineChange:
    intent: str
    marker: str
    quote: str
    detected_due_at: datetime | None
    warnings: list[str]
    notice_digest: str


def notice_digest(value: str) -> str:
    return sha256(value.strip().encode("utf-8")).hexdigest()


def detect_deadline_change(notice_text: str, *, reference_time: datetime) -> DetectedDeadlineChange:
    text = notice_text.strip()
    cancel_matches = list(_CANCEL_MARKER.finditer(text))
    reschedule_matches = list(_RESCHEDULE_MARKER.finditer(text))
    if cancel_matches and reschedule_matches:
        raise DeadlineRadarError(
            "DEADLINE_CHANGE_AMBIGUOUS",
            "通知同时包含取消和改期表达，请拆成一条明确通知后再预览。",
        )
    if not cancel_matches and not reschedule_matches:
        raise DeadlineRadarError(
            "DEADLINE_CHANGE_NOT_FOUND",
            "没有找到明确的提前、延期、改期或取消表达；本功能不会把普通日期自动覆盖到已有任务。",
        )

    digest = notice_digest(text)
    if cancel_matches:
        marker = cancel_matches[-1]
        return DetectedDeadlineChange(
            intent="cancel",
            marker=marker.group(0)[:24],
            quote=_evidence_quote(text, marker.start(), marker.end()),
            detected_due_at=None,
            warnings=[],
            notice_digest=digest,
        )

    marker = reschedule_matches[-1]
    source_after_marker = text[marker.start():]
    local_reference = as_local(reference_time).replace(tzinfo=None)
    detected, warnings = parse_deadline_text(source_after_marker, local_reference)
    if detected is None:
        raise DeadlineRadarError(
            "DEADLINE_CHANGE_DATE_UNCLEAR",
            "识别到改期表达，但新截止时间无法唯一确认；请保留明确日期和时间后重试。",
        )
    detected_utc = deadline_to_utc(detected)
    return DetectedDeadlineChange(
        intent="reschedule",
        marker=marker.group(0)[:24],
        quote=_evidence_quote(text, marker.start(), len(text)),
        detected_due_at=detected_utc,
        warnings=list(dict.fromkeys(warnings))[:10],
        notice_digest=digest,
    )


def build_deadline_radar_preview(
    db: Session,
    task: Task,
    notice_text: str,
    *,
    reference_time: datetime | None = None,
) -> DeadlineRadarPreviewRead:
    evaluated_at = as_utc(reference_time) if reference_time is not None else utc_now()
    if task.status in {"completed", "canceled"}:
        raise DeadlineRadarError(
            "TASK_NOT_ACTIONABLE",
            "已完成或已取消的任务不能直接应用通知变更；请先在任务页核对状态。",
            status_code=409,
        )

    detected = detect_deadline_change(notice_text, reference_time=evaluated_at)
    if detected.intent == "reschedule" and task.due_at is not None and detected.detected_due_at == as_utc(task.due_at):
        raise DeadlineRadarError(
            "DEADLINE_CHANGE_NO_EFFECT",
            "识别出的截止时间与当前任务相同，没有需要执行的变更。",
        )

    before = build_capacity(db, evaluated_at=evaluated_at)
    if detected.intent == "cancel":
        after = build_capacity_with_overrides(
            db,
            evaluated_at=evaluated_at,
            excluded_task_ids={task.id},
        )
        proposed_due_at = None
    else:
        after = build_capacity_with_overrides(
            db,
            evaluated_at=evaluated_at,
            due_at_overrides={task.id: detected.detected_due_at},
        )
        proposed_due_at = detected.detected_due_at

    pressure_days = _pressure_days(before, after, evaluated_at=evaluated_at)
    direction, day_shift = _direction(task.due_at, proposed_due_at, detected.intent)
    overload_delta = sum(
        day["after_overload_minutes"] - day["before_overload_minutes"]
        for day in pressure_days
    )
    summary = _impact_summary(
        task=task,
        direction=direction,
        day_shift=day_shift,
        before=before,
        after=after,
        overload_delta=overload_delta,
    )
    return DeadlineRadarPreviewRead(
        generated_at=evaluated_at,
        intent=detected.intent,
        task={
            "id": task.id,
            "navigation_key": task.navigation_key,
            "revision": task.revision,
            "name": task.name,
            "status": task.status,
            "current_due_at": as_utc(task.due_at) if task.due_at is not None else None,
            "proposed_due_at": proposed_due_at,
        },
        evidence={
            "quote": detected.quote,
            "marker": detected.marker,
            "detected_due_at": detected.detected_due_at,
            "warnings": detected.warnings,
        },
        pressure_days=pressure_days,
        impact={
            "direction": direction,
            "day_shift": day_shift,
            "before_risk": before.risk_level,
            "after_risk": after.risk_level,
            "before_known_minutes": before.known_workload_minutes,
            "after_known_minutes": after.known_workload_minutes,
            "overload_delta_minutes": overload_delta,
            "summary": summary,
        },
        action_label="确认取消任务" if detected.intent == "cancel" else "确认更新截止时间",
        calculation_basis={
            "timezone": "Asia/Shanghai",
            "window": "从同一评估时刻起的未来 7 天",
            "task_binding": "由用户选择任务，并校验不可复用身份与版本",
            "workload_formula": "remaining_minutes ?? estimated_minutes；缺失估时不补造分钟数",
            "capacity_formula": "min(每周可用时间, 每日上限 × 7) × (1 - 缓冲比例)",
            "execution_boundary": "预览不修改任务；确认时服务端重新解析通知并再次校验任务版本",
        },
    )


def find_idempotent_result(
    db: Session,
    *,
    idempotency_key: str,
    task_id: int,
    digest: str,
) -> AgentSuggestion | None:
    existing = db.scalar(select(AgentSuggestion).where(AgentSuggestion.idempotency_key == idempotency_key))
    if existing is None:
        return None
    if (
        existing.action_type not in {UPDATE_DEADLINE_FROM_NOTICE, CANCEL_TASK_FROM_NOTICE}
        or existing.source_id != task_id
        or existing.current_payload.get("notice_digest") != digest
    ):
        raise DeadlineRadarError(
            "IDEMPOTENCY_KEY_CONFLICT",
            "该幂等键已用于另一项操作。",
            status_code=409,
        )
    return existing


def execute_deadline_change(
    db: Session,
    task: Task,
    preview: DeadlineRadarPreviewRead,
    *,
    notice_text: str,
    idempotency_key: str,
) -> tuple[Task, ActionReceipt, int]:
    now = utc_now()
    before = _task_snapshot(task)
    if preview.intent == "cancel":
        task.status = "canceled"
        task.remaining_minutes = 0
        task.completed_at = None
        action_type = CANCEL_TASK_FROM_NOTICE
        trigger = "task_canceled"
        message = f"已取消任务“{task.name}”，原任务与通知变更回执继续保留。"
    else:
        task.due_at = preview.task.proposed_due_at
        if task.due_at is not None and as_utc(task.due_at) <= now:
            task.status = "overdue"
        elif task.status == "overdue":
            task.status = "not_started"
        action_type = UPDATE_DEADLINE_FROM_NOTICE
        trigger = "deadline_changed"
        message = f"已更新任务“{task.name}”的截止时间，并重新评估未来 7 天压力。"

    db.flush()
    after = _task_snapshot(task)
    digest = notice_digest(notice_text)
    fingerprint = sha256(json.dumps({
        "action_type": action_type,
        "navigation_key": task.navigation_key,
        "before_revision": before["revision"],
        "notice_digest": digest,
    }, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    suggestion = AgentSuggestion(
        action_type=action_type,
        status="executed",
        source_type="task",
        source_id=task.id,
        source_navigation_key=task.navigation_key,
        source_name=task.name,
        title="取消已有 DDL" if preview.intent == "cancel" else "更新已有 DDL 截止时间",
        explanation=preview.impact.summary,
        reason_code="notice_task_canceled" if preview.intent == "cancel" else "notice_deadline_changed",
        current_payload={
            "task": before,
            "notice_digest": digest,
            "notice_quote": preview.evidence.quote,
            "change_marker": preview.evidence.marker,
        },
        proposed_payload={
            "task": after,
            "intent": preview.intent,
            "impact_summary": preview.impact.summary,
            "overload_delta_minutes": preview.impact.overload_delta_minutes,
        },
        risk_level=preview.impact.after_risk,
        confidence=0.9,
        expires_at=now,
        fingerprint=fingerprint,
        idempotency_key=idempotency_key,
        created_at=now,
        updated_at=now,
        accepted_at=now,
        executed_at=now,
    )
    db.add(suggestion)
    db.flush()
    plan_deltas = create_plan_delta_candidates(db, task, trigger, now=now)
    receipt = ActionReceipt(
        suggestion_id=suggestion.id,
        action_type=action_type,
        source_type="task",
        source_id=task.id,
        source_navigation_key=task.navigation_key,
        outcome="executed",
        applied_payload={
            "intent": preview.intent,
            "due_at": after["due_at"],
            "status": after["status"],
            "plan_delta_count": len(plan_deltas),
        },
        before_payload=before,
        after_payload=after,
        message=message,
        executed_at=now,
    )
    db.add(receipt)
    db.flush()
    db.add(AgentEvent(
        event_type="deadline_change_executed",
        entity_type="task",
        entity_id=task.id,
        entity_navigation_key=task.navigation_key,
        suggestion_id=suggestion.id,
        payload={
            "intent": preview.intent,
            "notice_digest": digest,
            "plan_delta_count": len(plan_deltas),
        },
        created_at=now,
    ))
    return task, receipt, len(plan_deltas)


def _task_snapshot(task: Task) -> dict[str, Any]:
    snapshot = task_feedback_snapshot(task)
    snapshot.update({
        "id": task.id,
        "navigation_key": task.navigation_key,
        "revision": task.revision,
        "name": task.name,
        "due_at": as_utc(task.due_at).isoformat() if task.due_at is not None else None,
        "remaining_minutes": task.remaining_minutes,
        "estimated_minutes": task.estimated_minutes,
    })
    return snapshot


def _evidence_quote(text: str, start: int, end: int) -> str:
    if len(text) <= 360:
        return text
    left = max(0, start - 100)
    right = min(len(text), max(end, start + 240))
    quote = text[left:right].strip()
    if left:
        quote = f"…{quote}"
    if right < len(text):
        quote = f"{quote}…"
    return quote[:360]


def _direction(current: datetime | None, proposed: datetime | None, intent: str) -> tuple[str, int | None]:
    if intent == "cancel":
        return "removed", None
    if current is None:
        return "new_deadline", None
    current_local = as_local(current).date()
    proposed_local = as_local(proposed).date() if proposed is not None else current_local
    shift = (proposed_local - current_local).days
    return ("earlier" if as_utc(proposed) < as_utc(current) else "later"), shift


def _pressure_days(before, after, *, evaluated_at: datetime) -> list[dict[str, Any]]:
    before_groups = {item.local_date: item for item in before.daily_risk_groups}
    after_groups = {item.local_date: item for item in after.daily_risk_groups}
    daily_capacity = before.calculation_basis.effective_daily_capacity_minutes
    first_day = as_local(evaluated_at).date()
    result = []
    for offset in range(7):
        local_date = first_day + timedelta(days=offset)
        key = local_date.isoformat()
        old = before_groups.get(key)
        new = after_groups.get(key)
        old_minutes = old.known_workload_minutes if old else 0
        new_minutes = new.known_workload_minutes if new else 0
        old_count = len(old.task_ids) if old else 0
        new_count = len(new.task_ids) if new else 0
        old_overload = old.overload_minutes if old else 0
        new_overload = new.overload_minutes if new else 0
        old_risk = old.risk_level if old else "low"
        new_risk = new.risk_level if new else "low"
        result.append({
            "local_date": local_date,
            "effective_capacity_minutes": daily_capacity,
            "before_minutes": old_minutes,
            "after_minutes": new_minutes,
            "before_overload_minutes": old_overload,
            "after_overload_minutes": new_overload,
            "before_risk": old_risk,
            "after_risk": new_risk,
            "before_task_count": old_count,
            "after_task_count": new_count,
            "affected": (old_minutes, old_count, old_risk) != (new_minutes, new_count, new_risk),
        })
    return result


def _impact_summary(*, task: Task, direction: str, day_shift: int | None, before, after, overload_delta: int) -> str:
    if direction == "removed":
        reduced = max(0, before.known_workload_minutes - after.known_workload_minutes)
        if reduced:
            return f"取消“{task.name}”后，未来 7 天已知负荷减少 {reduced} 分钟；确认前不会修改任务。"
        return f"取消“{task.name}”后，该任务会退出未来 7 天压力计算；其估时缺失时不补造分钟数。"
    if direction == "new_deadline":
        lead = "新增截止时间后"
    else:
        magnitude = abs(day_shift or 0)
        lead = f"截止时间{'提前' if direction == 'earlier' else '延后'} {magnitude} 天后"
    risk_change = "整体风险不变"
    if before.risk_level != after.risk_level:
        risk_change = f"整体风险由 {before.risk_level} 变为 {after.risk_level}"
    if overload_delta > 0:
        return f"{lead}，{risk_change}，七日逐日超载增加 {overload_delta} 分钟。"
    if overload_delta < 0:
        return f"{lead}，{risk_change}，七日逐日超载减少 {abs(overload_delta)} 分钟。"
    return f"{lead}，{risk_change}，当前没有新增可确认的逐日超载分钟数。"
