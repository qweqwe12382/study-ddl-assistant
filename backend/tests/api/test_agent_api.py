from datetime import timedelta

from app.time import utc_now


def _create_task(
    client, *, name: str, due_hours: float = 24, priority: int = 3, status: str = "not_started",
    course_id: int | None = None, estimated_minutes: int | None = None,
):
    payload = {
        "name": name,
        "due_at": (utc_now() + timedelta(hours=due_hours)).isoformat(),
        "priority": priority,
        "status": status,
        "course_id": course_id,
        "estimated_minutes": estimated_minutes,
    }
    if estimated_minutes is not None:
        payload["remaining_minutes"] = estimated_minutes
    return client.post(
        "/api/tasks",
        json=payload,
    ).json()


def _refresh_single_suggestion(client):
    response = client.post("/api/agent/refresh")
    assert response.status_code == 200
    assert response.json()["pending_count"] == 1
    return response.json()["suggestions"][0]


def test_agent_deadline_window_boundaries_are_inclusive_only_at_48_hours():
    from app.models.task import Task
    from app.services.agent import is_priority_candidate, risk_level_for

    now = utc_now()
    within = Task(name="47:59", due_at=now + timedelta(hours=47, minutes=59), priority=3, status="not_started")
    boundary = Task(name="48:00", due_at=now + timedelta(hours=48), priority=3, status="not_started")
    outside = Task(name="48:01", due_at=now + timedelta(hours=48, minutes=1), priority=3, status="not_started")

    assert is_priority_candidate(within, now) is True
    assert is_priority_candidate(boundary, now) is True
    assert is_priority_candidate(outside, now) is False
    assert risk_level_for(within, now) == "medium"
    assert risk_level_for(boundary, now) == "medium"


def test_agent_lightweight_migration_backfills_contract_columns_and_expires_unverifiable_pending():
    from sqlalchemy import create_engine, inspect, text

    from app.database import _apply_agent_migrations

    legacy_engine = create_engine("sqlite://")
    try:
        with legacy_engine.begin() as connection:
            connection.execute(text("CREATE TABLE agent_suggestions (id INTEGER PRIMARY KEY, status VARCHAR(30), fingerprint VARCHAR(128))"))
            connection.execute(text("INSERT INTO agent_suggestions (id, status, fingerprint) VALUES (1, 'pending', 'same')"))
            connection.execute(text("INSERT INTO agent_suggestions (id, status, fingerprint) VALUES (2, 'pending', 'same')"))
            connection.execute(text("CREATE TABLE agent_runs (id INTEGER PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE action_receipts (id INTEGER PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE agent_events (id INTEGER PRIMARY KEY)"))
            _apply_agent_migrations(connection)

            inspector = inspect(connection)
            assert {"title", "explanation"} <= {item["name"] for item in inspector.get_columns("agent_suggestions")}
            assert {"ruleset_version", "input_snapshot"} <= {item["name"] for item in inspector.get_columns("agent_runs")}
            assert {"before_payload", "after_payload", "message"} <= {
                item["name"] for item in inspector.get_columns("action_receipts")
            }
            assert {"entity_type", "entity_id"} <= {item["name"] for item in inspector.get_columns("agent_events")}
            assert connection.scalar(text("SELECT COUNT(*) FROM agent_suggestions WHERE status = 'pending'")) == 0
            assert connection.scalar(text("SELECT COUNT(*) FROM agent_suggestions WHERE status = 'expired'")) == 2
            assert connection.scalar(text("SELECT COUNT(*) FROM agent_suggestions WHERE source_navigation_key IS NOT NULL")) == 0
            assert "uq_agent_suggestions_pending_fingerprint" in {
                item["name"] for item in inspector.get_indexes("agent_suggestions")
            }
    finally:
        legacy_engine.dispose()


def test_agent_briefing_caps_display_but_counts_all_valid_pending_suggestions(client):
    for index in range(4):
        _create_task(client, name=f"待处理-{index}", due_hours=12 + index)

    briefing = client.post("/api/agent/refresh")

    assert briefing.status_code == 200
    assert briefing.json()["pending_count"] == 4
    assert len(briefing.json()["suggestions"]) == 3


def test_agent_briefing_and_pending_list_hide_elapsed_suggestions(client, monkeypatch):
    _create_task(client, name="即将过期建议", due_hours=1)
    _refresh_single_suggestion(client)
    future = utc_now() + timedelta(hours=2)
    from app.api import agent as agent_api

    monkeypatch.setattr(agent_api, "utc_now", lambda: future)

    briefing = client.get("/api/agent/briefing")
    pending = client.get("/api/agent/suggestions", params={"status": "pending"})

    assert briefing.status_code == 200
    assert briefing.json()["pending_count"] == 0
    assert briefing.json()["suggestions"] == []
    assert pending.json() == []


def test_agent_refresh_generates_only_eligible_task_and_reuses_pending_suggestion(client):
    eligible = _create_task(client, name="48小时内提交报告", due_hours=12)
    _create_task(client, name="三天后任务", due_hours=72)
    _create_task(client, name="已完成任务", status="completed")
    _create_task(client, name="高优先级任务", priority=4)

    first = client.post("/api/agent/refresh")
    second = client.post("/api/agent/refresh")

    assert first.status_code == 200
    assert first.json()["pending_count"] == 1
    suggestion = first.json()["suggestions"][0]
    assert suggestion["source_id"] == eligible["id"]
    assert suggestion["action_type"] == "adjust_priority"
    assert suggestion["reason_code"] == "deadline_within_48h"
    assert suggestion["proposed_payload"] == {"priority": 4}
    assert suggestion["current_payload"]["status"] == "not_started"
    assert suggestion["current_payload"]["due_at"]
    assert suggestion["title"]
    assert suggestion["explanation"]
    assert suggestion["risk_level"] == "high"
    assert second.status_code == 200
    assert second.json()["suggestions"][0]["id"] == suggestion["id"]
    assert len(client.get("/api/agent/suggestions").json()) == 1


def test_agent_accept_changes_priority_to_four_or_five_and_returns_receipt(client):
    first_task = _create_task(client, name="优先级提升到四")
    first = _refresh_single_suggestion(client)

    accepted_four = client.post(
        f"/api/agent/suggestions/{first['id']}/accept",
        json={"priority": 4, "idempotency_key": "priority-four"},
    )

    assert accepted_four.status_code == 200
    assert accepted_four.json()["status"] == "executed"
    assert accepted_four.json()["receipt"]["applied_payload"] == {"priority": 4}
    assert client.get(f"/api/tasks/{first_task['id']}").json()["priority"] == 4

    second_task = _create_task(client, name="优先级提升到五")
    second = _refresh_single_suggestion(client)
    assert second["source_id"] == second_task["id"]
    accepted_five = client.post(
        f"/api/agent/suggestions/{second['id']}/accept",
        json={"priority": 5, "idempotency_key": "priority-five"},
    )

    assert accepted_five.status_code == 200
    assert accepted_five.json()["receipt"]["applied_payload"] == {"priority": 5}
    assert client.get(f"/api/tasks/{second_task['id']}").json()["priority"] == 5


def test_agent_repeated_accept_returns_original_receipt_without_second_execution(client):
    task = _create_task(client, name="重复确认")
    suggestion = _refresh_single_suggestion(client)

    first = client.post(
        f"/api/agent/suggestions/{suggestion['id']}/accept",
        json={"idempotency_key": "repeat-accept"},
    )
    repeated = client.post(
        f"/api/agent/suggestions/{suggestion['id']}/accept",
        json={"priority": 5, "idempotency_key": "repeat-accept"},
    )

    assert first.status_code == repeated.status_code == 200
    assert first.json()["receipt"]["id"] == repeated.json()["receipt"]["id"]
    assert client.get(f"/api/tasks/{task['id']}").json()["priority"] == 4


def test_agent_dismiss_leaves_task_unchanged(client):
    task = _create_task(client, name="忽略建议")
    suggestion = _refresh_single_suggestion(client)

    response = client.post(
        f"/api/agent/suggestions/{suggestion['id']}/dismiss",
        json={"reason": "暂不调整"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"
    assert response.json()["dismissal_reason"] == "暂不调整"
    assert client.get(f"/api/tasks/{task['id']}").json()["priority"] == 3

    refreshed = client.post("/api/agent/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["pending_count"] == 0
    assert len(client.get("/api/agent/suggestions").json()) == 1


def test_agent_refresh_expires_pending_suggestion_when_task_state_changes(client):
    task = _create_task(client, name="状态变化后过期")
    suggestion = _refresh_single_suggestion(client)

    changed = client.patch(f"/api/tasks/{task['id']}", json={"status": "completed"})
    refreshed = client.post("/api/agent/refresh")
    expired = client.get("/api/agent/suggestions", params={"status": "expired"})

    assert changed.status_code == 200
    assert refreshed.status_code == 200
    assert refreshed.json()["pending_count"] == 0
    assert suggestion["id"] in [item["id"] for item in expired.json()]


def test_agent_snapshot_change_expires_old_suggestion_and_generates_new_one(client):
    task = _create_task(client, name="截止时间调整", due_hours=30)
    old_suggestion = _refresh_single_suggestion(client)

    changed = client.patch(
        f"/api/tasks/{task['id']}",
        json={"due_at": (utc_now() + timedelta(hours=12)).isoformat()},
    )
    refreshed = client.post("/api/agent/refresh")
    expired = client.get("/api/agent/suggestions", params={"status": "expired"}).json()

    assert changed.status_code == 200
    assert refreshed.status_code == 200
    assert refreshed.json()["pending_count"] == 1
    new_suggestion = refreshed.json()["suggestions"][0]
    assert new_suggestion["id"] != old_suggestion["id"]
    assert new_suggestion["fingerprint"] != old_suggestion["fingerprint"]
    assert old_suggestion["id"] in [item["id"] for item in expired]
    assert new_suggestion["risk_level"] == "high"


def test_agent_accept_expires_changed_task_without_modifying_priority(client):
    task = _create_task(client, name="直接确认前已变化")
    suggestion = _refresh_single_suggestion(client)

    changed = client.patch(f"/api/tasks/{task['id']}", json={"due_at": (utc_now() + timedelta(hours=12)).isoformat()})
    response = client.post(
        f"/api/agent/suggestions/{suggestion['id']}/accept",
        json={"idempotency_key": "changed-before-accept"},
    )

    assert changed.status_code == 200
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SUGGESTION_EXPIRED"
    assert client.get(f"/api/tasks/{task['id']}").json()["priority"] == 3
    assert client.get("/api/agent/suggestions", params={"status": "expired"}).json()[0]["id"] == suggestion["id"]


def test_agent_idempotency_key_cannot_be_reused_across_suggestions(client):
    _create_task(client, name="第一项")
    _create_task(client, name="第二项")
    suggestions = client.post("/api/agent/refresh").json()["suggestions"]

    first = client.post(
        f"/api/agent/suggestions/{suggestions[0]['id']}/accept",
        json={"idempotency_key": "shared-key"},
    )
    conflict = client.post(
        f"/api/agent/suggestions/{suggestions[1]['id']}/accept",
        json={"idempotency_key": "shared-key"},
    )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


def test_dev_reset_removes_agent_records_in_foreign_key_order(client):
    _create_task(client, name="重置智能体记录")
    suggestion = _refresh_single_suggestion(client)
    accepted = client.post(
        f"/api/agent/suggestions/{suggestion['id']}/accept",
        json={"idempotency_key": "reset-agent-records"},
    )

    response = client.post("/api/dev/reset")

    assert accepted.status_code == 200
    assert response.status_code == 200
    assert client.get("/api/agent/suggestions").json() == []


def test_m83_briefing_prioritizes_stably_with_course_weight_and_never_invents_minutes(client):
    course = client.post("/api/courses", json={"name": "高权重课程"}).json()
    client.put(
        "/api/study-preferences",
        json={"course_weights": {str(course["id"]): 2.0}, "preferred_time_slots": ["morning", "evening"]},
    )
    weighted = _create_task(client, name="加权任务", due_hours=30, priority=3, course_id=course["id"], estimated_minutes=60)
    missing = _create_task(client, name="缺估时任务", due_hours=32, priority=3)
    completed = _create_task(client, name="已完成任务", due_hours=1, status="completed", estimated_minutes=20)

    first = client.get("/api/agent/briefing")
    second = client.get("/api/agent/briefing")

    assert first.status_code == second.status_code == 200
    actions = first.json()["today_actions"]
    assert [item["task_id"] for item in actions] == [item["task_id"] for item in second.json()["today_actions"]]
    assert actions[0]["task_id"] == weighted["id"]
    assert completed["id"] not in [item["task_id"] for item in actions]
    missing_action = next(item for item in actions if item["task_id"] == missing["id"])
    assert missing_action["estimated_minutes"] is None
    assert "missing_estimate" in missing_action["reason_codes"]
    assert actions[0]["course_name"] == "高权重课程"
    assert actions[0]["preferred_time_slot"] == "morning"
    assert "score_components" in actions[0] and "score_basis" in actions[0]


def test_m83_capacity_candidates_cover_missing_estimate_high_day_and_same_day(client):
    client.put("/api/study-preferences", json={"daily_limit_minutes": 30, "weekly_available_minutes": 300, "buffer_ratio": 0})
    missing = _create_task(client, name="待估时", due_hours=72)
    _create_task(client, name="同日一", due_hours=73, estimated_minutes=20)
    _create_task(client, name="同日二", due_hours=73, estimated_minutes=20)

    briefing = client.post("/api/agent/refresh").json()
    candidates = briefing["capacity_action_candidates"]
    estimate = next(item for item in candidates if item["action_type"] == "set_task_estimate")

    assert estimate["target_id"] == missing["id"]
    assert estimate["suggestion_id"]
    assert estimate["allowed_input"]["estimated_minutes"] == {"minimum": 15, "maximum": 10080}
    assert estimate["source_refs"][0]["source_type"] == "task"
    overload = next(item for item in candidates if item["action_type"] == "review_daily_overload")
    same_day = next(item for item in candidates if item["action_type"] == "navigate_same_day_deadlines")
    assert overload["execution_mode"] == "review"
    assert same_day["execution_mode"] == "navigate"
    # Both date-level actions now carry evidence resolvable by the M8.7
    # server contract rather than relying on the client to invent a route.
    for candidate in (overload, same_day):
        assert candidate["source_refs"][0]["source_type"] == "capacity"
        assert candidate["source_refs"][0]["source_id"] == "next_7_days"
        assert candidate["source_refs"][0]["snapshot"]["local_date"] == candidate["target_id"]
        assert any(ref["source_type"] == "task" for ref in candidate["source_refs"])
    navigation = client.post("/api/agent/source-navigation/resolve", json={
        "source_refs": [
            {"source_type": overload["source_refs"][0]["source_type"], "source_id": overload["source_refs"][0]["source_id"]},
            {"source_type": same_day["source_refs"][0]["source_type"], "source_id": same_day["source_refs"][0]["source_id"]},
        ],
    })
    assert navigation.status_code == 200
    assert all(item["available"] for item in navigation.json()["items"])
    assert all(item["target"] == {"path": "/tasks", "query": {"view": "capacity_next_7_days"}}
               for item in navigation.json()["items"])
    assert briefing["capacity"]["risk_level"] == "high"


def test_m83_set_estimate_accept_is_bounded_idempotent_and_revalidates(client):
    task = _create_task(client, name="可确认估时", due_hours=72)
    briefing = client.post("/api/agent/refresh").json()
    candidate = next(item for item in briefing["capacity_action_candidates"] if item["target_id"] == task["id"])

    invalid = client.post(
        f"/api/agent/suggestions/{candidate['suggestion_id']}/accept",
        json={"idempotency_key": "estimate-invalid"},
    )
    accepted = client.post(
        f"/api/agent/suggestions/{candidate['suggestion_id']}/accept",
        json={"estimated_minutes": 75, "idempotency_key": "estimate-ok"},
    )
    repeated = client.post(
        f"/api/agent/suggestions/{candidate['suggestion_id']}/accept",
        json={"estimated_minutes": 76, "idempotency_key": "estimate-ok"},
    )

    assert invalid.status_code == 409
    assert accepted.status_code == repeated.status_code == 200
    assert accepted.json()["receipt"]["id"] == repeated.json()["receipt"]["id"]
    saved = client.get(f"/api/tasks/{task['id']}").json()
    assert (saved["estimated_minutes"], saved["remaining_minutes"]) == (75, 75)
    executed = client.get("/api/agent/suggestions", params={"status": "executed"}).json()
    assert any(item["id"] == candidate["suggestion_id"] and item["receipt"] for item in executed)
    recent = client.get("/api/agent/briefing").json()["recent_results"]
    assert any(item["id"] == candidate["suggestion_id"] and item["receipt"] for item in recent)

    stale_task = _create_task(client, name="状态变化估时", due_hours=72)
    stale_briefing = client.post("/api/agent/refresh").json()
    stale = next(item for item in stale_briefing["capacity_action_candidates"] if item["target_id"] == stale_task["id"])
    client.patch(f"/api/tasks/{stale_task['id']}", json={"status": "completed"})
    expired = client.post(
        f"/api/agent/suggestions/{stale['suggestion_id']}/accept",
        json={"estimated_minutes": 90, "idempotency_key": "estimate-stale"},
    )
    assert expired.status_code == 409
    assert expired.json()["error"]["code"] == "SUGGESTION_EXPIRED"


def test_m83_start_task_is_server_controlled(client):
    task = _create_task(client, name="开始受控任务", due_hours=24, estimated_minutes=30)
    briefing = client.post("/api/agent/refresh").json()
    start = next(item for item in briefing["today_actions"] if item["task_id"] == task["id"])
    assert start["controlled_action"] == "start_task"

    accepted = client.post(
        f"/api/agent/suggestions/{start['suggestion_id']}/accept", json={"idempotency_key": "start-controlled"}
    )

    assert accepted.status_code == 200
    assert accepted.json()["receipt"]["applied_payload"] == {"status": "in_progress"}
    assert client.get(f"/api/tasks/{task['id']}").json()["status"] == "in_progress"


def test_m83_today_action_uses_known_workload_for_equal_priority_ordering(client):
    slow = _create_task(client, name="同条件较慢", due_hours=36, estimated_minutes=100)
    fast = _create_task(client, name="同条件较快", due_hours=36, estimated_minutes=30)

    actions = client.get("/api/agent/briefing").json()["today_actions"]
    ordered = [item for item in actions if item["task_id"] in {slow["id"], fast["id"]}]

    assert [item["task_id"] for item in ordered] == [fast["id"], slow["id"]]
    assert ordered[0]["score_components"]["quick_win"] > ordered[1]["score_components"]["quick_win"]
    assert ordered[0]["minute_source"] == "remaining_minutes"


def test_m83_briefing_inbox_only_summarizes_extractable_materials(client):
    material = client.post(
        "/api/materials",
        json={"original_filename": "通知.txt", "extracted_text": "作业截止时间：2026年10月15日"},
    ).json()
    extracted = client.post(f"/api/materials/{material['id']}/extract")
    briefing = client.get("/api/agent/briefing").json()

    assert extracted.status_code == 200
    extraction_status = extracted.json()["status"]
    assert extraction_status in {"ready", "needs_review"}
    assert briefing["inbox"][extraction_status] == {"count": 1, "material_ids": [material["id"]]}
    other = "needs_review" if extraction_status == "ready" else "ready"
    assert briefing["inbox"][other] == {"count": 0, "material_ids": []}
    assert briefing["inbox"]["failed"] == {"count": 0, "material_ids": []}


def test_m83_briefing_uses_one_evaluation_instant(client, monkeypatch):
    from app.api import agent as agent_api

    fixed_now = utc_now()
    calls = []

    def one_now():
        calls.append(True)
        return fixed_now

    monkeypatch.setattr(agent_api, "utc_now", one_now)
    response = client.get("/api/agent/briefing")

    assert response.status_code == 200
    assert len(calls) == 1
    assert response.json()["generated_at"] == fixed_now.isoformat().replace("+00:00", "Z")
    assert response.json()["capacity"]["calculation_basis"]["evaluated_at"] == fixed_now.isoformat().replace("+00:00", "Z")


def test_m83_inbox_failed_merges_processing_and_extraction_without_duplicates():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.api.agent import _inbox_summary
    from app.database import Base
    from app.models.material import Material

    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add_all([
                Material(original_filename="解析失败.txt", processing_status="failed", extraction_status="not_started"),
                Material(original_filename="抽取失败.txt", processing_status="processed", extraction_status="failed"),
                Material(original_filename="双重失败.txt", processing_status="failed", extraction_status="failed"),
            ])
            db.commit()
            failed = _inbox_summary(db)["failed"]
        assert failed == {"count": 3, "material_ids": [1, 2, 3]}
    finally:
        engine.dispose()


def test_m83_today_actions_explain_same_day_deadline_conflict(client):
    first = _create_task(client, name="同日截止一", due_hours=36, estimated_minutes=30)
    second = _create_task(client, name="同日截止二", due_hours=36, estimated_minutes=30)

    actions = client.get("/api/agent/briefing").json()["today_actions"]
    matched = [item for item in actions if item["task_id"] in {first["id"], second["id"]}]

    assert len(matched) == 2
    assert all("same_day_deadline_conflict" in item["reason_codes"] for item in matched)
    assert all("同日有多项截止任务" in " ".join(item["display_reasons"]) for item in matched)
    assert all(item["score_components"]["same_day_deadline_conflict"] == 20 for item in matched)
    assert all(item["score_basis"]["same_day_deadline_conflict"] is True for item in matched)
