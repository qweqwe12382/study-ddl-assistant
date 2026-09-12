"""M8.29 legacy identity migration and plan-item generation boundaries."""

from datetime import date, timedelta
import json

from sqlalchemy import create_engine, text

from app.database import _apply_agent_migrations, _apply_navigation_key_migrations
from app.services.source_identity import valid_navigation_key


def test_m829_migration_preserves_history_and_is_idempotent():
    legacy = create_engine("sqlite://")
    item = {
        "id": "day-1", "date": date.today().isoformat(), "phase": "复习", "title": "旧计划项",
        "content": "保留旧内容", "minutes": 30, "status": "not_started", "knowledge_points": [],
        "source_material_ids": [1], "source_task_ids": [1],
    }
    plan = json.dumps({"version": 2, "items": [item], "agent": {"baseline_items": {"day-1": item}}})
    historic = json.dumps({"source_refs": [{"source_type": "material", "source_id": 1}]})
    try:
        with legacy.begin() as connection:
            for table in ("materials", "tasks"):
                connection.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, name TEXT)"))
                connection.execute(text(f"INSERT INTO {table} VALUES (1, '原对象')"))
            connection.execute(text("CREATE TABLE study_plans (id INTEGER PRIMARY KEY, plan_content TEXT)"))
            connection.execute(text("INSERT INTO study_plans VALUES (1, :content)"), {"content": plan})
            connection.execute(text("CREATE TABLE action_receipts (id INTEGER PRIMARY KEY, source_id INTEGER)"))
            connection.execute(text("INSERT INTO action_receipts VALUES (1, 1)"))
            connection.execute(text("CREATE TABLE agent_suggestions (id INTEGER PRIMARY KEY, status TEXT, fingerprint TEXT)"))
            connection.execute(text("INSERT INTO agent_suggestions VALUES (1, 'pending', 'legacy')"))
            connection.execute(text("CREATE TABLE agent_events (id INTEGER PRIMARY KEY, entity_id INTEGER)"))
            connection.execute(text("INSERT INTO agent_events VALUES (1, 1)"))
            connection.execute(text("CREATE TABLE weekly_review_snapshots (id INTEGER PRIMARY KEY, review_payload JSON)"))
            connection.execute(text("INSERT INTO weekly_review_snapshots VALUES (1, :history)"), {"history": historic})

        with legacy.begin() as connection:
            _apply_agent_migrations(connection)
            _apply_navigation_key_migrations(connection)
            keys = {table: connection.scalar(text(f"SELECT navigation_key FROM {table} WHERE id=1"))
                    for table in ("materials", "tasks", "study_plans", "action_receipts")}
            assert all(valid_navigation_key(key) for key in keys.values())
            assert len(set(keys.values())) == 4
            migrated = connection.scalar(text("SELECT plan_content FROM study_plans WHERE id=1"))
            decoded = json.loads(migrated)
            migrated_item = decoded["items"][0]
            assert valid_navigation_key(migrated_item["navigation_key"])
            assert migrated_item["content"] == item["content"]
            assert migrated_item["source_material_ids"] == [1]
            assert migrated_item["source_material_refs"] == []
            assert migrated_item["source_task_refs"] == []
            assert decoded["agent"]["baseline_items"]["day-1"] == migrated_item
            assert connection.scalar(text("SELECT source_navigation_key FROM action_receipts")) is None
            assert connection.scalar(text("SELECT source_navigation_key FROM agent_suggestions")) is None
            assert connection.scalar(text("SELECT entity_navigation_key FROM agent_events")) is None
            assert connection.scalar(text("SELECT status FROM agent_suggestions")) == "expired"
            assert connection.scalar(text("SELECT review_payload FROM weekly_review_snapshots")) == historic
            _apply_agent_migrations(connection)
            _apply_navigation_key_migrations(connection)
            assert connection.scalar(text("SELECT plan_content FROM study_plans WHERE id=1")) == migrated
            for table, key in keys.items():
                assert connection.scalar(text(f"SELECT navigation_key FROM {table} WHERE id=1")) == key
    finally:
        legacy.dispose()


def test_m829_plan_item_key_is_server_owned_and_not_reused(client):
    course = client.post("/api/courses", json={"name": "计划身份课程"}).json()
    material = client.post(
        "/api/materials",
        json={"course_id": course["id"], "original_filename": "计划身份基础资料.md"},
    )
    assert material.status_code == 201
    response = client.post("/api/study-plans/generate", json={
        "course_id": course["id"], "exam_date": (date.today() + timedelta(days=2)).isoformat(), "daily_minutes": 60,
    })
    assert response.status_code == 201
    plan = response.json()
    original = plan["items"][0]
    original_key = original["navigation_key"]
    forged = {**original, "navigation_key": "a" * 32,
              "source_material_ids": [999], "source_material_refs": [{"source_id": 999, "navigation_key": "b" * 32}]}
    update = client.patch(f"/api/study-plans/{plan['id']}", json={"items": [forged]})
    assert update.status_code == 200
    saved = update.json()["items"][0]
    assert saved["navigation_key"] == original_key
    assert saved["source_material_refs"] == []
    duplicate = client.patch(f"/api/study-plans/{plan['id']}", json={"items": [saved, saved]})
    assert duplicate.status_code == 422
    assert client.patch(f"/api/study-plans/{plan['id']}", json={"items": []}).status_code == 200
    replacement = client.patch(f"/api/study-plans/{plan['id']}", json={"items": [original]}).json()["items"][0]
    assert replacement["id"] == original["id"]
    assert replacement["navigation_key"] != original_key
    refs = [{"source_type": "study_plan_item", "source_id": f"{plan['id']}:{original['id']}", "navigation_key": key}
            for key in (original_key, replacement["navigation_key"])]
    resolved = client.post("/api/agent/source-navigation/resolve", json={"source_refs": refs}).json()["items"]
    assert [row["available"] for row in resolved] == [False, True]
    assert resolved[1]["target"]["query"]["navigation_key"] == replacement["navigation_key"]


def test_m829_old_suggestion_cannot_execute_on_reused_task_id(client):
    from app.database import get_db
    from app.models.agent import AgentSuggestion
    from app.models.task import Task
    from app.services.agent import task_fingerprint
    from app.time import utc_now

    body = {"name": "原任务", "due_at": (utc_now() + timedelta(hours=12)).isoformat(), "priority": 2}
    task = client.post("/api/tasks", json=body).json()
    suggestion = client.post("/api/agent/refresh").json()["suggestions"][0]
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 204
    replacement = client.post("/api/tasks", json=body).json()
    assert replacement["id"] == task["id"]
    # Even matching the new object's ordinary snapshot cannot authorize the
    # previous generation: the independently saved source key is required.
    generator = client.app.dependency_overrides[get_db]()
    db = next(generator)
    try:
        stored = db.get(AgentSuggestion, suggestion["id"])
        stored.fingerprint = task_fingerprint(db.get(Task, replacement["id"]))
        db.commit()
    finally:
        generator.close()
    outcome = client.post(f"/api/agent/suggestions/{suggestion['id']}/accept", json={"idempotency_key": "m829-old-task"})
    assert outcome.status_code == 409
    assert client.get(f"/api/tasks/{replacement['id']}").json()["priority"] == 2
