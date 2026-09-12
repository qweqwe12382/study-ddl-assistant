"""M8.4 feedback, calibration, and explicitly-protected plan-delta rules."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from hashlib import sha256
import json
from statistics import median
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.agent import ActionReceipt, AgentEvent, AgentSuggestion
from app.models.calibration import CourseCalibrationState
from app.models.study_plan import StudyPlan
from app.models.task import Task
from app.schemas.study_plan import StudyPlanItem, PlanSourceIdentity
from app.services.study_plan import (
    decode_plan_agent_metadata,
    decode_plan_content,
    plan_content_fingerprint,
)
from app.time import as_utc, utc_now


COMPLETE_TASK = "complete_task"
APPLY_PLAN_DELTA = "apply_plan_delta"
RESET_COURSE_CALIBRATION = "reset_course_calibration"
PLAN_DELTA_ACTIONS = (APPLY_PLAN_DELTA,)
MIN_CALIBRATION_SAMPLES = 3
SAMPLE_RATIO_MIN = 0.25
SAMPLE_RATIO_MAX = 4.0
CALIBRATION_FACTOR_MIN = 0.5
CALIBRATION_FACTOR_MAX = 2.5


def task_feedback_snapshot(task: Task) -> dict[str, object]:
    return {
        "id": task.id,
        "navigation_key": task.navigation_key,
        "course_id": task.course_id,
        "name": task.name,
        "status": task.status,
        "estimated_minutes": task.estimated_minutes,
        "remaining_minutes": task.remaining_minutes,
        "actual_minutes": task.actual_minutes,
        "difficulty": task.difficulty,
        "due_at": as_utc(task.due_at).isoformat() if task.due_at else None,
        "completed_at": as_utc(task.completed_at).isoformat() if task.completed_at else None,
    }


def _digest(value: object) -> str:
    return sha256(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _calibration_samples(db: Session, course_id: int, reset_at: datetime | None) -> list[Task]:
    statement = select(Task).where(
        Task.course_id == course_id,
        Task.status == "completed",
        Task.actual_minutes.is_not(None),
        Task.estimated_minutes.is_not(None),
        Task.estimated_minutes > 0,
        Task.completed_at.is_not(None),
    ).order_by(Task.completed_at.asc(), Task.id.asc())
    rows = list(db.scalars(statement).all())
    if reset_at is not None:
        rows = [task for task in rows if as_utc(task.completed_at) > as_utc(reset_at)]
    return rows


def calibration_payload(db: Session, course_id: int) -> dict[str, Any]:
    state = db.scalar(select(CourseCalibrationState).where(CourseCalibrationState.course_id == course_id))
    reset_at = state.reset_at if state else None
    samples = _calibration_samples(db, course_id, reset_at)
    ratios = [max(SAMPLE_RATIO_MIN, min(SAMPLE_RATIO_MAX, task.actual_minutes / task.estimated_minutes)) for task in samples]
    raw_median = float(median(ratios)) if ratios else None
    factor = (
        round(max(CALIBRATION_FACTOR_MIN, min(CALIBRATION_FACTOR_MAX, raw_median)), 3)
        if len(samples) >= MIN_CALIBRATION_SAMPLES and raw_median is not None else None
    )
    difficulty_values = [task.difficulty for task in samples if task.difficulty is not None]
    return {
        "course_id": course_id,
        "minimum_sample_count": MIN_CALIBRATION_SAMPLES,
        "sample_count": len(samples),
        "eligible": factor is not None,
        "factor": factor,
        "ratio_bounds": {"minimum": SAMPLE_RATIO_MIN, "maximum": SAMPLE_RATIO_MAX},
        "median_ratio": round(raw_median, 3) if raw_median is not None else None,
        "difficulty_average": round(sum(difficulty_values) / len(difficulty_values), 2) if difficulty_values else None,
        "reset_at": reset_at,
        "explanation": (
            f"基于完成后显式填写的实际/预计时长比值中位数；单样本比值裁剪到 {SAMPLE_RATIO_MIN:g}–{SAMPLE_RATIO_MAX:g}，"
            f"达到 {MIN_CALIBRATION_SAMPLES} 个样本后才给出建议系数。"
        ),
    }


def _json_safe_calibration(payload: dict[str, Any]) -> dict[str, Any]:
    """JSON columns cannot store datetime objects returned by the read contract."""

    result = dict(payload)
    if result.get("reset_at") is not None:
        result["reset_at"] = as_utc(result["reset_at"]).isoformat()
    return result


def _eligible_plan_items(plan: StudyPlan) -> tuple[list[StudyPlanItem], dict[str, Any], list[StudyPlanItem]]:
    items, _warnings, _materials, _tasks = decode_plan_content(plan.plan_content)
    metadata = decode_plan_agent_metadata(plan.plan_content)
    baseline = metadata["baseline_items"]
    manual = set(metadata["manual_item_ids"])
    eligible = [
        item for item in items
        if item.status != "completed"
        and item.id not in manual
        and baseline.get(item.id) == item.model_dump(mode="json")
    ]
    # v1/no-baseline plans deliberately produce an empty candidate set.
    return items, metadata, eligible


def _candidate_changes(plan: StudyPlan, task: Task, trigger: str) -> list[dict[str, Any]]:
    _items, _metadata, eligible = _eligible_plan_items(plan)
    if not eligible:
        return []
    if trigger in {"task_completed", "task_canceled"}:
        targets = [item for item in eligible if any(ref.source_id == task.id and ref.navigation_key == task.navigation_key for ref in item.source_task_refs)]
        changes: list[dict[str, Any]] = []
        for item in targets:
            after = item.model_copy(deep=True)
            after.source_task_ids = [value for value in after.source_task_ids if value != task.id]
            after.source_task_refs = [ref for ref in after.source_task_refs if ref.navigation_key != task.navigation_key]
            terminal_label = "已完成" if trigger == "task_completed" else "已取消"
            after.content = f"{after.content}\n智能体差异：关联任务“{task.name}”{terminal_label}，预留时段改作复盘或缓冲。"[:2000]
            changes.append({"item_id": item.id, "before": item.model_dump(mode="json"), "after": after.model_dump(mode="json")})
        return changes
    # New/overdue/actual-time triggers need a visible yet narrow adjustment.
    target = sorted(eligible, key=lambda item: (item.date, item.id))[0]
    after = target.model_copy(deep=True)
    labels = {
        "task_created": "新增任务",
        "task_overdue": "逾期任务回收",
        "actual_minutes_changed": "实际用时反馈",
        "deadline_changed": "截止时间变化",
    }
    note = labels.get(trigger, "任务变化")
    minutes = task.actual_minutes if trigger == "actual_minutes_changed" else (task.remaining_minutes or task.estimated_minutes)
    detail = f"智能体差异：{note}“{task.name}”"
    if minutes is not None:
        detail += f"（{minutes} 分钟）"
    after.content = f"{after.content}\n{detail}，请在确认后纳入本时段。"[:2000]
    if task.id not in after.source_task_ids:
        after.source_task_ids = [*after.source_task_ids, task.id][:50]
    if not any(ref.navigation_key == task.navigation_key for ref in after.source_task_refs):
        after.source_task_refs = [*after.source_task_refs, PlanSourceIdentity(source_id=task.id, navigation_key=task.navigation_key)][:50]
    return [{"item_id": target.id, "before": target.model_dump(mode="json"), "after": after.model_dump(mode="json")}]


def plan_delta_fingerprint(plan: StudyPlan, task: Task, trigger: str) -> str:
    return _digest({"action": APPLY_PLAN_DELTA, "trigger": trigger, "plan_id": plan.id, "plan_navigation_key": plan.navigation_key,
                    "plan_content": plan_content_fingerprint(plan.plan_content), "task": task_feedback_snapshot(task)})


def create_plan_delta_candidates(db: Session, task: Task, trigger: str, *, now: datetime | None = None) -> list[AgentSuggestion]:
    """Record every trigger and create only safe, user-confirmable candidates."""

    evaluated_at = now or utc_now()
    event_payload = {"trigger": trigger, "task_snapshot": task_feedback_snapshot(task)}
    if trigger not in {"task_completed", "task_canceled"}:
        db.add(AgentEvent(event_type=trigger, entity_type="task", entity_id=task.id, entity_navigation_key=task.navigation_key, payload=event_payload))
    if task.course_id is None:
        db.add(AgentEvent(event_type="plan_delta_evaluated", entity_type="task", entity_id=task.id, entity_navigation_key=task.navigation_key,
                          payload={**event_payload, "outcome": "no_course"}))
        return []
    plans = list(db.scalars(select(StudyPlan).where(
        StudyPlan.course_id == task.course_id, StudyPlan.status == "active"
    ).order_by(StudyPlan.id.asc())).all())
    if not plans:
        db.add(AgentEvent(event_type="plan_delta_evaluated", entity_type="task", entity_id=task.id, entity_navigation_key=task.navigation_key,
                          payload={**event_payload, "outcome": "no_active_plan"}))
        return []
    # A newer task event supersedes any pending delta derived from an older task snapshot.
    for pending in db.scalars(select(AgentSuggestion).where(
        AgentSuggestion.action_type == APPLY_PLAN_DELTA, AgentSuggestion.status == "pending"
    )).all():
        if pending.current_payload.get("task_id") == task.id:
            pending.status = "expired"
            pending.updated_at = evaluated_at
            db.add(AgentEvent(event_type="plan_delta_expired", suggestion_id=pending.id, entity_type="study_plan",
                              entity_id=pending.source_id, entity_navigation_key=pending.source_navigation_key, payload={"reason_code": "source_task_changed"}))
    created: list[AgentSuggestion] = []
    for plan in plans:
        changes = _candidate_changes(plan, task, trigger)
        common = {**event_payload, "plan_id": plan.id, "plan_snapshot": plan_content_fingerprint(plan.plan_content),
                  "protected_item_count": len(_eligible_plan_items(plan)[0]) - len(_eligible_plan_items(plan)[2])}
        if not changes:
            db.add(AgentEvent(event_type="plan_delta_evaluated", entity_type="study_plan", entity_id=plan.id, entity_navigation_key=plan.navigation_key,
                              payload={**common, "outcome": "no_safe_change"}))
            continue
        fingerprint = plan_delta_fingerprint(plan, task, trigger)
        suggestion = AgentSuggestion(
            action_type=APPLY_PLAN_DELTA, status="pending", source_type="study_plan", source_id=plan.id, source_navigation_key=plan.navigation_key,
            source_name=plan.title, title=f"复核“{plan.title}”的计划差异",
            explanation=f"检测到“{task.name}”发生{ {'task_created':'新增','task_completed':'完成','task_canceled':'取消','task_overdue':'逾期','actual_minutes_changed':'实际用时变化','deadline_changed':'截止时间变化'}.get(trigger, '状态') }，仅提出未完成且未人工修改的计划项调整。",
            reason_code=trigger, current_payload={"task_id": task.id, "task_snapshot": task_feedback_snapshot(task),
                                                    "plan_snapshot": common["plan_snapshot"]},
            proposed_payload={"plan_id": plan.id, "trigger": trigger, "changes": changes},
            risk_level="medium" if trigger in ("task_overdue", "actual_minutes_changed") else "low",
            confidence=0.9, expires_at=evaluated_at + timedelta(days=7), fingerprint=fingerprint,
            created_at=evaluated_at, updated_at=evaluated_at,
        )
        try:
            with db.begin_nested():
                db.add(suggestion)
                db.flush()
        except IntegrityError:
            db.expire_all()
            continue
        db.add(AgentEvent(event_type="plan_delta_created", suggestion_id=suggestion.id, entity_type="study_plan",
                          entity_id=plan.id, entity_navigation_key=plan.navigation_key, payload={**common, "trigger": trigger, "change_count": len(changes)}))
        created.append(suggestion)
    return created


def recompute_delta_is_current(db: Session, suggestion: AgentSuggestion) -> tuple[StudyPlan | None, Task | None, list[dict[str, Any]]]:
    if suggestion.action_type != APPLY_PLAN_DELTA:
        return None, None, []
    plan = db.get(StudyPlan, suggestion.source_id)
    task_id = suggestion.current_payload.get("task_id")
    task = db.get(Task, task_id) if isinstance(task_id, int) else None
    if plan is None or task is None or plan.status != "active" or plan.navigation_key != suggestion.source_navigation_key:
        return plan, task, []
    if suggestion.current_payload.get("plan_snapshot") != plan_content_fingerprint(plan.plan_content):
        return plan, task, []
    if suggestion.current_payload.get("task_snapshot") != task_feedback_snapshot(task):
        return plan, task, []
    changes = _candidate_changes(plan, task, suggestion.reason_code)
    if changes != suggestion.proposed_payload.get("changes"):
        return plan, task, []
    return plan, task, changes


def complete_task_with_feedback(
    db: Session, task: Task, *, actual_minutes: int | None, difficulty: int | None,
    idempotency_key: str | None, now: datetime | None = None,
) -> Task:
    """Atomically complete one task and retain a real receipt for feedback."""

    evaluated_at = now or utc_now()
    if idempotency_key:
        existing = db.scalar(select(AgentSuggestion).where(AgentSuggestion.idempotency_key == idempotency_key))
        if existing is not None:
            if existing.action_type == COMPLETE_TASK and existing.source_type == "task" and existing.source_id == task.id and existing.source_navigation_key == task.navigation_key:
                return task
            raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
    before = task_feedback_snapshot(task)
    was_completed = task.status == "completed"
    # The legacy empty completion remains a no-op on an already completed task;
    # explicit feedback may be corrected later and has its own audit record.
    if was_completed and actual_minutes is None and difficulty is None:
        return task
    selected = {"status": "completed", "remaining_minutes": 0}
    if actual_minutes is not None:
        selected["actual_minutes"] = actual_minutes
    if difficulty is not None:
        selected["difficulty"] = difficulty
    if not was_completed:
        selected["completed_at"] = evaluated_at.isoformat()
    fingerprint = _digest({"action": COMPLETE_TASK, "task": before, "selected": selected, "key": idempotency_key})
    suggestion = AgentSuggestion(
        action_type=COMPLETE_TASK, status="accepted", source_type="task", source_id=task.id, source_navigation_key=task.navigation_key, source_name=task.name,
        title=f"完成“{task.name}”", explanation="用户确认任务完成；实际用时与难度仅在主动填写后保存。",
        reason_code="completion_feedback" if actual_minutes is not None or difficulty is not None else "completion_quick",
        current_payload=before, proposed_payload=selected, risk_level="low", confidence=1.0,
        expires_at=evaluated_at, fingerprint=fingerprint, idempotency_key=idempotency_key,
        created_at=evaluated_at, updated_at=evaluated_at, accepted_at=evaluated_at,
    )
    db.add(suggestion)
    db.flush()
    task.status = "completed"
    task.remaining_minutes = 0
    if not was_completed:
        task.completed_at = evaluated_at
    if actual_minutes is not None:
        task.actual_minutes = actual_minutes
    if difficulty is not None:
        task.difficulty = difficulty
    after = task_feedback_snapshot(task)
    db.add(ActionReceipt(
        suggestion_id=suggestion.id, action_type=COMPLETE_TASK, source_type="task", source_id=task.id, source_navigation_key=task.navigation_key,
        outcome="executed", applied_payload=selected, before_payload=before, after_payload=after,
        message="任务已完成，并已保存完成反馈" if actual_minutes is not None or difficulty is not None else "任务已完成",
        executed_at=evaluated_at,
    ))
    suggestion.status = "executed"
    suggestion.executed_at = evaluated_at
    db.add(AgentEvent(event_type="task_completed" if not was_completed else "task_feedback_updated", suggestion_id=suggestion.id,
                      entity_type="task", entity_id=task.id, entity_navigation_key=task.navigation_key, payload={"before": before, "after": after}))
    if not was_completed:
        create_plan_delta_candidates(db, task, "task_completed", now=evaluated_at)
    if actual_minutes is not None and before.get("actual_minutes") != actual_minutes:
        create_plan_delta_candidates(db, task, "actual_minutes_changed", now=evaluated_at)
    return task


def reset_calibration(
    db: Session, course_id: int, *, idempotency_key: str, now: datetime | None = None,
) -> dict[str, Any]:
    evaluated_at = now or utc_now()
    existing = db.scalar(select(AgentSuggestion).where(AgentSuggestion.idempotency_key == idempotency_key))
    if existing is not None:
        if existing.action_type == RESET_COURSE_CALIBRATION and existing.source_type == "course" and existing.source_id == course_id:
            return calibration_payload(db, course_id)
        raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
    before = calibration_payload(db, course_id)
    state = db.scalar(select(CourseCalibrationState).where(CourseCalibrationState.course_id == course_id))
    if state is None:
        state = CourseCalibrationState(course_id=course_id, reset_at=evaluated_at, reset_count=1)
        db.add(state)
    else:
        state.reset_at = evaluated_at
        state.reset_count += 1
    db.flush()
    after = calibration_payload(db, course_id)
    before_snapshot = _json_safe_calibration(before)
    after_snapshot = _json_safe_calibration(after)
    suggestion = AgentSuggestion(
        action_type=RESET_COURSE_CALIBRATION, status="executed", source_type="course", source_id=course_id,
        source_name=f"课程 {course_id}", title="重置课程估时校准", explanation="仅清空用于计算的历史窗口，不删除任务完成记录。",
        reason_code="user_requested_reset", current_payload=before_snapshot, proposed_payload={"reset_at": evaluated_at.isoformat()},
        risk_level="low", confidence=1.0, expires_at=evaluated_at,
        fingerprint=_digest({"action": RESET_COURSE_CALIBRATION, "course_id": course_id, "key": idempotency_key}),
        idempotency_key=idempotency_key, created_at=evaluated_at, updated_at=evaluated_at,
        accepted_at=evaluated_at, executed_at=evaluated_at,
    )
    db.add(suggestion)
    db.flush()
    db.add(ActionReceipt(suggestion_id=suggestion.id, action_type=RESET_COURSE_CALIBRATION, source_type="course",
                         source_id=course_id, outcome="executed", applied_payload={"reset_at": evaluated_at.isoformat()},
                         before_payload=before_snapshot, after_payload=after_snapshot,
                         message="课程估时校准窗口已重置，历史任务记录未删除", executed_at=evaluated_at))
    db.add(AgentEvent(event_type="calibration_reset", suggestion_id=suggestion.id, entity_type="course", entity_id=course_id,
                      payload={"before": before_snapshot, "after": after_snapshot}))
    return after
