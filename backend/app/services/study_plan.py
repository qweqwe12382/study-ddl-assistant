"""Deterministic review-plan generation and storage helpers."""

from __future__ import annotations

import json
from hashlib import sha256
from datetime import date, datetime, timedelta
from typing import Any

from app.models.material import Material
from app.models.task import Task
from app.schemas.study_plan import StudyPlanItem, StudyPlanUnscheduledItem
from app.services.source_identity import new_navigation_key, valid_navigation_key
from app.time import as_local, as_utc


MAX_PLAN_DAYS = 366
MAX_FOCUSES_PER_DAY = 3
DEFAULT_TASK_MINUTES = 30
DEFAULT_MATERIAL_MINUTES = 60


def _short_text(value: str | None, *, limit: int = 100) -> str | None:
    if not value:
        return None
    normalized = " ".join(value.split())
    if not normalized:
        return None
    return normalized if len(normalized) <= limit else f"{normalized[:limit - 1]}…"


def _material_points(material: Material) -> list[str]:
    points: list[str] = []
    for tag in material.tags or []:
        value = _short_text(tag, limit=50)
        if value and value not in points:
            points.append(value)

    source = material.summary or material.extracted_text or ""
    for line in source.splitlines():
        value = _short_text(line.strip(" -*•\t"), limit=100)
        if value and len(value) >= 3 and value not in points:
            points.append(value)
        if len(points) >= 3:
            break

    if not points:
        filename = material.original_filename.rsplit(".", 1)[0]
        points.append(_short_text(filename, limit=80) or "课程资料")
    return points[:3]


def _phase(index: int, total_days: int) -> str:
    ratio = (index + 1) / total_days
    if total_days == 1 or ratio > 0.8:
        return "考前冲刺"
    if ratio > 0.5:
        return "重点强化"
    return "基础梳理"


def _material_focus(material: Material) -> dict[str, Any]:
    points = _material_points(material)
    return {
        "kind": "material",
        "label": material.original_filename,
        "detail": points[0],
        "knowledge_points": points,
        "material_id": material.id,
        "navigation_key": material.navigation_key,
        "task_id": None,
    }


def _task_focus(task: Task) -> dict[str, Any]:
    return {
        "kind": "task",
        "label": task.name,
        "detail": _short_text(task.description or task.source_quote, limit=100)
        or "检查要求并完成提交准备",
        "knowledge_points": [task.task_type] if task.task_type else [],
        "material_id": None,
        "task_id": task.id,
        "navigation_key": task.navigation_key,
    }


def _allocate_focus(
    *,
    focus: dict[str, Any],
    requested_minutes: int,
    latest_day_index: int,
    day_focuses: list[list[dict[str, Any]]],
    day_remaining_minutes: list[int],
) -> tuple[int, list[int]]:
    """Allocate one source once per day while decrementing one shared workload.

    Returning the unallocated remainder makes overload an explicit result. The
    helper also enforces the existing three-focus display bound before capacity
    is consumed, so a later render step cannot silently slice assigned work.
    """

    unallocated = requested_minutes
    scheduled_days: list[int] = []
    for day_index in range(min(len(day_focuses), max(0, latest_day_index + 1))):
        if unallocated <= 0:
            break
        if day_remaining_minutes[day_index] <= 0:
            continue
        if len(day_focuses[day_index]) >= MAX_FOCUSES_PER_DAY:
            continue
        allocated = min(unallocated, day_remaining_minutes[day_index])
        day_focuses[day_index].append({**focus, "allocated_minutes": allocated})
        day_remaining_minutes[day_index] -= allocated
        unallocated -= allocated
        scheduled_days.append(day_index)
    return unallocated, scheduled_days


def _unallocated_reason(
    *,
    unallocated_minutes: int,
    latest_day_index: int,
    day_focuses: list[list[dict[str, Any]]],
    day_remaining_minutes: list[int],
) -> tuple[str, str]:
    last_index = min(len(day_focuses) - 1, latest_day_index)
    focus_blocked_minutes = sum(
        day_remaining_minutes[index]
        for index in range(max(0, last_index + 1))
        if len(day_focuses[index]) >= MAX_FOCUSES_PER_DAY
    )
    if focus_blocked_minutes >= unallocated_minutes:
        return "daily_focus_limit", f"部分日期已达到每天最多 {MAX_FOCUSES_PER_DAY} 个主题的限制"
    if focus_blocked_minutes:
        return (
            "daily_capacity_and_focus_limit",
            f"每日分钟容量不足，且部分日期已达到每天最多 {MAX_FOCUSES_PER_DAY} 个主题的限制",
        )
    return "daily_capacity", "本计划每日容量不足"


def generate_review_schedule(
    *,
    start_date: date,
    exam_date: date,
    daily_minutes: int,
    materials: list[Material],
    tasks: list[Task],
    calibration_factor: float | None = None,
    evaluated_at: datetime | None = None,
) -> tuple[list[StudyPlanItem], list[str], list[StudyPlanUnscheduledItem]]:
    """Generate one editable session per available day.

    The generator intentionally uses local database data only. It is predictable,
    works without an LLM key, and keeps the source IDs on each session for review.
    """

    total_days = (exam_date - start_date).days + 1
    if total_days <= 0:
        raise ValueError("考试日期不能早于今天")
    if total_days > MAX_PLAN_DAYS:
        raise ValueError(f"复习计划最多生成 {MAX_PLAN_DAYS} 天，请把考试日期设在一年内")

    unfinished = [task for task in tasks if task.status not in {"completed", "canceled"}]
    material_focuses = [_material_focus(material) for material in materials]
    task_focuses = {task.id: _task_focus(task) for task in unfinished}
    task_requested_minutes = {
        task.id: task.remaining_minutes
        if task.remaining_minutes is not None
        else (task.estimated_minutes if task.estimated_minutes is not None else DEFAULT_TASK_MINUTES)
        for task in unfinished
    }
    entry_count = len(material_focuses) + sum(minutes > 0 for minutes in task_requested_minutes.values())
    warnings: list[str] = []
    unscheduled_items: list[StudyPlanUnscheduledItem] = []
    if not materials and not unfinished:
        warnings.append("当前课程还没有资料或未完成任务，建议先补充复习内容。")
    if total_days <= 7:
        warnings.append(f"距离考试仅 {total_days} 天，建议优先处理高优先级任务。")
    if entry_count > total_days:
        warnings.append(
            f"当前有 {entry_count} 个复习主题，但只有 {total_days} 天，部分日期会安排多个主题。"
        )
    if entry_count > total_days * MAX_FOCUSES_PER_DAY:
        warnings.append(
            f"复习主题较多，每天最多安排 {MAX_FOCUSES_PER_DAY} 个主题，建议手动调整重点。"
        )

    raw_task_minutes = sum(task_requested_minutes.values())
    adjusted_task_minutes = round(raw_task_minutes * calibration_factor) if calibration_factor is not None else raw_task_minutes
    estimated_minutes = len(materials) * DEFAULT_MATERIAL_MINUTES + adjusted_task_minutes
    available_minutes = total_days * daily_minutes
    if estimated_minutes > available_minutes:
        warnings.append(
            f"预计复习内容约需 {estimated_minutes} 分钟，可用时间为 {available_minutes} 分钟，时间可能不足。"
        )
    if calibration_factor is not None:
        warnings.append(
            f"课程完成反馈校准系数 {calibration_factor:g} 仅用于总体工作量风险参考"
            f"（任务原始 {raw_task_minutes} 分钟）；本次日程仍按当前剩余或预计分钟分配。"
        )

    # `daily_minutes` is this plan's per-day review ceiling. It is intentionally
    # independent from the weekly/daily preference budget: shared capacity and
    # timetable occupancy require a later cross-plan calendar integration.
    day_focuses: list[list[dict[str, Any]]] = [[] for _ in range(total_days)]
    day_remaining_minutes = [daily_minutes for _ in range(total_days)]
    deadline_day_used = False

    def task_order(task: Task) -> tuple[date, int, int]:
        local_due = as_local(task.due_at).date() if task.due_at is not None else exam_date
        return local_due, -task.priority, task.id

    for task in sorted(unfinished, key=task_order):
        requested_minutes = task_requested_minutes[task.id]
        if task.remaining_minutes is None and task.estimated_minutes is None:
            warnings.append(
                f"任务“{task.name}”缺少剩余和预计时长，按 {DEFAULT_TASK_MINUTES} 分钟假设参与排期。"
            )

        if requested_minutes <= 0:
            warnings.append(f"任务“{task.name}”剩余时长为 0 分钟，未生成复习安排。")
            continue

        due_date = as_local(task.due_at).date() if task.due_at is not None else None
        if due_date is not None and due_date < start_date:
            message = (
                f"任务“{task.name}”有 {requested_minutes} 分钟未排入："
                f"截止日期 {due_date.isoformat()} 早于计划开始日期 {start_date.isoformat()}。"
            )
            warnings.append(message)
            unscheduled_items.append(
                StudyPlanUnscheduledItem(
                    source_type="task",
                    source_id=task.id,
                    navigation_key=task.navigation_key if valid_navigation_key(task.navigation_key) else None,
                    label=task.name,
                    requested_minutes=requested_minutes,
                    scheduled_minutes=0,
                    unscheduled_minutes=requested_minutes,
                    latest_date=due_date,
                    reason="deadline_passed",
                    message=message,
                )
            )
            continue
        if task.due_at is not None and evaluated_at is not None and as_utc(task.due_at) <= as_utc(evaluated_at):
            due_at_local = as_local(task.due_at)
            message = (
                f"任务“{task.name}”有 {requested_minutes} 分钟未排入："
                f"截止时间 {due_at_local.isoformat(timespec='minutes')} 已过。"
            )
            warnings.append(message)
            unscheduled_items.append(
                StudyPlanUnscheduledItem(
                    source_type="task",
                    source_id=task.id,
                    navigation_key=task.navigation_key if valid_navigation_key(task.navigation_key) else None,
                    label=task.name,
                    requested_minutes=requested_minutes,
                    scheduled_minutes=0,
                    unscheduled_minutes=requested_minutes,
                    latest_date=due_date,
                    reason="deadline_passed",
                    message=message,
                )
            )
            continue

        latest_date = min(due_date, exam_date) if due_date is not None else exam_date
        latest_day_index = (latest_date - start_date).days
        unallocated, scheduled_days = _allocate_focus(
            focus=task_focuses[task.id],
            requested_minutes=requested_minutes,
            latest_day_index=latest_day_index,
            day_focuses=day_focuses,
            day_remaining_minutes=day_remaining_minutes,
        )
        if due_date is not None and any(start_date + timedelta(days=index) == due_date for index in scheduled_days):
            deadline_day_used = True
        if unallocated:
            boundary = (
                f"截止日期 {due_date.isoformat()} 前"
                if due_date is not None and due_date <= exam_date
                else f"考试日期 {exam_date.isoformat()} 前"
            )
            reason, reason_message = _unallocated_reason(
                unallocated_minutes=unallocated,
                latest_day_index=latest_day_index,
                day_focuses=day_focuses,
                day_remaining_minutes=day_remaining_minutes,
            )
            message = f"任务“{task.name}”有 {unallocated} 分钟未排入：{boundary}{reason_message}。"
            warnings.append(message)
            unscheduled_items.append(
                StudyPlanUnscheduledItem(
                    source_type="task",
                    source_id=task.id,
                    navigation_key=task.navigation_key if valid_navigation_key(task.navigation_key) else None,
                    label=task.name,
                    requested_minutes=requested_minutes,
                    scheduled_minutes=requested_minutes - unallocated,
                    unscheduled_minutes=unallocated,
                    latest_date=latest_date,
                    reason=reason,
                    message=message,
                )
            )

    if deadline_day_used:
        warnings.append(
            "任务仅按 Asia/Shanghai 自然日排期；截止日当天的安排不代表已核验具体截止时刻前存在空闲时段。"
        )

    # Materials have no DDL. They use only capacity left after all unfinished
    # tasks, and each material's default review workload is consumed once.
    for material, focus in zip(materials, material_focuses):
        unallocated, _scheduled_days = _allocate_focus(
            focus=focus,
            requested_minutes=DEFAULT_MATERIAL_MINUTES,
            latest_day_index=total_days - 1,
            day_focuses=day_focuses,
            day_remaining_minutes=day_remaining_minutes,
        )
        if unallocated:
            reason, reason_message = _unallocated_reason(
                unallocated_minutes=unallocated,
                latest_day_index=total_days - 1,
                day_focuses=day_focuses,
                day_remaining_minutes=day_remaining_minutes,
            )
            message = (
                f"资料“{material.original_filename}”有 {unallocated} 分钟未排入："
                f"考试日期 {exam_date.isoformat()} 前{reason_message}。"
            )
            warnings.append(message)
            unscheduled_items.append(
                StudyPlanUnscheduledItem(
                    source_type="material",
                    source_id=material.id,
                    navigation_key=material.navigation_key if valid_navigation_key(material.navigation_key) else None,
                    label=material.original_filename,
                    requested_minutes=DEFAULT_MATERIAL_MINUTES,
                    scheduled_minutes=DEFAULT_MATERIAL_MINUTES - unallocated,
                    unscheduled_minutes=unallocated,
                    latest_date=exam_date,
                    reason=reason,
                    message=message,
                )
            )

    items: list[StudyPlanItem] = []
    for index in range(total_days):
        focuses = day_focuses[index]
        if not focuses:
            continue
        phase = _phase(index, total_days)
        labels = [focus["label"] for focus in focuses]
        title = f"{phase} · {'、'.join(labels)}"
        instructions = []
        knowledge_points: list[str] = []
        source_material_ids: list[int] = []
        source_task_ids: list[int] = []
        for focus in focuses:
            allocated_minutes = focus["allocated_minutes"]
            if focus["task_id"] is not None:
                instructions.append(
                    f"安排任务“{focus['label']}”{allocated_minutes} 分钟：{focus['detail']}"
                )
                if focus["task_id"] not in source_task_ids:
                    source_task_ids.append(focus["task_id"])
            elif focus["material_id"] is not None:
                instructions.append(
                    f"复习资料“{focus['label']}”{allocated_minutes} 分钟：{focus['detail']}"
                )
                if focus["material_id"] not in source_material_ids:
                    source_material_ids.append(focus["material_id"])
            for point in focus["knowledge_points"]:
                if point and point not in knowledge_points:
                    knowledge_points.append(point)
        content = f"{phase}安排：{'；'.join(instructions)}。"
        items.append(
            StudyPlanItem(
                id=f"day-{index + 1}",
                navigation_key=new_navigation_key(),
                date=start_date + timedelta(days=index),
                phase=phase,
                title=title[:200],
                content=content[:2000],
                minutes=sum(focus["allocated_minutes"] for focus in focuses),
                knowledge_points=knowledge_points[:20],
                source_material_ids=source_material_ids[:50],
                source_task_ids=source_task_ids[:50],
                source_material_refs=[{"source_id": focus["material_id"], "navigation_key": focus["navigation_key"]}
                                      for focus in focuses if focus["material_id"] is not None and valid_navigation_key(focus.get("navigation_key"))][:50],
                source_task_refs=[{"source_id": focus["task_id"], "navigation_key": focus["navigation_key"]}
                                  for focus in focuses if focus["task_id"] is not None and valid_navigation_key(focus.get("navigation_key"))][:50],
            )
        )
    return items, warnings, unscheduled_items


def generate_review_items(
    *,
    start_date: date,
    exam_date: date,
    daily_minutes: int,
    materials: list[Material],
    tasks: list[Task],
    calibration_factor: float | None = None,
    evaluated_at: datetime | None = None,
) -> tuple[list[StudyPlanItem], list[str]]:
    """Backward-compatible wrapper for callers that only consume text warnings."""

    items, warnings, _unscheduled_items = generate_review_schedule(
        start_date=start_date,
        exam_date=exam_date,
        daily_minutes=daily_minutes,
        materials=materials,
        tasks=tasks,
        calibration_factor=calibration_factor,
        evaluated_at=evaluated_at,
    )
    return items, warnings


def encode_plan_content(
    items: list[StudyPlanItem],
    warnings: list[str],
    *,
    material_count: int = 0,
    task_count: int = 0,
    unscheduled_items: list[StudyPlanUnscheduledItem] | None = None,
) -> str:
    for item in items:
        if not valid_navigation_key(item.navigation_key):
            item.navigation_key = new_navigation_key()
    baseline_items = {item.id: item.model_dump(mode="json") for item in items}
    payload = {
        "version": 3,
        "items": [item.model_dump(mode="json") for item in items],
        "warnings": warnings,
        "unscheduled_items": [item.model_dump(mode="json") for item in unscheduled_items or []],
        "material_count": material_count,
        "task_count": task_count,
        # A baseline is evidence, not a heuristic: a later plan-delta may only
        # touch an item still byte-equivalent to this generated version.
        "agent": {"baseline_items": baseline_items, "manual_item_ids": [], "adjustment_log": []},
    }
    return json.dumps(payload, ensure_ascii=False)


def decode_plan_content(content: str | None) -> tuple[list[StudyPlanItem], list[str], int, int]:
    if not content:
        return [], [], 0, 0
    try:
        payload = json.loads(content)
        items = [StudyPlanItem.model_validate(item) for item in payload.get("items", [])]
        warnings = [str(item) for item in payload.get("warnings", [])]
        return items, warnings, int(payload.get("material_count", 0)), int(payload.get("task_count", 0))
    except (TypeError, ValueError, json.JSONDecodeError):
        return [], ["计划内容无法读取，请重新生成或手动补充。"], 0, 0


def decode_plan_unscheduled_items(content: str | None) -> list[StudyPlanUnscheduledItem]:
    """Read additive scheduling feedback while keeping old plan snapshots valid."""

    if not content:
        return []
    try:
        payload = json.loads(content)
        raw_items = payload.get("unscheduled_items", []) if isinstance(payload, dict) else []
        if not isinstance(raw_items, list):
            return []
        return [StudyPlanUnscheduledItem.model_validate(item) for item in raw_items]
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def decode_plan_agent_metadata(content: str | None) -> dict[str, Any]:
    """Read optional M8.4 protection metadata without invalidating v1 plans."""

    try:
        payload = json.loads(content or "{}")
        agent = payload.get("agent") if isinstance(payload, dict) else None
        if not isinstance(agent, dict):
            return {"baseline_items": {}, "manual_item_ids": [], "adjustment_log": []}
        baseline = agent.get("baseline_items", {})
        manual = agent.get("manual_item_ids", [])
        log = agent.get("adjustment_log", [])
        return {
            "baseline_items": baseline if isinstance(baseline, dict) else {},
            "manual_item_ids": [str(value) for value in manual if isinstance(value, str)],
            "adjustment_log": log if isinstance(log, list) else [],
        }
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"baseline_items": {}, "manual_item_ids": [], "adjustment_log": []}


def encode_plan_content_with_metadata(
    items: list[StudyPlanItem], warnings: list[str], *, material_count: int, task_count: int,
    metadata: dict[str, Any], unscheduled_items: list[StudyPlanUnscheduledItem] | None = None,
) -> str:
    """Write the normal plan payload while retaining explicit user protections."""

    payload = {
        "version": 3,
        "items": [item.model_dump(mode="json") for item in items],
        "warnings": warnings,
        "unscheduled_items": [item.model_dump(mode="json") for item in unscheduled_items or []],
        "material_count": material_count,
        "task_count": task_count,
        "agent": {
            "baseline_items": metadata.get("baseline_items", {}),
            "manual_item_ids": sorted(set(str(value) for value in metadata.get("manual_item_ids", []))),
            "adjustment_log": list(metadata.get("adjustment_log", []))[-50:],
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def plan_content_fingerprint(content: str | None) -> str:
    """Stable plan-version token used to reject stale delta acceptance."""

    return sha256((content or "").encode("utf-8")).hexdigest()
