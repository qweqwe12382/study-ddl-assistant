from datetime import date, timedelta
import json
import re
from typing import Any

from sqlalchemy import select


_NAVIGATION_KEY = re.compile(r"^[0-9a-f]{32}$")


def _assert_navigation_key(value: object) -> str:
    assert isinstance(value, str)
    assert _NAVIGATION_KEY.fullmatch(value), value
    return value


def _resolve(client, source_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    response = client.post("/api/agent/source-navigation/resolve", json={"source_refs": source_refs})
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _assert_unavailable(item: dict[str, Any]) -> None:
    assert item["available"] is False
    assert item["target"] is None


def _create_material(client, filename: str, *, course_id: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"original_filename": filename}
    if course_id is not None:
        payload["course_id"] = course_id
    response = client.post("/api/materials", json=payload)
    assert response.status_code == 201, response.text
    material = response.json()
    _assert_navigation_key(material["navigation_key"])
    return material


def _create_task(
    client,
    name: str,
    *,
    material_id: int | None = None,
    course_id: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": name}
    if material_id is not None:
        payload["material_id"] = material_id
    if course_id is not None:
        payload["course_id"] = course_id
    response = client.post("/api/tasks", json=payload)
    assert response.status_code == 201, response.text
    task = response.json()
    _assert_navigation_key(task["navigation_key"])
    return task


def _create_course(client, name: str = "M8.29 身份测试") -> dict[str, Any]:
    response = client.post("/api/courses", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def _generate_plan(client, course_id: int, *, days_ahead: int = 30) -> dict[str, Any]:
    response = client.post(
        "/api/study-plans/generate",
        json={
            "course_id": course_id,
            "exam_date": (date.today() + timedelta(days=days_ahead)).isoformat(),
            "daily_minutes": 60,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _db_from_client(client):
    from app.database import get_db

    generator = client.app.dependency_overrides[get_db]()
    return generator, next(generator)


def test_m829_material_navigation_key_is_required_after_sqlite_id_reuse(client):
    material_a = _create_material(client, "M829-A.pdf")
    material_id = material_a["id"]
    key_a = material_a["navigation_key"]

    first = _resolve(
        client,
        [{"source_type": "material", "source_id": material_id, "navigation_key": key_a}],
    )[0]
    assert first["available"] is True
    assert first["target"] == {
        "path": "/materials",
        "query": {"material_id": str(material_id), "navigation_key": key_a},
    }

    deleted = client.delete(f"/api/materials/{material_id}")
    assert deleted.status_code == 204, deleted.text
    material_b = _create_material(client, "M829-B.pdf")
    assert material_b["id"] == material_id, "测试必须覆盖 SQLite 删除后的编号复用"
    key_b = material_b["navigation_key"]
    assert key_b != key_a

    old_ref = _resolve(
        client,
        [{"source_type": "material", "source_id": material_id, "navigation_key": key_a}],
    )[0]
    _assert_unavailable(old_ref)

    numeric_ref = _resolve(client, [{"source_type": "material", "source_id": material_id}])[0]
    _assert_unavailable(numeric_ref)

    wrong_key = _resolve(
        client,
        [{"source_type": "material", "source_id": material_id, "navigation_key": "0" * 32}],
    )[0]
    _assert_unavailable(wrong_key)

    new_ref = _resolve(
        client,
        [{"source_type": "material", "source_id": material_id, "navigation_key": key_b}],
    )[0]
    assert new_ref["available"] is True
    assert new_ref["target"] == {
        "path": "/materials",
        "query": {"material_id": str(material_id), "navigation_key": key_b},
    }

    malformed = client.post(
        "/api/agent/source-navigation/resolve",
        json={
            "source_refs": [
                {"source_type": "material", "source_id": material_id, "navigation_key": "not-a-key"}
            ]
        },
    )
    assert malformed.status_code == 422, malformed.text


def test_m829_task_navigation_and_material_key_are_bound_to_the_current_rows(client):
    material = _create_material(client, "M829-task-source.pdf")
    task_a = _create_task(client, "M829 旧任务", material_id=material["id"])
    task_id = task_a["id"]
    key_a = task_a["navigation_key"]
    assert task_a["material_navigation_key"] == material["navigation_key"]

    first = _resolve(
        client,
        [{"source_type": "task", "source_id": task_id, "navigation_key": key_a}],
    )[0]
    assert first["available"] is True
    assert first["target"] == {
        "path": "/tasks",
        "query": {"task_id": str(task_id), "navigation_key": key_a},
    }

    deleted = client.delete(f"/api/tasks/{task_id}")
    assert deleted.status_code == 204, deleted.text
    task_b = _create_task(client, "M829 新任务", material_id=material["id"])
    assert task_b["id"] == task_id, "测试必须覆盖 SQLite 删除后的编号复用"
    key_b = task_b["navigation_key"]
    assert key_b != key_a
    assert task_b["material_navigation_key"] == material["navigation_key"]

    old_ref = _resolve(
        client,
        [{"source_type": "task", "source_id": task_id, "navigation_key": key_a}],
    )[0]
    _assert_unavailable(old_ref)
    _assert_unavailable(_resolve(client, [{"source_type": "task", "source_id": task_id}])[0])
    _assert_unavailable(
        _resolve(
            client,
            [{"source_type": "task", "source_id": task_id, "navigation_key": "0" * 32}],
        )[0]
    )

    new_ref = _resolve(
        client,
        [{"source_type": "task", "source_id": task_id, "navigation_key": key_b}],
    )[0]
    assert new_ref["available"] is True
    assert new_ref["target"] == {
        "path": "/tasks",
        "query": {"task_id": str(task_id), "navigation_key": key_b},
    }


def test_m829_plan_and_item_navigation_keys_are_validated_and_refs_are_typed(client):
    course = _create_course(client)
    material = _create_material(client, "M829-plan-source.pdf", course_id=course["id"])
    task = _create_task(client, "M829 计划任务", course_id=course["id"], material_id=material["id"])
    plan = _generate_plan(client, course["id"])

    plan_key = _assert_navigation_key(plan["navigation_key"])
    assert plan["items"]
    for item in plan["items"]:
        item_key = _assert_navigation_key(item["navigation_key"])
        assert item_key

    material_item = next((item for item in plan["items"] if item["source_material_refs"]), None)
    task_item = next((item for item in plan["items"] if item["source_task_refs"]), None)
    assert material_item is not None
    assert task_item is not None
    assert material_item["source_material_refs"] == [
        {"source_id": material["id"], "navigation_key": material["navigation_key"]}
    ]
    assert task_item["source_task_refs"] == [
        {"source_id": task["id"], "navigation_key": task["navigation_key"]}
    ]

    plan_id = plan["id"]
    resolved_plan = _resolve(
        client,
        [{"source_type": "study_plan", "source_id": plan_id, "navigation_key": plan_key}],
    )[0]
    assert resolved_plan["available"] is True
    assert resolved_plan["target"] == {
        "path": "/study-plans",
        "query": {"plan_id": str(plan_id), "navigation_key": plan_key},
    }
    _assert_unavailable(_resolve(client, [{"source_type": "study_plan", "source_id": plan_id}])[0])
    _assert_unavailable(
        _resolve(
            client,
            [{"source_type": "study_plan", "source_id": plan_id, "navigation_key": "0" * 32}],
        )[0]
    )

    item_key = material_item["navigation_key"]
    item_source_id = f"{plan_id}:{material_item['id']}"
    resolved_item = _resolve(
        client,
        [{"source_type": "study_plan_item", "source_id": item_source_id, "navigation_key": item_key}],
    )[0]
    assert resolved_item["available"] is True
    assert resolved_item["target"] == {
        "path": "/study-plans",
        "query": {"plan_id": str(plan_id), "item_id": material_item["id"], "navigation_key": item_key},
    }
    _assert_unavailable(
        _resolve(client, [{"source_type": "study_plan_item", "source_id": item_source_id}])[0]
    )
    _assert_unavailable(
        _resolve(
            client,
            [{"source_type": "study_plan_item", "source_id": item_source_id, "navigation_key": "0" * 32}],
        )[0]
    )
    malformed_item_key = client.post(
        "/api/agent/source-navigation/resolve",
        json={
            "source_refs": [
                {
                    "source_type": "study_plan_item",
                    "source_id": item_source_id,
                    "navigation_key": "not-a-key",
                }
            ]
        },
    )
    assert malformed_item_key.status_code == 422, malformed_item_key.text


def test_m829_action_receipt_uses_its_own_key_but_forwards_the_current_source_key(client):
    task_a = _create_task(client, "M829 回执旧任务")
    completed = client.post(f"/api/tasks/{task_a['id']}/complete")
    assert completed.status_code == 200, completed.text

    generator, db = _db_from_client(client)
    try:
        from app.models.agent import ActionReceipt

        receipt = db.scalar(
            select(ActionReceipt)
            .where(ActionReceipt.source_id == task_a["id"])
            .order_by(ActionReceipt.id.desc())
        )
        assert receipt is not None
        receipt_id = receipt.id
        receipt_key = _assert_navigation_key(receipt.navigation_key)
        assert receipt.source_navigation_key == task_a["navigation_key"]
    finally:
        generator.close()

    resolved = _resolve(
        client,
        [{"source_type": "action_receipt", "source_id": receipt_id, "navigation_key": receipt_key}],
    )[0]
    assert resolved["available"] is True
    assert resolved["target"] == {
        "path": "/tasks",
        "query": {"task_id": str(task_a["id"]), "navigation_key": task_a["navigation_key"]},
    }
    _assert_unavailable(
        _resolve(client, [{"source_type": "action_receipt", "source_id": receipt_id}])[0]
    )
    _assert_unavailable(
        _resolve(
            client,
            [{"source_type": "action_receipt", "source_id": receipt_id, "navigation_key": "0" * 32}],
        )[0]
    )

    deleted = client.delete(f"/api/tasks/{task_a['id']}")
    assert deleted.status_code == 204, deleted.text
    task_b = _create_task(client, "M829 回执新任务")
    assert task_b["id"] == task_a["id"], "测试必须覆盖 SQLite 删除后的编号复用"

    # A valid receipt identity must not fall through to a newly reused task ID.
    _assert_unavailable(
        _resolve(
            client,
            [{"source_type": "action_receipt", "source_id": receipt_id, "navigation_key": receipt_key}],
        )[0]
    )
    new_task = _resolve(
        client,
        [{"source_type": "task", "source_id": task_b["id"], "navigation_key": task_b["navigation_key"]}],
    )[0]
    assert new_task["target"] == {
        "path": "/tasks",
        "query": {"task_id": str(task_b["id"]), "navigation_key": task_b["navigation_key"]},
    }


def test_m829_named_collections_remain_resolvable_without_navigation_key(client):
    refs = [
        {"source_type": "task_collection", "source_id": "weekly_overdue"},
        {"source_type": "material_collection", "source_id": "failed_materials"},
        {"source_type": "study_plan_collection", "source_id": "weekly_plan_delays"},
        {"source_type": "capacity", "source_id": "next_7_days"},
    ]
    resolved = _resolve(client, refs)
    assert [item["available"] for item in resolved] == [True, True, True, True]
    assert [item["target"] for item in resolved] == [
        {"path": "/tasks", "query": {"view": "weekly_overdue"}},
        {"path": "/materials", "query": {"view": "failed_materials"}},
        {"path": "/study-plans", "query": {"view": "weekly_plan_delays"}},
        {"path": "/tasks", "query": {"view": "capacity_next_7_days"}},
    ]


def test_m829_study_plan_export_does_not_resolve_legacy_numeric_source_ids(client):
    course = _create_course(client, "M8.29 导出身份测试")
    material_a = _create_material(client, "M829-export-A.pdf", course_id=course["id"])
    plan_a = _generate_plan(client, course["id"])
    assert plan_a["items"][0]["source_material_refs"]

    # Simulate a real legacy payload directly in this isolated test database.
    # The update API intentionally preserves server-owned source refs and must
    # not let a client manufacture or erase an identity-bearing reference.
    generator, db = _db_from_client(client)
    try:
        from app.models.study_plan import StudyPlan

        stored_plan = db.get(StudyPlan, plan_a["id"])
        assert stored_plan is not None
        legacy_payload = json.loads(stored_plan.plan_content or "{}")
        legacy_payload["items"][0]["source_material_refs"] = []
        stored_plan.plan_content = json.dumps(legacy_payload, ensure_ascii=False)
        db.commit()
    finally:
        generator.close()

    deleted = client.delete(f"/api/materials/{material_a['id']}")
    assert deleted.status_code == 204, deleted.text
    material_b = _create_material(client, "M829-export-B.pdf", course_id=course["id"])
    assert material_b["id"] == material_a["id"], "测试必须覆盖 SQLite 删除后的编号复用"

    legacy_export = client.get(f"/api/exports/study-plans/{plan_a['id']}.md")
    assert legacy_export.status_code == 200, legacy_export.text
    legacy_text = legacy_export.content.decode("utf-8")
    assert "历史来源未验证" in legacy_text
    assert "M829-export-B.pdf" not in legacy_text

    # A one-day plan keeps the mismatched-ref export assertion focused on one
    # source row rather than also containing other valid repetitions of B.
    plan_b = _generate_plan(client, course["id"], days_ahead=0)
    assert plan_b["items"][0]["source_material_refs"] == [
        {"source_id": material_b["id"], "navigation_key": material_b["navigation_key"]}
    ]
    normal_items = [dict(item) for item in plan_b["items"]]
    normal_items[0]["title"] = "人工复习标题"
    normal_items[0]["content"] = "人工复习内容"
    normal_update = client.patch(
        f"/api/study-plans/{plan_b['id']}",
        json={"items": normal_items},
    )
    assert normal_update.status_code == 200, normal_update.text
    normal_export = client.get(f"/api/exports/study-plans/{plan_b['id']}.md")
    assert normal_export.status_code == 200, normal_export.text
    normal_text = normal_export.content.decode("utf-8")
    assert "来源：资料：M829-export-B.pdf" in normal_text

    # Likewise, inject a mismatched persisted ref to model an imported/corrupt
    # snapshot; the normal update API deliberately refuses client-owned source
    # identity changes.
    generator, db = _db_from_client(client)
    try:
        from app.models.study_plan import StudyPlan

        stored_plan = db.get(StudyPlan, plan_b["id"])
        assert stored_plan is not None
        wrong_payload = json.loads(stored_plan.plan_content or "{}")
        wrong_payload["items"][0]["title"] = "错误来源测试"
        wrong_payload["items"][0]["content"] = "不应解析同号资料"
        wrong_payload["items"][0]["source_material_refs"] = [
            {"source_id": material_b["id"], "navigation_key": "0" * 32}
        ]
        stored_plan.plan_content = json.dumps(wrong_payload, ensure_ascii=False)
        db.commit()
    finally:
        generator.close()

    wrong_export = client.get(f"/api/exports/study-plans/{plan_b['id']}.md")
    assert wrong_export.status_code == 200, wrong_export.text
    wrong_text = wrong_export.content.decode("utf-8")
    assert "来源已失效" in wrong_text
    assert "M829-export-B.pdf" not in wrong_text
