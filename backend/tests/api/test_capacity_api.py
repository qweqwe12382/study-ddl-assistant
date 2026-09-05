from datetime import datetime, time, timedelta

from app.time import LOCAL_TIMEZONE, as_local, deadline_to_utc, utc_now


def _create_task(
    client, *, name: str, due_hours: float = 24, due_at: datetime | None = None,
    estimated_minutes=None, remaining_minutes=None, status="not_started",
):
    payload = {
        "name": name,
        "due_at": (due_at or (utc_now() + timedelta(hours=due_hours))).isoformat(),
        "status": status,
    }
    if estimated_minutes is not None:
        payload["estimated_minutes"] = estimated_minutes
    if remaining_minutes is not None:
        payload["remaining_minutes"] = remaining_minutes
    response = client.post("/api/tasks", json=payload)
    assert response.status_code == 201
    return response.json()


def test_study_preferences_are_created_updated_and_reset(client):
    default = client.get("/api/study-preferences")
    updated = client.put(
        "/api/study-preferences",
        json={
            "weekly_available_minutes": 600,
            "daily_limit_minutes": 120,
            "buffer_ratio": 0.2,
            "preferred_time_slots": ["morning", "morning", "evening"],
            "course_weights": {"1": 1.5},
        },
    )
    reset = client.post("/api/study-preferences/reset")

    assert default.status_code == 200
    assert default.json()["weekly_available_minutes"] == 1200
    assert default.json()["preferred_time_slots"] == ["evening"]
    assert updated.status_code == 200
    assert updated.json()["weekly_available_minutes"] == 600
    assert updated.json()["preferred_time_slots"] == ["morning", "evening"]
    assert updated.json()["course_weights"] == {"1": 1.5}
    assert reset.status_code == 200
    assert reset.json()["weekly_available_minutes"] == 1200
    assert reset.json()["buffer_ratio"] == 0.15


def test_study_preferences_reject_out_of_range_and_invalid_fields(client):
    too_small = client.put("/api/study-preferences", json={"weekly_available_minutes": 299})
    empty_slots = client.put("/api/study-preferences", json={"preferred_time_slots": []})
    invalid_weight = client.put("/api/study-preferences", json={"course_weights": {"course-a": 1}})
    extra = client.put("/api/study-preferences", json={"unknown": True})
    explicit_null = client.put("/api/study-preferences", json={"daily_limit_minutes": None})

    assert too_small.status_code == 422
    assert empty_slots.status_code == 422
    assert invalid_weight.status_code == 422
    assert extra.status_code == 422
    assert explicit_null.status_code == 422
    assert explicit_null.json()["error"]["code"] == "VALIDATION_ERROR"


def test_task_duration_contract_and_completion_sets_remaining_to_zero(client):
    invalid = client.post(
        "/api/tasks",
        json={"name": "无效时长", "estimated_minutes": 30, "remaining_minutes": 31},
    )
    remaining_only = client.post("/api/tasks", json={"name": "仅剩余时长", "remaining_minutes": 30})
    task = _create_task(client, name="完成后归零", estimated_minutes=90, remaining_minutes=45)
    completed = client.post(f"/api/tasks/{task['id']}/complete")
    created_completed = _create_task(
        client,
        name="初始完成也归零",
        estimated_minutes=60,
        remaining_minutes=30,
        status="completed",
    )
    second = _create_task(client, name="更新完成归零", estimated_minutes=60, remaining_minutes=30)
    updated = client.patch(f"/api/tasks/{second['id']}", json={"status": "completed", "remaining_minutes": 30})
    third = _create_task(client, name="更新时长校验", estimated_minutes=30, remaining_minutes=20)
    invalid_update = client.patch(f"/api/tasks/{third['id']}", json={"estimated_minutes": 15})
    remaining_only_update = client.patch(f"/api/tasks/{third['id']}", json={"estimated_minutes": None, "remaining_minutes": 10})

    assert invalid.status_code == 422
    assert remaining_only.status_code == 422
    assert completed.status_code == 200
    assert completed.json()["remaining_minutes"] == 0
    assert created_completed["remaining_minutes"] == 0
    assert updated.status_code == 200
    assert updated.json()["remaining_minutes"] == 0
    assert invalid_update.status_code == 422
    assert remaining_only_update.status_code == 422


def test_capacity_risk_boundaries_and_same_day_groups(client):
    configured = client.put(
        "/api/study-preferences",
        json={"weekly_available_minutes": 300, "daily_limit_minutes": 240, "buffer_ratio": 0},
    )
    # Construct the pair from one explicit China-local tomorrow rather than
    # adding 12/13 hours independently: the old form crossed midnight when
    # this test ran late in the day and made a same-day assertion flaky.
    tomorrow = as_local(utc_now()).date() + timedelta(days=1)
    first_due = deadline_to_utc(datetime.combine(tomorrow, time(12, 0), tzinfo=LOCAL_TIMEZONE))
    second_due = deadline_to_utc(datetime.combine(tomorrow, time(13, 0), tzinfo=LOCAL_TIMEZONE))
    task = _create_task(client, name="容量边界", estimated_minutes=180, due_at=first_due)
    low = client.get("/api/agent/capacity")
    peer = _create_task(client, name="同日 DDL", estimated_minutes=60, due_at=second_due)
    medium = client.get("/api/agent/capacity")
    high_update = client.patch(f"/api/tasks/{task['id']}", json={"estimated_minutes": 301})
    high = client.get("/api/agent/capacity")

    assert configured.status_code == 200
    assert low.json()["effective_capacity_minutes"] == 300
    assert low.json()["calculation_basis"]["base_capacity_minutes"] == 300
    assert low.json()["known_workload_minutes"] == 180
    assert low.json()["risk_level"] == "low"
    assert medium.json()["known_workload_minutes"] == 240
    assert medium.json()["risk_level"] == "medium"
    assert {item["id"] for item in medium.json()["tasks"]} == {task["id"], peer["id"]}
    assert medium.json()["same_day_deadline_groups"][0]["task_count"] == 2
    assert high_update.status_code == 200
    assert high.json()["risk_level"] == "high"


def test_capacity_reports_missing_estimates_and_ignores_out_of_window_or_completed_tasks(client):
    missing = _create_task(client, name="未估时", due_hours=12)
    _create_task(client, name="窗口外", due_hours=24 * 8, estimated_minutes=1000)
    _create_task(client, name="已完成", due_hours=12, estimated_minutes=1000, status="completed")

    response = client.get("/api/agent/capacity")

    assert response.status_code == 200
    assert response.json()["known_workload_minutes"] == 0
    assert response.json()["missing_estimate_task_ids"] == [missing["id"]]
    assert response.json()["risk_level"] == "unknown"
    assert [item["id"] for item in response.json()["tasks"]] == [missing["id"]]


def test_capacity_is_unknown_when_known_workload_has_any_missing_estimate(client):
    estimated = _create_task(client, name="已估时", due_hours=12, estimated_minutes=100)
    missing = _create_task(client, name="仍未估时", due_hours=13)

    response = client.get("/api/agent/capacity")

    assert response.status_code == 200
    assert response.json()["known_workload_minutes"] == 100
    assert response.json()["missing_estimate_task_ids"] == [missing["id"]]
    assert response.json()["risk_level"] == "unknown"
    assert [item["id"] for item in response.json()["tasks"]] == [estimated["id"], missing["id"]]


def test_task_api_normalizes_naive_shanghai_and_aware_deadlines_to_same_utc_instant(client):
    naive = "2099-01-02T20:00:00"
    aware = "2099-01-02T12:00:00Z"

    first = client.post("/api/tasks", json={"name": "本地输入", "due_at": naive})
    second = client.post("/api/tasks", json={"name": "UTC 输入", "due_at": aware})

    assert first.status_code == second.status_code == 201
    assert first.json()["due_at"] == second.json()["due_at"]
    assert first.json()["due_at"] == deadline_to_utc(datetime.fromisoformat(naive)).isoformat().replace("+00:00", "Z")


def test_extraction_deadline_is_utc_and_capacity_groups_by_shanghai_local_date(client):
    from app.services.extraction import _parse_due_at

    local_date = as_local(utc_now()).date() + timedelta(days=1)
    extracted_due, warnings = _parse_due_at({"due_at": local_date}, "", None)
    local_morning = datetime.combine(local_date, time(9, 0))
    first = client.post(
        "/api/tasks",
        json={"name": "抽取日期等价", "due_at": extracted_due.isoformat(), "estimated_minutes": 30},
    )
    second = client.post(
        "/api/tasks",
        json={
            "name": "同一本地日", "due_at": local_morning.replace(tzinfo=LOCAL_TIMEZONE).isoformat(), "estimated_minutes": 30
        },
    )
    capacity = client.get("/api/agent/capacity")

    assert warnings == []
    assert extracted_due.tzinfo is not None
    assert as_local(extracted_due).date() == local_date
    assert first.status_code == second.status_code == 201
    group = capacity.json()["same_day_deadline_groups"][0]
    assert group["local_date"] == local_date.isoformat()
    assert set(group["task_ids"]) == {first.json()["id"], second.json()["id"]}
    assert capacity.json()["calculation_basis"]["timezone"] == "Asia/Shanghai"


def test_daily_overload_escalates_overall_capacity_risk(client):
    client.put(
        "/api/study-preferences",
        json={"weekly_available_minutes": 10080, "daily_limit_minutes": 30, "buffer_ratio": 0},
    )
    _create_task(client, name="单日超载", due_hours=12, estimated_minutes=40)

    capacity = client.get("/api/agent/capacity").json()

    assert capacity["effective_capacity_minutes"] == 210
    assert capacity["calculation_basis"]["effective_daily_capacity_minutes"] == 30
    assert capacity["risk_level"] == "high"
    assert capacity["daily_risk_groups"][0]["risk_level"] == "high"
    assert capacity["daily_risk_groups"][0]["overload_minutes"] == 10


def test_extraction_confirmation_flows_into_capacity_with_duration_contract(client):
    local_date = as_local(utc_now()).date() + timedelta(days=1)
    material = client.post(
        "/api/materials",
        json={
            "original_filename": "容量抽取通知.txt",
            "extracted_text": f"作业一：提交容量报告，截止时间：{local_date.year}年{local_date.month}月{local_date.day}日 20:00",
        },
    ).json()
    extracted = client.post(f"/api/materials/{material['id']}/extract").json()
    candidate = extracted["tasks"][0]
    invalid_candidate = dict(candidate)
    invalid_candidate["estimated_minutes"] = None
    invalid_candidate["remaining_minutes"] = 30
    invalid = client.post(f"/api/materials/{material['id']}/extraction/confirm", json={"tasks": [invalid_candidate]})
    edited_local_due = datetime.combine(local_date, time(20, 0))
    candidate["due_at"] = edited_local_due.isoformat()
    candidate["estimated_minutes"] = 45
    candidate["remaining_minutes"] = 30
    confirmed = client.post(f"/api/materials/{material['id']}/extraction/confirm", json={"tasks": [candidate]})
    capacity = client.get("/api/agent/capacity").json()

    assert invalid.status_code == 422
    assert confirmed.status_code == 200
    task_id = confirmed.json()["confirmed_task_ids"][0]
    capacity_task = next(item for item in capacity["tasks"] if item["id"] == task_id)
    assert capacity_task["estimated_minutes"] == 45
    assert capacity_task["remaining_minutes"] == 30
    assert capacity_task["counted_minutes"] == 30
    assert capacity_task["due_at"] == deadline_to_utc(edited_local_due).isoformat().replace("+00:00", "Z")


def test_capacity_lightweight_migrations_add_task_and_preference_columns():
    from sqlalchemy import create_engine, inspect, text

    from app.database import _apply_study_preference_migrations, _apply_task_migrations

    legacy_engine = create_engine("sqlite://")
    try:
        with legacy_engine.begin() as connection:
            connection.execute(text("CREATE TABLE tasks (id INTEGER PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE study_preferences (id INTEGER PRIMARY KEY)"))
            _apply_task_migrations(connection)
            _apply_study_preference_migrations(connection)
            inspector = inspect(connection)
            assert {"estimated_minutes", "remaining_minutes"} <= {item["name"] for item in inspector.get_columns("tasks")}
            assert {"weekly_available_minutes", "daily_limit_minutes", "buffer_ratio", "preferred_time_slots", "course_weights"} <= {
                item["name"] for item in inspector.get_columns("study_preferences")
            }
    finally:
        legacy_engine.dispose()
