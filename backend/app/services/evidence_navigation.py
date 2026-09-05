"""Server-authoritative resolution for durable learning-agent evidence.

Weekly snapshots and reminders keep their original source references so the
historical record remains understandable after a task, material, or plan item
is removed.  Navigation, by contrast, is resolved against the current local
database at click time.  This separation prevents stale evidence from opening
an invented client route or silently referring to a newly reused identifier.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent import ActionReceipt
from app.models.material import Material
from app.models.study_plan import StudyPlan
from app.models.task import Task
from app.services.source_identity import valid_navigation_key
from app.services.study_plan import decode_plan_content


_POSITIVE_ID = re.compile(r"^[1-9][0-9]{0,9}$")
_PLAN_ITEM_REF = re.compile(r"^([1-9][0-9]{0,9}):(.*)$", re.DOTALL)
_MAX_DISPLAY_LABEL_LENGTH = 200

# Collection identifiers are not general filters.  Each one is a deliberate,
# named view which the UI may render from existing local data only.
_COLLECTION_TARGETS: dict[tuple[str, str], tuple[str, dict[str, str], str]] = {
    ("task_collection", "weekly_overdue"): ("/tasks", {"view": "weekly_overdue"}, "近 7 天逾期任务"),
    ("task_collection", "weekly_estimate_variance"): ("/tasks", {"view": "weekly_estimate_variance"}, "近 7 天估时偏差任务"),
    ("material_collection", "current_inbox"): ("/materials", {"view": "current_inbox"}, "当前资料收件箱"),
    ("material_collection", "failed_materials"): ("/materials", {"view": "failed_materials"}, "处理失败资料"),
    ("material_collection", "review_materials"): ("/materials", {"view": "review_materials"}, "待复核资料"),
    ("study_plan_collection", "weekly_plan_delays"): ("/study-plans", {"view": "weekly_plan_delays"}, "延期复习计划项"),
    ("capacity", "next_7_days"): ("/tasks", {"view": "capacity_next_7_days"}, "未来 7 天学习容量"),
}


def _identity(source_type: str, source_id: int | str, navigation_key: str | None = None) -> dict[str, str | None]:
    return {"source_type": source_type, "source_id": str(source_id), "navigation_key": navigation_key}


def _unavailable(source_type: str, source_id: int | str, navigation_key: str | None, message: str) -> dict[str, Any]:
    return {"source_ref": _identity(source_type, source_id, navigation_key), "available": False, "target": None,
            "label": None, "message": message}


def _available(source_type: str, source_id: int | str, navigation_key: str | None, *, path: str, query: dict[str, str], label: str,
               message: str = "已定位到当前可用页面") -> dict[str, Any]:
    return {"source_ref": _identity(source_type, source_id, navigation_key), "available": True,
            "target": {"path": path, "query": query}, "label": label, "message": message}


def _display_label(value: object) -> str:
    """Keep a live database label within the public response contract.

    Historical evidence can refer to a currently renamed file.  A filename is
    allowed to be longer than the UI label field, but that must make only the
    label compact, never make the navigation endpoint fail.
    """

    return str(value)[:_MAX_DISPLAY_LABEL_LENGTH]


def _positive_id(value: int | str) -> int | None:
    text = str(value)
    if not _POSITIVE_ID.fullmatch(text):
        return None
    return int(text)


def _navigation_identity_is_current(entity: Any, navigation_key: str | None) -> bool:
    return valid_navigation_key(navigation_key) and entity is not None and entity.navigation_key == navigation_key


def _resolve_task(db: Session, source_type: str, source_id: int | str, navigation_key: str | None) -> dict[str, Any]:
    identifier = _positive_id(source_id)
    task = db.get(Task, identifier) if identifier is not None else None
    if not _navigation_identity_is_current(task, navigation_key):
        return _unavailable(source_type, source_id, navigation_key, "该历史任务已不存在或身份已变化，保留证据但不提供跳转")
    return _available(source_type, source_id, navigation_key, path="/tasks",
                      query={"task_id": str(task.id), "navigation_key": task.navigation_key}, label=_display_label(task.name))


def _resolve_material(db: Session, source_type: str, source_id: int | str, navigation_key: str | None) -> dict[str, Any]:
    identifier = _positive_id(source_id)
    material = db.get(Material, identifier) if identifier is not None else None
    if not _navigation_identity_is_current(material, navigation_key):
        return _unavailable(source_type, source_id, navigation_key, "该历史资料已不存在或身份已变化，保留证据但不提供跳转")
    return _available(source_type, source_id, navigation_key, path="/materials",
                      query={"material_id": str(material.id), "navigation_key": material.navigation_key},
                      label=_display_label(material.original_filename))


def _resolve_plan(db: Session, source_type: str, source_id: int | str, navigation_key: str | None) -> dict[str, Any]:
    identifier = _positive_id(source_id)
    plan = db.get(StudyPlan, identifier) if identifier is not None else None
    if not _navigation_identity_is_current(plan, navigation_key):
        return _unavailable(source_type, source_id, navigation_key, "该历史复习计划已不存在或身份已变化，保留证据但不提供跳转")
    return _available(source_type, source_id, navigation_key, path="/study-plans",
                      query={"plan_id": str(plan.id), "navigation_key": plan.navigation_key}, label=_display_label(plan.title))


def _resolve_plan_item(db: Session, source_type: str, source_id: int | str, navigation_key: str | None) -> dict[str, Any]:
    match = _PLAN_ITEM_REF.fullmatch(str(source_id))
    if match is None:
        return _unavailable(source_type, source_id, navigation_key, "计划项证据标识无效，不能生成跳转")
    plan_id, item_id = int(match.group(1)), match.group(2)
    # Plan-item IDs are user-editable strings in the existing plan contract.
    # Keep that compatibility while refusing control characters; the value is
    # still emitted only as a value under the fixed `item_id` query key.
    if not item_id or len(item_id) > 80 or any(ord(char) < 32 for char in item_id):
        return _unavailable(source_type, source_id, navigation_key, "计划项证据标识无效，不能生成跳转")
    plan = db.get(StudyPlan, plan_id)
    if plan is None:
        return _unavailable(source_type, source_id, navigation_key, "该历史复习计划已不存在，保留证据但不提供跳转")
    items, _warnings, _materials, _tasks = decode_plan_content(plan.plan_content)
    item = next((row for row in items if row.id == item_id), None)
    if item is None or not valid_navigation_key(navigation_key) or item.navigation_key != navigation_key:
        return _unavailable(source_type, source_id, navigation_key, "该历史计划项已被删除或身份已变化，保留证据但不提供跳转")
    return _available(source_type, source_id, navigation_key, path="/study-plans",
                      query={"plan_id": str(plan.id), "item_id": item.id, "navigation_key": item.navigation_key},
                      label=_display_label(item.title))


def _resolve_receipt(db: Session, source_type: str, source_id: int | str, navigation_key: str | None) -> dict[str, Any]:
    identifier = _positive_id(source_id)
    receipt = db.get(ActionReceipt, identifier) if identifier is not None else None
    if not _navigation_identity_is_current(receipt, navigation_key):
        return _unavailable(source_type, source_id, navigation_key, "该历史执行回执已不存在或身份已变化，保留证据但不提供跳转")
    # Receipts are audit evidence, not a screen.  Resolve their already-stored
    # server source to one of the fixed current views; no receipt payload is
    # interpreted as a URL or command.
    if receipt.source_type == "task":
        resolved = _resolve_task(db, "task", receipt.source_id, receipt.source_navigation_key)
    elif receipt.source_type == "study_plan":
        resolved = _resolve_plan(db, "study_plan", receipt.source_id, receipt.source_navigation_key)
    else:
        return _unavailable(source_type, source_id, navigation_key, "该执行回执没有可用的站内来源页面")
    if not resolved["available"]:
        return _unavailable(source_type, source_id, navigation_key, "回执关联的当前来源已不存在或身份已变化，保留证据但不提供跳转")
    return _available(source_type, source_id, navigation_key, path=resolved["target"]["path"], query=resolved["target"]["query"],
                      label=f"执行回执：{receipt.action_type}", message="已定位到该回执关联的当前来源")


def resolve_source_navigation(db: Session, source_type: str, source_id: int | str,
                              navigation_key: str | None = None) -> dict[str, Any]:
    """Resolve one whitelisted evidence identity without any database writes."""

    if source_type == "task":
        return _resolve_task(db, source_type, source_id, navigation_key)
    if source_type == "material":
        return _resolve_material(db, source_type, source_id, navigation_key)
    if source_type == "study_plan":
        return _resolve_plan(db, source_type, source_id, navigation_key)
    if source_type == "study_plan_item":
        return _resolve_plan_item(db, source_type, source_id, navigation_key)
    if source_type == "action_receipt":
        return _resolve_receipt(db, source_type, source_id, navigation_key)
    target = _COLLECTION_TARGETS.get((source_type, str(source_id)))
    if target is not None:
        path, query, label = target
        return _available(source_type, source_id, navigation_key, path=path, query=query, label=label)
    return _unavailable(source_type, source_id, navigation_key, "该证据来源不在允许的站内导航范围内")


def resolve_source_navigation_batch(db: Session, source_refs: list[Any]) -> list[dict[str, Any]]:
    """Bounded order-preserving resolver used by the HTTP contract."""

    return [resolve_source_navigation(db, row.source_type, row.source_id, row.navigation_key) for row in source_refs]
