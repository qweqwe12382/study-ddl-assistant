"""M8.30 optimistic-edit and revision-lock regression coverage."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError


def _if_match(row: dict, *, key_field: str = "navigation_key", revision_field: str = "revision") -> dict[str, str]:
    return {"If-Match": f'"{row[key_field]}:{row[revision_field]}"'}


def _assert_conflict(response) -> None:
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "EDIT_CONFLICT"


def _assert_invalid_precondition(response) -> None:
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "INVALID_EDIT_PRECONDITION"


def _create_material(client, *, body: str = "资料正文") -> dict:
    response = client.post(
        "/api/materials",
        json={"original_filename": "M8.30 通知.txt", "extracted_text": body},
    )
    assert response.status_code == 201, response.text
    material = response.json()
    assert material["revision"] >= 1
    return material


def _create_task(client, *, course_id: int | None = None, name: str = "M8.30 任务") -> dict:
    response = client.post(
        "/api/tasks",
        json={
            "course_id": course_id,
            "name": name,
            "estimated_minutes": 60,
            "remaining_minutes": 60,
        },
    )
    assert response.status_code == 201, response.text
    task = response.json()
    assert task["revision"] >= 1
    return task


def _create_plan(client, course_id: int) -> dict:
    material = client.post(
        "/api/materials",
        json={"course_id": course_id, "original_filename": "M8.30 计划基础资料.md"},
    )
    assert material.status_code == 201, material.text
    response = client.post(
        "/api/study-plans/generate",
        json={
            "course_id": course_id,
            "exam_date": (date.today() + timedelta(days=3)).isoformat(),
            "daily_minutes": 60,
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()
    assert plan["revision"] >= 1
    assert plan["items"]
    return plan


def _db_from_client(client):
    from app.database import get_db

    generator = client.app.dependency_overrides[get_db]()
    return generator, next(generator)


def test_m830_revision_reads_latest_headers_and_legacy_no_header_remain_compatible(client):
    course = client.post("/api/courses", json={"name": "M8.30 课程"}).json()
    material = _create_material(client)
    task = _create_task(client, course_id=course["id"])
    plan = _create_plan(client, course["id"])

    updated_material = client.patch(
        f"/api/materials/{material['id']}",
        json={"summary": "最新资料摘要"},
        headers=_if_match(material),
    )
    assert updated_material.status_code == 200, updated_material.text
    material_after = updated_material.json()
    assert material_after["summary"] == "最新资料摘要"
    assert material_after["revision"] > material["revision"]

    updated_task = client.patch(
        f"/api/tasks/{task['id']}",
        json={"priority": 4},
        headers=_if_match(task),
    )
    assert updated_task.status_code == 200, updated_task.text
    task_after = updated_task.json()
    assert task_after["priority"] == 4
    assert task_after["revision"] > task["revision"]

    updated_plan = client.patch(
        f"/api/study-plans/{plan['id']}",
        json={"title": "最新计划标题"},
        headers=_if_match(plan),
    )
    assert updated_plan.status_code == 200, updated_plan.text
    plan_after = updated_plan.json()
    assert plan_after["title"] == "最新计划标题"
    assert plan_after["revision"] > plan["revision"]

    # Omitting If-Match keeps the pre-M8.30 API behavior available to callers
    # that have not adopted the optimistic-edit contract yet.
    legacy_update = client.patch(
        f"/api/materials/{material['id']}",
        json={"summary": "无条件头兼容"},
    )
    assert legacy_update.status_code == 200, legacy_update.text
    assert legacy_update.json()["summary"] == "无条件头兼容"


def test_m830_matching_if_match_empty_patch_does_not_bump_revision_or_timestamp(client):
    course = client.post("/api/courses", json={"name": "M8.30 空编辑课程"}).json()
    material = _create_material(client)
    task = _create_task(client, course_id=course["id"], name="空编辑任务")
    plan = _create_plan(client, course["id"])

    for path, row in (
        (f"/api/materials/{material['id']}", material),
        (f"/api/tasks/{task['id']}", task),
        (f"/api/study-plans/{plan['id']}", plan),
    ):
        response = client.patch(path, json={}, headers=_if_match(row))
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["revision"] == row["revision"]
        assert body["updated_at"] == row["updated_at"]


@pytest.mark.parametrize(
    "invalid_shape",
    [
        pytest.param("unquoted", id="unquoted"),
        pytest.param("weak", id="weak"),
        pytest.param("wildcard", id="wildcard"),
        pytest.param("list", id="list"),
        pytest.param("zero", id="zero"),
        pytest.param("negative", id="negative"),
        pytest.param("leadingzero", id="leadingzero"),
        pytest.param("oversize", id="oversize"),
        pytest.param("uppercase-key", id="uppercase-key"),
    ],
)
def test_m830_invalid_strong_if_match_shapes_are_400(client, invalid_shape):
    material = _create_material(client)
    key = material["navigation_key"]
    revision = material["revision"]
    valid_value = f'"{key}:{revision}"'
    invalid_values = {
        "unquoted": f"{key}:{revision}",
        "weak": f"W/{valid_value}",
        "wildcard": "*",
        "list": f"{valid_value}, {valid_value}",
        "zero": f'"{key}:0"',
        "negative": f'"{key}:-1"',
        "leadingzero": f'"{key}:01"',
        # A 33-character key is outside the strong-tag grammar's fixed
        # navigation-key width and is distinct from a legal-but-stale key.
        "oversize": f'"{key}0:{revision}"',
        "uppercase-key": f'"{key.upper()}:{revision}"',
    }

    response = client.patch(
        f"/api/materials/{material['id']}",
        json={"summary": "非法头不应写入"},
        headers={"If-Match": invalid_values[invalid_shape]},
    )
    _assert_invalid_precondition(response)
    saved = client.get(f"/api/materials/{material['id']}").json()
    assert saved["summary"] is None
    assert saved["revision"] == revision


def test_m830_stale_edit_conflicts_and_keeps_current_value(client):
    material = _create_material(client)
    old_header = _if_match(material)

    first = client.patch(
        f"/api/materials/{material['id']}",
        json={"summary": "第一次保存"},
        headers=old_header,
    )
    assert first.status_code == 200, first.text
    current = first.json()

    stale = client.patch(
        f"/api/materials/{material['id']}",
        json={"summary": "旧页面覆盖"},
        headers=old_header,
    )
    _assert_conflict(stale)

    saved = client.get(f"/api/materials/{material['id']}")
    assert saved.status_code == 200
    assert saved.json()["summary"] == "第一次保存"
    assert saved.json()["revision"] == current["revision"]


def test_m830_malformed_or_wrong_edit_preconditions_are_explicit(client):
    material = _create_material(client)

    malformed = client.patch(
        f"/api/materials/{material['id']}",
        json={"summary": "不应写入"},
        headers={"If-Match": "not-a-strong-etag"},
    )
    _assert_invalid_precondition(malformed)

    wrong_revision = client.patch(
        f"/api/materials/{material['id']}",
        json={"summary": "不应写入"},
        headers={"If-Match": f'"{material["navigation_key"]}:999"'},
    )
    _assert_conflict(wrong_revision)

    old_key = material["navigation_key"]
    wrong_key = ("0" if old_key[0] != "0" else "1") + old_key[1:]
    wrong_key_response = client.patch(
        f"/api/materials/{material['id']}",
        json={"summary": "不应写入"},
        headers={"If-Match": f'"{wrong_key}:{material["revision"]}"'},
    )
    _assert_conflict(wrong_key_response)

    assert client.get(f"/api/materials/{material['id']}").json()["summary"] is None


def test_m830_stale_delete_does_not_remove_new_task_state(client):
    task = _create_task(client)
    old_header = _if_match(task)
    saved = client.patch(
        f"/api/tasks/{task['id']}",
        json={"name": "当前任务名称"},
        headers=old_header,
    )
    assert saved.status_code == 200, saved.text
    current = saved.json()

    stale_delete = client.delete(f"/api/tasks/{task['id']}", headers=old_header)
    _assert_conflict(stale_delete)

    still_there = client.get(f"/api/tasks/{task['id']}")
    assert still_there.status_code == 200
    assert still_there.json()["name"] == "当前任务名称"
    assert still_there.json()["revision"] == current["revision"]


def test_m830_stale_task_completion_has_no_receipt_or_feedback_side_effect(client):
    task = _create_task(client)
    old_header = _if_match(task)
    changed = client.patch(
        f"/api/tasks/{task['id']}",
        json={"priority": 5},
        headers=old_header,
    )
    assert changed.status_code == 200, changed.text
    current = changed.json()

    from app.models.agent import ActionReceipt, AgentEvent, AgentSuggestion

    generator, db = _db_from_client(client)
    try:
        counts_before = {
            ActionReceipt: db.query(ActionReceipt).count(),
            AgentSuggestion: db.query(AgentSuggestion).count(),
            AgentEvent: db.query(AgentEvent).count(),
        }
    finally:
        generator.close()

    for path, body in (
        (
            f"/api/tasks/{task['id']}/complete",
            {"actual_minutes": 30, "difficulty": 4, "idempotency_key": "m830-stale-direct"},
        ),
        (
            f"/api/agent/tasks/{task['id']}/complete",
            {"actual_minutes": 45, "difficulty": 5, "idempotency_key": "m830-stale-agent"},
        ),
    ):
        stale = client.post(path, json=body, headers=old_header)
        _assert_conflict(stale)

    saved = client.get(f"/api/tasks/{task['id']}")
    assert saved.status_code == 200
    saved_body = saved.json()
    assert saved_body["status"] == "not_started"
    assert saved_body["actual_minutes"] is None
    assert saved_body["difficulty"] is None
    assert saved_body["priority"] == current["priority"]
    assert saved_body["revision"] == current["revision"]

    generator, db = _db_from_client(client)
    try:
        counts_after = {
            ActionReceipt: db.query(ActionReceipt).count(),
            AgentSuggestion: db.query(AgentSuggestion).count(),
            AgentEvent: db.query(AgentEvent).count(),
        }
    finally:
        generator.close()
    assert counts_after == counts_before


def test_m830_stale_plan_items_and_archive_do_not_overwrite_current_plan(client):
    course = client.post("/api/courses", json={"name": "M8.30 计划课程"}).json()
    plan = _create_plan(client, course["id"])
    old_header = _if_match(plan)

    renamed = client.patch(
        f"/api/study-plans/{plan['id']}",
        json={"title": "当前计划标题"},
        headers=old_header,
    )
    assert renamed.status_code == 200, renamed.text
    current = renamed.json()
    stale_items = [dict(item) for item in current["items"]]
    stale_items[0]["status"] = "completed"

    stale_completion = client.patch(
        f"/api/study-plans/{plan['id']}",
        json={"items": stale_items},
        headers=old_header,
    )
    _assert_conflict(stale_completion)

    stale_archive = client.post(f"/api/study-plans/{plan['id']}/archive", headers=old_header)
    _assert_conflict(stale_archive)

    saved = client.get(f"/api/study-plans/{plan['id']}")
    assert saved.status_code == 200
    saved_body = saved.json()
    assert saved_body["title"] == "当前计划标题"
    assert saved_body["status"] == "active"
    assert saved_body["items"][0]["status"] == current["items"][0]["status"]
    assert saved_body["revision"] == current["revision"]


def test_m830_material_body_change_invalidates_old_confirmation_preview(client):
    material = _create_material(
        client,
        body="作业一：完成 SQL 练习，截止时间：2026年10月15日 23:59",
    )
    extracted = client.post(f"/api/materials/{material['id']}/extract")
    assert extracted.status_code == 200, extracted.text
    preview = extracted.json()
    assert preview["material_navigation_key"] == material["navigation_key"]
    assert preview["material_revision"] >= material["revision"]
    assert preview["tasks"]
    preview_header = _if_match(
        {"navigation_key": preview["material_navigation_key"], "revision": preview["material_revision"]}
    )
    candidate = preview["tasks"][0]

    changed_body = client.patch(
        f"/api/materials/{material['id']}",
        json={"extracted_text": "新作业：完成 Python 报告，截止时间：2026年10月20日 18:00"},
        headers=preview_header,
    )
    assert changed_body.status_code == 200, changed_body.text
    current = changed_body.json()
    assert current["revision"] > preview["material_revision"]
    assert current["extraction_status"] == "not_started"

    stale_confirm = client.post(
        f"/api/materials/{material['id']}/extraction/confirm",
        json={"tasks": [candidate]},
        headers=preview_header,
    )
    _assert_conflict(stale_confirm)
    assert client.get("/api/tasks").json() == []

    # A fresh extraction preview and matching header still form a valid
    # confirmation path after the body edit.
    fresh_extract = client.post(
        f"/api/materials/{material['id']}/extract",
        headers=_if_match(current),
    )
    assert fresh_extract.status_code == 200, fresh_extract.text
    fresh_preview = fresh_extract.json()
    assert fresh_preview["material_revision"] > current["revision"]
    confirmed = client.post(
        f"/api/materials/{material['id']}/extraction/confirm",
        json={"tasks": fresh_preview["tasks"]},
        headers=_if_match(
            {
                "navigation_key": fresh_preview["material_navigation_key"],
                "revision": fresh_preview["material_revision"],
            }
        ),
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["confirmed_task_ids"]


def test_m830_retry_and_extract_require_current_material_header(client, isolated_upload_dir):
    response = client.post(
        "/api/materials/upload",
        files={
            "files": (
                "M8.30 retry.txt",
                "作业一：提交实验报告，截止时间：2026年10月15日".encode("utf-8"),
                "text/plain",
            )
        },
    )
    assert response.status_code == 201, response.text
    material = response.json()[0]

    changed = client.patch(
        f"/api/materials/{material['id']}",
        json={"summary": "当前摘要"},
        headers=_if_match(material),
    )
    assert changed.status_code == 200, changed.text
    current = changed.json()

    stale_retry = client.post(
        f"/api/materials/{material['id']}/retry",
        headers=_if_match(material),
    )
    _assert_conflict(stale_retry)
    assert client.get(f"/api/materials/{material['id']}").json()["summary"] == "当前摘要"

    retried = client.post(
        f"/api/materials/{material['id']}/retry",
        headers=_if_match(current),
    )
    assert retried.status_code == 200, retried.text
    retried_body = retried.json()
    assert retried_body["revision"] > current["revision"]

    stale_extract = client.post(
        f"/api/materials/{material['id']}/extract",
        headers=_if_match(current),
    )
    _assert_conflict(stale_extract)

    fresh_extract = client.post(
        f"/api/materials/{material['id']}/extract",
        headers=_if_match(retried_body),
    )
    assert fresh_extract.status_code == 200, fresh_extract.text
    assert fresh_extract.json()["material_revision"] > retried_body["revision"]


def test_m830_old_navigation_key_cannot_update_same_number_after_recreate(client):
    original = _create_material(client, body="旧对象")
    old_header = _if_match(original)
    deleted = client.delete(f"/api/materials/{original['id']}")
    assert deleted.status_code == 204, deleted.text

    replacement = _create_material(client, body="新对象")
    assert replacement["id"] == original["id"]
    assert replacement["revision"] == original["revision"]
    assert replacement["navigation_key"] != original["navigation_key"]

    stale = client.patch(
        f"/api/materials/{replacement['id']}",
        json={"summary": "旧页面越权写入"},
        headers=old_header,
    )
    _assert_conflict(stale)
    saved = client.get(f"/api/materials/{replacement['id']}").json()
    assert saved["extracted_text"] == "新对象"
    assert saved["summary"] is None


@pytest.mark.parametrize("kind", ["material", "task", "study_plan"])
def test_m830_two_orm_sessions_keep_first_value_and_reject_stale_commit(tmp_path, kind):
    from app.database import Base
    from app.models.material import Material
    from app.models.study_plan import StudyPlan
    from app.models.task import Task

    models = {"material": Material, "task": Task, "study_plan": StudyPlan}
    model = models[kind]
    engine = create_engine(
        f"sqlite:///{tmp_path / f'm830-{kind}.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            if kind == "material":
                entity = Material(original_filename="ORM 资料", extracted_text="原文")
                field, first_value, second_value = "summary", "先提交摘要", "后提交摘要"
            elif kind == "task":
                entity = Task(name="ORM 任务")
                field, first_value, second_value = "name", "先提交任务", "后提交任务"
            else:
                entity = StudyPlan(title="ORM 计划", plan_content="{}")
                field, first_value, second_value = "title", "先提交计划", "后提交计划"
            db.add(entity)
            db.commit()
            entity_id = entity.id
            assert entity.revision == 1

        with Session(engine) as first, Session(engine) as second:
            first_entity = first.get(model, entity_id)
            second_entity = second.get(model, entity_id)
            assert first_entity is not None and second_entity is not None
            assert first_entity.revision == second_entity.revision == 1
            setattr(first_entity, field, first_value)
            setattr(second_entity, field, second_value)

            first.commit()
            assert first_entity.revision == 2
            with pytest.raises(StaleDataError):
                second.commit()
            second.rollback()

        with Session(engine) as db:
            saved = db.get(model, entity_id)
            assert saved is not None
            assert getattr(saved, field) == first_value
            assert saved.revision == 2
    finally:
        engine.dispose()


def test_m830_conditional_precondition_rejects_delete_recreate_aba(tmp_path):
    from app.database import Base
    from app.models.material import Material
    from app.services.edit_concurrency import check_edit_precondition

    engine = create_engine(
        f"sqlite:///{tmp_path / 'm830-aba.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as seed:
            original = Material(original_filename="ABA 旧资料", extracted_text="旧")
            seed.add(original)
            seed.commit()
            entity_id = original.id
            old_key = original.navigation_key
            old_revision = original.revision

        first = Session(engine)
        try:
            old_entity = first.get(Material, entity_id)
            assert old_entity is not None

            with Session(engine) as second:
                second.delete(second.get(Material, entity_id))
                second.commit()
                replacement = Material(
                    id=entity_id,
                    original_filename="ABA 新资料",
                    extracted_text="新",
                )
                second.add(replacement)
                second.commit()
                assert replacement.revision == old_revision
                assert replacement.navigation_key != old_key

            with pytest.raises(HTTPException) as raised:
                check_edit_precondition(first, old_entity, f'"{old_key}:{old_revision}"')
            assert raised.value.status_code == 409
            assert raised.value.detail["code"] == "EDIT_CONFLICT"
            first.rollback()
        finally:
            first.close()

        with Session(engine) as verify:
            saved = verify.get(Material, entity_id)
            assert saved is not None
            assert saved.original_filename == "ABA 新资料"
            assert saved.revision == old_revision
    finally:
        engine.dispose()


def test_m830_revision_migration_from_old_sql_is_idempotent():
    from app.database import _apply_revision_migrations

    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE materials (id INTEGER PRIMARY KEY, original_filename TEXT)"))
            connection.execute(text("CREATE TABLE tasks (id INTEGER PRIMARY KEY, name TEXT)"))
            connection.execute(text("CREATE TABLE study_plans (id INTEGER PRIMARY KEY, title TEXT)"))
            connection.execute(text("INSERT INTO materials VALUES (1, '旧资料')"))
            connection.execute(text("INSERT INTO tasks VALUES (1, '旧任务')"))
            connection.execute(text("INSERT INTO study_plans VALUES (1, '旧计划')"))

        with engine.begin() as connection:
            _apply_revision_migrations(connection)
        with engine.begin() as connection:
            _apply_revision_migrations(connection)

        inspector = inspect(engine)
        for table_name in ("materials", "tasks", "study_plans"):
            columns = {column["name"]: column for column in inspector.get_columns(table_name)}
            assert "revision" in columns
            assert columns["revision"]["nullable"] is False

        with engine.connect() as connection:
            assert connection.scalar(text("SELECT revision FROM materials WHERE id=1")) == 1
            assert connection.scalar(text("SELECT revision FROM tasks WHERE id=1")) == 1
            assert connection.scalar(text("SELECT revision FROM study_plans WHERE id=1")) == 1
    finally:
        engine.dispose()
