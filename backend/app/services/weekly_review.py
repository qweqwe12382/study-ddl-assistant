"""Bounded, local-only weekly review and durable in-app reminder rules.

The review deliberately does not infer time a student did not provide.  Every
aggregate carries its source rows and a calculation basis, while missing or
insufficient evidence remains ``unknown``/``partial`` instead of becoming a
precise-looking score.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from hashlib import sha256
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import ActionReceipt, AgentReminder, AgentSuggestion
from app.models.material import Material
from app.models.study_plan import StudyPlan
from app.models.task import Task
from app.services.agent import ADJUST_PRIORITY, SET_TASK_ESTIMATE, START_TASK, is_action_candidate
from app.services.study_plan import decode_plan_content
from app.services.study_preferences import build_capacity
from app.time import LOCAL_TIMEZONE, as_local, as_utc, utc_now


MAX_SOURCE_REFS = 50
MAX_NEXT_WEEK_ACTIONS = 3
RISK_ORDER = {"high": 0, "medium": 1, "low": 2}


def weekly_window(evaluated_at: datetime) -> tuple[datetime, datetime]:
    """Return an explicit seven China-local-calendar-day half-open window."""

    local_now = as_local(evaluated_at)
    window_start = datetime.combine(local_now.date() - timedelta(days=6), time.min, tzinfo=LOCAL_TIMEZONE)
    window_end = datetime.combine(local_now.date() + timedelta(days=1), time.min, tzinfo=LOCAL_TIMEZONE)
    return window_start.astimezone(evaluated_at.tzinfo), window_end.astimezone(evaluated_at.tzinfo)


def _ref(source_type: str, source_id: int | str, source_name: str | None = None, *, navigation_key: str | None = None, **snapshot: Any) -> dict[str, Any]:
    return {"source_type": source_type, "source_id": source_id, "source_name": source_name, "navigation_key": navigation_key, "snapshot": snapshot}


def _metric(
    *, count: int, known_count: int, unknown_count: int, value: int | float | None,
    refs: list[dict[str, Any]], basis: dict[str, Any], sample_count: int | None = None,
    missing_count: int | None = None, direction: str | None = None,
    empty_is_known: bool = False,
) -> dict[str, Any]:
    has_known_evidence = known_count > 0 or (empty_is_known and unknown_count == 0)
    status = "unknown" if not has_known_evidence else ("partial" if unknown_count else "known")
    return {
        "count": count, "known_count": known_count, "unknown_count": unknown_count,
        # A zero count is not evidence of a zero value. This is particularly
        # important for historical rows that predate completed_at/feedback.
        "value": value if has_known_evidence else None, "status": status,
        "sample_count": sample_count, "missing_count": missing_count, "direction": direction,
        "source_refs": refs[:MAX_SOURCE_REFS], "calculation_basis": basis,
    }


def _in_window(value: datetime | None, start: datetime, end: datetime) -> bool:
    return value is not None and start <= as_utc(value) < end


def _pending_executable_actions(db: Session, now: datetime) -> list[dict[str, Any]]:
    """Project only existing server candidates; never invent a new command."""

    actions: list[dict[str, Any]] = []
    suggestions = db.scalars(
        select(AgentSuggestion).where(
            AgentSuggestion.status == "pending",
            AgentSuggestion.action_type.in_((ADJUST_PRIORITY, SET_TASK_ESTIMATE, START_TASK)),
        ).order_by(AgentSuggestion.expires_at.asc(), AgentSuggestion.id.asc())
    ).all()
    for suggestion in suggestions:
        task = db.get(Task, suggestion.source_id)
        if task is None or task.navigation_key != suggestion.source_navigation_key or as_utc(suggestion.expires_at) <= now or not is_action_candidate(task, suggestion.action_type, now):
            continue
        actions.append({
            "action_type": suggestion.action_type, "target_type": "task", "target_id": task.id,
            "title": suggestion.title, "explanation": suggestion.explanation, "reason_code": suggestion.reason_code,
            "risk_level": suggestion.risk_level if suggestion.risk_level in RISK_ORDER else "low",
            "execution_mode": "accept", "suggestion_id": suggestion.id,
            "source_refs": [_ref("task", task.id, task.name, navigation_key=task.navigation_key, due_at=as_utc(task.due_at).isoformat() if task.due_at else None,
                                  status=task.status)],
        })
    return actions


def build_weekly_review(db: Session, *, evaluated_at: datetime | None = None) -> dict[str, Any]:
    """Build a traceable seven-day snapshot from local persisted data only."""

    now = as_utc(evaluated_at or utc_now())
    window_start, window_end = weekly_window(now)
    window_start_local = as_local(window_start).date()
    window_end_local = as_local(window_end).date()

    completed_rows = list(db.scalars(select(Task).where(Task.status == "completed").order_by(Task.id.asc())).all())
    completed = [task for task in completed_rows if _in_window(task.completed_at, window_start, window_end)]
    completed_unknown = [task for task in completed_rows if task.completed_at is None]
    completed_refs = [_ref("task", task.id, task.name, navigation_key=task.navigation_key, completed_at=as_utc(task.completed_at).isoformat(),
                           estimated_minutes=task.estimated_minutes, actual_minutes=task.actual_minutes)
                      for task in completed]

    paired = [task for task in completed if task.actual_minutes is not None and task.estimated_minutes is not None]
    unknown_variance = len(completed) - len(paired)
    total_variance = sum(task.actual_minutes - task.estimated_minutes for task in paired)
    estimate_variance = _metric(
        count=len(completed), known_count=len(paired), unknown_count=unknown_variance,
        value=total_variance if paired else None,
        refs=[_ref("task", task.id, task.name, navigation_key=task.navigation_key, estimated_minutes=task.estimated_minutes,
                   actual_minutes=task.actual_minutes, variance_minutes=task.actual_minutes - task.estimated_minutes)
              for task in paired],
        basis={"formula": "sum(actual_minutes - estimated_minutes)", "unit": "minutes",
               "completed_task_window": "[window_start, window_end)"},
        sample_count=len(paired), missing_count=unknown_variance,
        direction="overrun" if total_variance > 0 else ("underrun" if total_variance < 0 else "balanced") if paired else None,
    )

    overdue = []
    for task in db.scalars(select(Task).where(Task.due_at.is_not(None)).order_by(Task.due_at.asc(), Task.id.asc())).all():
        due_at = as_utc(task.due_at)
        # Open tasks are late now; a completed task is late only if it was
        # completed after its deadline. Both must have a deadline in this week.
        if task.status not in {"completed", "canceled"}:
            is_late = due_at < now and window_start <= due_at < window_end
        else:
            # A late completion belongs to the review period of the completion
            # event, not indefinitely to the older deadline's calendar week.
            is_late = (
                task.completed_at is not None
                and as_utc(task.completed_at) > due_at
                and window_start <= as_utc(task.completed_at) < window_end
            )
        if is_late:
            overdue.append(task)
    overdue_refs = [_ref("task", task.id, task.name, navigation_key=task.navigation_key, due_at=as_utc(task.due_at).isoformat(), status=task.status,
                         completed_at=as_utc(task.completed_at).isoformat() if task.completed_at else None)
                    for task in overdue]
    overdue_metric = _metric(
        count=len(overdue), known_count=len(overdue), unknown_count=0, value=len(overdue), refs=overdue_refs,
        basis={"formula": "open deadline in window and past evaluated_at, or late completion event in window", "evaluated_at": now.isoformat()},
        empty_is_known=True,
    )

    plan_total = plan_completed = plan_delayed = plan_unknown = 0
    plan_refs: list[dict[str, Any]] = []
    for plan in db.scalars(select(StudyPlan).where(StudyPlan.status == "active").order_by(StudyPlan.id.asc())).all():
        items, warnings, _materials, _tasks = decode_plan_content(plan.plan_content)
        invalid = not plan.plan_content or any("无法读取" in warning for warning in warnings)
        if invalid:
            plan_unknown += 1
            plan_refs.append(_ref("study_plan", plan.id, plan.title, navigation_key=plan.navigation_key, reason="plan_content_unreadable"))
            continue
        for item in items:
            if not (window_start_local <= item.date < window_end_local):
                continue
            plan_total += 1
            delayed = item.status != "completed" and item.date < as_local(now).date()
            if item.status == "completed":
                plan_completed += 1
            if delayed:
                plan_delayed += 1
            plan_refs.append(_ref("study_plan_item", f"{plan.id}:{item.id}", item.title, navigation_key=item.navigation_key,
                                  plan_id=plan.id, date=item.date.isoformat(), status=item.status, delayed=delayed))
    plan_item_status = _metric(
        count=plan_total, known_count=plan_total if plan_total else 0, unknown_count=plan_unknown,
        value=plan_completed if plan_total else None, refs=plan_refs,
        basis={"formula": "current statuses of plan items whose scheduled dates fall in seven China-local dates; items have no completed_at",
               "scheduled_item_count": plan_total, "current_completed_item_count": plan_completed,
               "current_delayed_item_count": plan_delayed},
    )

    review_materials = list(db.scalars(select(Material).where(Material.extraction_status == "needs_review").order_by(Material.id.asc())).all())
    failed_materials = list(db.scalars(select(Material).where(
        (Material.extraction_status == "failed") | (Material.processing_status == "failed")
    ).distinct().order_by(Material.id.asc())).all())
    def material_metric(rows: list[Material], reason: str) -> dict[str, Any]:
        return _metric(
            count=len(rows), known_count=len(rows), unknown_count=0, value=len(rows),
            refs=[_ref("material", row.id, row.original_filename, navigation_key=row.navigation_key, extraction_status=row.extraction_status,
                       processing_status=row.processing_status) for row in rows],
            basis={"formula": reason, "scope": "current material inbox snapshot (not a fabricated weekly history)"},
            empty_is_known=True,
        )

    receipts = [receipt for receipt in db.scalars(select(ActionReceipt).order_by(ActionReceipt.executed_at.asc(), ActionReceipt.id.asc())).all()
                if _in_window(receipt.executed_at, window_start, window_end)]
    receipt_refs = [_ref("action_receipt", receipt.id, receipt.action_type, navigation_key=receipt.navigation_key, suggestion_id=receipt.suggestion_id,
                         outcome=receipt.outcome, executed_at=as_utc(receipt.executed_at).isoformat()) for receipt in receipts]
    receipt_metric = _metric(
        count=len(receipts), known_count=len(receipts), unknown_count=0, value=len(receipts), refs=receipt_refs,
        basis={"formula": "persisted action_receipts.executed_at in [window_start, window_end)"},
        empty_is_known=True,
    )

    actions = _pending_executable_actions(db, now)
    if overdue:
        actions.append({"action_type": "review_overdue_tasks", "target_type": "task_collection", "target_id": "weekly_overdue",
                        "title": "复核近 7 天逾期任务", "explanation": "仅导航到现有任务并由用户决定后续处理。",
                        "reason_code": "weekly_overdue_tasks", "risk_level": "high", "execution_mode": "review",
                        "suggestion_id": None, "source_refs": overdue_refs})
    if plan_delayed:
        actions.append({"action_type": "review_plan_delays", "target_type": "study_plan_collection", "target_id": "weekly_plan_delays",
                        "title": "复核延期计划项", "explanation": "仅打开原计划项，不会自动覆盖人工安排。",
                        "reason_code": "weekly_plan_delays", "risk_level": "medium", "execution_mode": "review",
                        "suggestion_id": None,
                        "source_refs": [ref for ref in plan_refs if ref["snapshot"].get("delayed")][:MAX_SOURCE_REFS]})
    if review_materials or failed_materials:
        material_refs = material_metric(review_materials, "current extraction_status == needs_review")["source_refs"] + material_metric(failed_materials, "failed")["source_refs"]
        actions.append({"action_type": "review_material_inbox", "target_type": "material_collection", "target_id": "current_inbox",
                        "title": "处理待复核资料", "explanation": "只导航到资料收件箱，保留人工确认。",
                        "reason_code": "weekly_material_inbox", "risk_level": "high" if failed_materials else "medium",
                        "execution_mode": "navigate", "suggestion_id": None, "source_refs": material_refs[:MAX_SOURCE_REFS]})
    actions.sort(key=lambda item: (RISK_ORDER[item["risk_level"]], item["execution_mode"] != "accept", str(item["target_id"])))
    # Deduplicate a suggestion if its task also appears in a fixed review card.
    seen: set[tuple[str, int | str]] = set()
    bounded_actions = []
    for action in actions:
        key = (action["action_type"], action["target_id"])
        if key not in seen:
            seen.add(key)
            bounded_actions.append(action)
        if len(bounded_actions) == MAX_NEXT_WEEK_ACTIONS:
            break

    capacity = build_capacity(db, evaluated_at=now)
    capacity_snapshot = {
        "risk_level": capacity.risk_level, "known_workload_minutes": capacity.known_workload_minutes,
        "effective_capacity_minutes": capacity.effective_capacity_minutes,
        "missing_estimate_task_ids": capacity.missing_estimate_task_ids,
        "daily_risk_groups": [item.model_dump(mode="json") for item in capacity.daily_risk_groups],
        "tasks": [item.model_dump(mode="json") for item in capacity.tasks],
    }
    return {
        "window_start": window_start, "window_end": window_end, "evaluated_at": now, "timezone": "Asia/Shanghai",
        "calculation_basis": {
            "window_semantics": "seven China-local calendar days, [window_start, window_end)",
            "timezone": "Asia/Shanghai", "evaluated_at": now.isoformat(),
            "unknown_policy": "missing completed_at, actual/estimated time, or unreadable plan content remains unknown/partial",
            "capacity_snapshot": capacity_snapshot,
        },
        "completed_tasks": _metric(
            count=len(completed) + len(completed_unknown), known_count=len(completed), unknown_count=len(completed_unknown),
            value=len(completed), refs=completed_refs + [_ref("task", task.id, task.name, navigation_key=task.navigation_key, reason="completed_at_missing") for task in completed_unknown],
            basis={"formula": "status=completed with completed_at in [window_start, window_end); older rows without completed_at are unknown"},
            empty_is_known=True,
        ),
        "overdue_tasks": overdue_metric, "estimate_variance": estimate_variance, "plan_item_status": plan_item_status,
        "review_materials": material_metric(review_materials, "current extraction_status == needs_review"),
        "failed_materials": material_metric(failed_materials, "current extraction_status == failed OR processing_status == failed"),
        "execution_receipts": receipt_metric, "next_week_actions": bounded_actions,
    }


def _digest(payload: dict[str, Any]) -> str:
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _reminder_candidates(review: dict[str, Any]) -> list[dict[str, Any]]:
    """Reduce review evidence to a small, explainable set of local signals."""

    candidates = []
    rules = (
        ("weekly_overdue_tasks", "high", "task_collection", "weekly_overdue", "近 7 天存在逾期任务",
         "逾期任务仍需要人工确认下一步安排。", review["overdue_tasks"]),
        ("weekly_plan_delays", "medium", "study_plan_collection", "weekly_plan_delays", "复习计划存在延期项",
         "仅提示窗口日期内计划项的当前延期状态，不自动覆盖你的计划。", review["plan_item_status"]),
        ("materials_failed", "high", "material_collection", "failed_materials", "资料处理失败待复核",
         "资料未被自动重试或外发，请在本地资料库人工复核。", review["failed_materials"]),
        ("materials_need_review", "medium", "material_collection", "review_materials", "资料抽取待人工复核",
         "候选尚未自动写入任务，确认前请核对原文。", review["review_materials"]),
    )
    for reason, risk, source_type, source_id, title, explanation, metric in rules:
        active_count = metric["count"]
        delayed_count = metric["calculation_basis"].get("current_delayed_item_count", 0) if reason == "weekly_plan_delays" else active_count
        if not delayed_count:
            continue
        refs = metric["source_refs"]
        candidates.append({"reason_code": reason, "risk_level": risk, "source_type": source_type, "source_id": source_id,
                           "title": title, "explanation": explanation, "source_refs": refs,
                           "calculation_basis": metric["calculation_basis"],
                           # Fingerprint evidence is deliberately source-state based, not refresh-time based.
                           "fingerprint": _digest({"reason": reason, "source_type": source_type, "source_id": source_id,
                                                 "refs": refs})})
    variance = review["estimate_variance"]
    if variance["known_count"] >= 3 and variance["value"] is not None and abs(variance["value"]) >= 60:
        candidates.append({"reason_code": "estimate_variance_trend", "risk_level": "medium", "source_type": "task_collection",
                           "source_id": "weekly_estimate_variance", "title": "近 7 天估时偏差值得复盘",
                           "explanation": "仅基于同时填写预计和实际用时的任务，不会猜测缺失用时。",
                           "source_refs": variance["source_refs"], "calculation_basis": variance["calculation_basis"],
                           "fingerprint": _digest({"reason": "estimate_variance_trend", "refs": variance["source_refs"],
                                                 "value": variance["value"]})})
    capacity = review["calculation_basis"]["capacity_snapshot"]
    if capacity["risk_level"] in {"high", "medium"}:
        risk = capacity["risk_level"]
        reason = "capacity_overload" if risk == "high" else "capacity_tight"
        refs = [_ref("task", item["id"], item["name"], due_at=str(item["due_at"]),
                     counted_minutes=item["counted_minutes"], estimated_minutes=item["estimated_minutes"])
                for item in sorted(
                    # Rebuild source rows from the documented capacity snapshot rather than inventing minutes.
                    [*capacity["tasks"]], key=lambda item: (item["due_at"], item["id"])
                )]
        candidates.append({
            "reason_code": reason, "risk_level": risk, "source_type": "capacity", "source_id": "next_7_days",
            "title": "未来 7 天学习容量超载" if risk == "high" else "未来 7 天学习容量紧张",
            "explanation": "仅基于已知的剩余/预计时长；缺失估时任务不会被当作 0 分钟。",
            "source_refs": refs, "calculation_basis": capacity,
            "fingerprint": _digest({"reason": reason, "risk": risk, "known_workload": capacity["known_workload_minutes"],
                                    "effective_capacity": capacity["effective_capacity_minutes"],
                                    "missing": capacity["missing_estimate_task_ids"], "refs": refs}),
        })
    return candidates


def sync_weekly_reminders(db: Session, review: dict[str, Any], *, evaluated_at: datetime | None = None) -> list[AgentReminder]:
    """Persist current reminders once, preserve dismissal, and resolve absent ones."""

    now = as_utc(evaluated_at or review["evaluated_at"])
    candidates = _reminder_candidates(review)
    current = list(db.scalars(select(AgentReminder).order_by(AgentReminder.id.asc())).all())
    by_fingerprint = {item.fingerprint: item for item in current}
    active_fingerprints: set[str] = set()
    changed = False
    for candidate in candidates:
        active_fingerprints.add(candidate["fingerprint"])
        existing = by_fingerprint.get(candidate["fingerprint"])
        if existing is None:
            db.add(AgentReminder(**candidate, status="active", created_at=now, updated_at=now))
            changed = True
        elif existing.status == "active":
            # The fingerprint already covers content; avoid needless writes on every refresh.
            continue
        # A dismissed exact source snapshot stays dismissed. A resolved exact
        # snapshot may become active again only after it was actually cleared.
        elif existing.status == "resolved":
            existing.status = "active"
            existing.updated_at = now
            existing.dismissed_at = None
            existing.dismissal_reason = None
            changed = True
    for item in current:
        if item.status == "active" and item.fingerprint not in active_fingerprints:
            item.status = "resolved"
            item.updated_at = now
            changed = True
    if changed:
        db.commit()
    active = list(db.scalars(select(AgentReminder).where(AgentReminder.status == "active").order_by(
        AgentReminder.id.asc()
    )).all())
    return sorted(active, key=lambda item: (RISK_ORDER[item.risk_level], -item.id))
