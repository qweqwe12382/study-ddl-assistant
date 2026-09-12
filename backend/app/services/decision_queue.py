"""Bounded, read-only next-decision projection for the learning agent.

This module deliberately derives its queue from existing authoritative records:
materials, still-valid user-confirmable suggestions, and the capacity projection
already calculated for one briefing.  It creates no AgentSuggestion, AgentEvent,
task, plan, reminder, or snapshot, and it never treats stored JSON as content or
as a route.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.agent import AgentSuggestion
from app.models.material import Material
from app.models.study_plan import StudyPlan
from app.models.task import Task
from app.services.agent import ADJUST_PRIORITY, SET_TASK_ESTIMATE, START_TASK
from app.services.agent_feedback import APPLY_PLAN_DELTA


_ORDERING_RULE = "risk_then_kind_then_source"
_PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "normal": 3}
_KIND_RANK = {
    "material_failed": 0,
    "capacity_overload_review": 1,
    "suggestion_priority_review": 2,
    "plan_delta_review": 3,
    "material_needs_review": 4,
    "capacity_estimate_review": 5,
    "capacity_same_day_review": 6,
    "capacity_start_review": 7,
    "material_ready": 8,
}


def _priority_for_risk(risk_level: object) -> str:
    # Persisted risk text is not public contract data.  Normalize only the
    # known values and fail safely to the lowest urgency for anything else.
    return {"high": "high", "medium": "medium", "unknown": "high", "low": "normal"}.get(
        str(risk_level), "normal"
    )


def _item(
    *,
    decision_id: str,
    kind: str,
    priority: str,
    title: str,
    description: str,
    action_label: str,
    reason_code: str,
    source_type: str,
    source_id: int | str,
    navigation_key: str | None = None,
    source_state: str,
    dedupe_key: str,
) -> dict[str, Any]:
    """Return only fixed public text and the minimal resolver identity."""

    return {
        "decision_id": decision_id,
        "kind": kind,
        "priority": priority,
        "title": title,
        "description": description,
        "action_label": action_label,
        "reason_code": reason_code,
        "source_refs": [{"source_type": source_type, "source_id": source_id, "navigation_key": navigation_key}],
        "calculation_basis": {
            "evaluated_at": None,  # populated once at the boundary below
            "ordering_rule": _ORDERING_RULE,
            "source_state": source_state,
        },
        "_dedupe_key": dedupe_key,
    }


def _material_candidates(db: Session) -> Iterable[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(Material)
            .where(
                or_(
                    Material.extraction_status.in_(("ready", "needs_review", "failed")),
                    Material.processing_status == "failed",
                )
            )
            .order_by(Material.id.asc())
        ).all()
    )
    for material in rows:
        if material.extraction_status == "failed" or material.processing_status == "failed":
            reason = "material_extraction_failed" if material.extraction_status == "failed" else "material_processing_failed"
            yield _item(
                decision_id=f"material:{material.id}:failed", kind="material_failed", priority="critical",
                title="处理失败资料", description="资料处理未完成，请先查看失败状态并决定是否重试或补充。",
                action_label="查看失败资料", reason_code=reason, source_type="material", source_id=material.id, navigation_key=material.navigation_key,
                source_state="failed", dedupe_key=f"material:{material.id}",
            )
        elif material.extraction_status == "needs_review":
            yield _item(
                decision_id=f"material:{material.id}:needs_review", kind="material_needs_review", priority="medium",
                title="复核资料识别结果", description="资料已产生待复核识别结果，确认前不会创建任务。",
                action_label="复核资料", reason_code="material_needs_review", source_type="material", source_id=material.id, navigation_key=material.navigation_key,
                source_state="needs_review", dedupe_key=f"material:{material.id}",
            )
        elif material.extraction_status == "ready":
            yield _item(
                decision_id=f"material:{material.id}:ready", kind="material_ready", priority="normal",
                title="确认资料识别结果", description="资料已完成本地识别，需人工确认后才会创建任务。",
                action_label="查看资料", reason_code="material_ready", source_type="material", source_id=material.id, navigation_key=material.navigation_key,
                source_state="ready", dedupe_key=f"material:{material.id}",
            )


def _pending_suggestion_candidates(db: Session, pending: Iterable[AgentSuggestion]) -> Iterable[dict[str, Any]]:
    """Project only known action/source pairs; unknown persisted rows disappear."""

    for suggestion in pending:
        if suggestion.action_type == APPLY_PLAN_DELTA and suggestion.source_type == "study_plan":
            plan = db.get(StudyPlan, suggestion.source_id)
            if plan is None or plan.navigation_key != suggestion.source_navigation_key:
                continue
            yield _item(
                decision_id=f"plan_delta:{suggestion.id}", kind="plan_delta_review",
                priority=_priority_for_risk(suggestion.risk_level), title="复核学习计划差异",
                description="计划差异仅供人工复核，确认前不会改动复习计划。", action_label="查看计划差异",
                reason_code="pending_plan_delta", source_type="study_plan", source_id=plan.id, navigation_key=plan.navigation_key,
                source_state="pending", dedupe_key=f"study_plan:{plan.id}",
            )
        elif suggestion.action_type == ADJUST_PRIORITY and suggestion.source_type == "task":
            task = db.get(Task, suggestion.source_id)
            if task is None or task.status in {"completed", "canceled"} or task.navigation_key != suggestion.source_navigation_key:
                continue
            yield _item(
                decision_id=f"priority_suggestion:{suggestion.id}", kind="suggestion_priority_review",
                priority=_priority_for_risk(suggestion.risk_level), title="复核待确认学习建议",
                description="该建议仍需人工确认，不会自动修改任务优先级。", action_label="查看待确认建议",
                reason_code="pending_priority_suggestion", source_type="task", source_id=task.id, navigation_key=task.navigation_key,
                source_state="pending", dedupe_key=f"task:{task.id}",
            )


def _capacity_candidates(db: Session, candidates: Iterable[dict[str, object]]) -> Iterable[dict[str, Any]]:
    """Use one current typed capacity candidate as a navigation-only signal."""

    for candidate in candidates:
        action_type = candidate.get("action_type")
        target_id = candidate.get("target_id")
        if action_type in (SET_TASK_ESTIMATE, START_TASK) and isinstance(target_id, int):
            task = db.get(Task, target_id)
            if task is None or task.status in {"completed", "canceled"}:
                continue
            if action_type == SET_TASK_ESTIMATE:
                yield _item(
                    decision_id=f"capacity:{SET_TASK_ESTIMATE}:task:{task.id}", kind="capacity_estimate_review",
                    priority="high", title="补充任务预计时长",
                    description="预计时长缺失，需人工补充后才能纳入容量计算。", action_label="查看任务估时",
                    reason_code="capacity_missing_estimate", source_type="task", source_id=task.id, navigation_key=task.navigation_key,
                    source_state="current_capacity", dedupe_key=f"task:{task.id}",
                )
            else:
                yield _item(
                    decision_id=f"capacity:{START_TASK}:task:{task.id}", kind="capacity_start_review",
                    priority=_priority_for_risk(candidate.get("risk_level")), title="复核今日学习任务",
                    description="这是当前容量计算下的下一步建议，仍需人工确认后才会开始任务。",
                    action_label="查看学习任务", reason_code="capacity_start_task", source_type="task", source_id=task.id, navigation_key=task.navigation_key,
                    source_state="current_capacity", dedupe_key=f"task:{task.id}",
                )
        elif action_type == "review_daily_overload" and isinstance(target_id, str):
            yield _item(
                decision_id=f"capacity:review_daily_overload:{target_id}", kind="capacity_overload_review",
                priority="critical", title="复核当日学习超载",
                description="当日已知学习量超过可用容量，请先人工调整安排。", action_label="查看学习容量",
                reason_code="capacity_daily_overload", source_type="capacity", source_id="next_7_days",
                source_state="current_capacity", dedupe_key=f"capacity_date:{target_id}",
            )
        elif action_type == "navigate_same_day_deadlines" and isinstance(target_id, str):
            yield _item(
                decision_id=f"capacity:navigate_same_day_deadlines:{target_id}", kind="capacity_same_day_review",
                priority="medium", title="查看同日截止任务",
                description="多项任务在同一天截止，建议先集中复核当前安排。", action_label="查看同日任务",
                reason_code="capacity_same_day_deadlines", source_type="capacity", source_id="next_7_days",
                source_state="current_capacity", dedupe_key=f"capacity_date:{target_id}",
            )


def build_decision_queue(
    db: Session,
    *,
    pending: Iterable[AgentSuggestion],
    capacity_candidates: Iterable[dict[str, object]],
    evaluated_at: datetime,
) -> list[dict[str, Any]]:
    """Return at most five deterministic, non-executable navigation decisions.

    A dedupe key represents the actual current object under review rather than
    the (possibly many) historic evidence references.  The sort therefore both
    prioritizes failure/risk and prevents a pending action plus capacity card
    from showing the same task twice in one briefing.
    """

    rows = [
        *_material_candidates(db),
        *_pending_suggestion_candidates(db, pending),
        *_capacity_candidates(db, capacity_candidates),
    ]
    rows.sort(key=lambda item: (
        _PRIORITY_RANK[item["priority"]],
        _KIND_RANK[item["kind"]],
        item["decision_id"],
    ))
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in rows:
        dedupe_key = item.pop("_dedupe_key")
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        item["calculation_basis"]["evaluated_at"] = evaluated_at
        result.append(item)
        if len(result) == 5:
            break
    return result
