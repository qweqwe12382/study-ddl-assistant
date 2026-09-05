"""Student UX iteration: study streak and semester start date."""

from datetime import date, timedelta

from app.services.study_streak import compute_study_streak


def _days(*offsets: int, today: date) -> set[date]:
    return {today - timedelta(days=offset) for offset in offsets}


def test_streak_empty_and_broken():
    today = date(2026, 9, 5)
    assert compute_study_streak(set(), today) == 0
    assert compute_study_streak(_days(3, 4, 5, today=today), today) == 0


def test_streak_today_extends_run():
    today = date(2026, 9, 5)
    assert compute_study_streak(_days(0, today=today), today) == 1
    assert compute_study_streak(_days(0, 1, 2, 5, today=today), today) == 3


def test_streak_survives_until_today_ends():
    today = date(2026, 9, 5)
    # Studied yesterday but nothing yet today: the streak is still alive.
    assert compute_study_streak(_days(1, today=today), today) == 1
    assert compute_study_streak(_days(1, 2, 3, today=today), today) == 3
    # ...but two missed days break it even with an older history.
    assert compute_study_streak(_days(2, 3, 4, today=today), today) == 0


def test_dashboard_reports_streak_after_completion(client):
    created = client.post("/api/tasks", json={"name": "连续学习任务"})
    assert created.status_code == 201
    task_id = created.json()["id"]

    dashboard_before = client.get("/api/dashboard").json()
    assert dashboard_before["study_streak_days"] == 0

    completed = client.post(f"/api/tasks/{task_id}/complete", json={"actual_minutes": 30})
    assert completed.status_code == 200

    dashboard_after = client.get("/api/dashboard").json()
    assert dashboard_after["study_streak_days"] == 1


def test_semester_start_date_roundtrip_and_clearing(client):
    initial = client.get("/api/study-preferences").json()
    assert initial["semester_start_date"] is None

    updated = client.put("/api/study-preferences", json={"semester_start_date": "2026-08-31"})
    assert updated.status_code == 200
    assert updated.json()["semester_start_date"] == "2026-08-31"

    reread = client.get("/api/study-preferences").json()
    assert reread["semester_start_date"] == "2026-08-31"

    cleared = client.put("/api/study-preferences", json={"semester_start_date": None})
    assert cleared.status_code == 200
    assert cleared.json()["semester_start_date"] is None


def test_semester_start_date_rejects_non_date(client):
    rejected = client.put("/api/study-preferences", json={"semester_start_date": "not-a-date"})
    assert rejected.status_code == 422


def test_study_preference_migration_adds_semester_column():
    """Existing workspace databases get the new column from the lightweight migration."""

    from sqlalchemy import create_engine, inspect, text

    from app.database import _apply_study_preference_migrations

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE study_preferences ("
            "id INTEGER PRIMARY KEY CHECK (id = 1), "
            "weekly_available_minutes INTEGER NOT NULL DEFAULT 1200, "
            "daily_limit_minutes INTEGER NOT NULL DEFAULT 240, "
            "buffer_ratio FLOAT NOT NULL DEFAULT 0.15, "
            "preferred_time_slots JSON NOT NULL DEFAULT '[\"evening\"]', "
            "course_weights JSON NOT NULL DEFAULT '{}')"
        ))
    with engine.begin() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        _apply_study_preference_migrations(connection)
    columns = {column["name"] for column in inspect(engine).get_columns("study_preferences")}
    assert "semester_start_date" in columns
