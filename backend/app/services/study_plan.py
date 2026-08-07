"""Deterministic review-plan generation and storage helpers."""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from app.models.material import Material
from app.models.task import Task
from app.schemas.study_plan import StudyPlanItem


MAX_PLAN_DAYS = 366
MAX_FOCUSES_PER_DAY = 3


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


def _focus_entries(materials: list[Material], tasks: list[Task]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for material in materials:
        points = _material_points(material)
        entries.append(
            {
                "label": material.original_filename,
                "detail": points[0],
                "knowledge_points": points,
                "material_id": material.id,
                "task_id": None,
            }
        )
    for task in tasks:
        if task.status == "completed":
            continue
        detail = _short_text(task.description or task.source_quote, limit=100) or "检查要求并完成提交准备"
        entries.append(
            {
                "label": task.name,
                "detail": detail,
                "knowledge_points": [task.task_type] if task.task_type else [],
                "material_id": None,
                "task_id": task.id,
            }
        )
    return entries


def generate_review_items(
    *,
    start_date: date,
    exam_date: date,
    daily_minutes: int,
    materials: list[Material],
    tasks: list[Task],
) -> tuple[list[StudyPlanItem], list[str]]:
    """Generate one editable session per available day.

    The generator intentionally uses local database data only. It is predictable,
    works without an LLM key, and keeps the source IDs on each session for review.
    """

    total_days = (exam_date - start_date).days + 1
    if total_days <= 0:
        raise ValueError("考试日期不能早于今天")
    if total_days > MAX_PLAN_DAYS:
        raise ValueError(f"复习计划最多生成 {MAX_PLAN_DAYS} 天，请把考试日期设在一年内")

    entries = _focus_entries(materials, tasks)
    warnings: list[str] = []
    if not materials and not tasks:
        warnings.append("当前课程还没有资料或未完成任务，建议先补充复习内容。")
    if total_days <= 7:
        warnings.append(f"距离考试仅 {total_days} 天，建议优先处理高优先级任务。")
    if len(entries) > total_days:
        warnings.append(
            f"当前有 {len(entries)} 个复习主题，但只有 {total_days} 天，部分日期会安排多个主题。"
        )
    if len(entries) > total_days * MAX_FOCUSES_PER_DAY:
        warnings.append(
            f"复习主题较多，每天最多安排 {MAX_FOCUSES_PER_DAY} 个主题，建议手动调整重点。"
        )

    estimated_minutes = max(90, len(materials) * 60 + len([task for task in tasks if task.status != "completed"]) * 30)
    available_minutes = total_days * daily_minutes
    if estimated_minutes > available_minutes:
        warnings.append(
            f"预计复习内容约需 {estimated_minutes} 分钟，可用时间为 {available_minutes} 分钟，时间可能不足。"
        )

    if entries:
        # Spread all available topics across the available days. When there are
        # more topics than days, a day can contain up to three topics instead of
        # silently skipping everything after the first rotation.
        day_focuses: list[list[dict[str, Any]]] = [[] for _ in range(total_days)]
        for entry_index, entry in enumerate(entries):
            day_focuses[entry_index % total_days].append(entry)
    else:
        fallback = {
            "label": "课程范围",
            "detail": "整理考试范围和待复习章节",
            "knowledge_points": ["考试范围"],
            "material_id": None,
            "task_id": None,
        }
        day_focuses = [[fallback] for _ in range(total_days)]

    items: list[StudyPlanItem] = []
    for index in range(total_days):
        focuses = day_focuses[index] or [entries[index % len(entries)]] if entries else day_focuses[index]
        focuses = focuses[:MAX_FOCUSES_PER_DAY]
        phase = _phase(index, total_days)
        labels = [focus["label"] for focus in focuses]
        title = f"{phase} · {'、'.join(labels)}"
        instructions = []
        knowledge_points: list[str] = []
        source_material_ids: list[int] = []
        source_task_ids: list[int] = []
        for focus in focuses:
            if focus["task_id"]:
                instructions.append(f"检查任务“{focus['label']}”：{focus['detail']}")
                if focus["task_id"] not in source_task_ids:
                    source_task_ids.append(focus["task_id"])
            else:
                instructions.append(f"复习“{focus['label']}”：{focus['detail']}")
                if focus["material_id"] and focus["material_id"] not in source_material_ids:
                    source_material_ids.append(focus["material_id"])
            for point in focus["knowledge_points"]:
                if point and point not in knowledge_points:
                    knowledge_points.append(point)
        content = f"{phase}安排：{'；'.join(instructions)}。"
        items.append(
            StudyPlanItem(
                id=f"day-{index + 1}",
                date=start_date + timedelta(days=index),
                phase=phase,
                title=title[:200],
                content=content[:2000],
                minutes=daily_minutes,
                knowledge_points=knowledge_points[:20],
                source_material_ids=source_material_ids[:50],
                source_task_ids=source_task_ids[:50],
            )
        )
    return items, warnings


def encode_plan_content(
    items: list[StudyPlanItem],
    warnings: list[str],
    *,
    material_count: int = 0,
    task_count: int = 0,
) -> str:
    payload = {
        "version": 1,
        "items": [item.model_dump(mode="json") for item in items],
        "warnings": warnings,
        "material_count": material_count,
        "task_count": task_count,
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
