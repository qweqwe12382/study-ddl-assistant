from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.time import utc_now

def _db_from_client(client):
    from app.database import get_db

    generator = client.app.dependency_overrides[get_db]()
    return generator, next(generator)


def _fixed_now():
    return datetime(2026, 8, 22, 4, 0, tzinfo=timezone.utc)  # 12:00 China time


def test_m86_current_review_materializes_one_truthful_same_window_snapshot(client):
    from app.models.task import Task
    from app.services.weekly_review import build_weekly_review
    from app.services.weekly_review_history import materialize_weekly_review, snapshot_read

    generator, db = _db_from_client(client)
    try:
        # The HTTP refresh below evaluates the real current window.  Use the
        # same current instant for the seeded snapshot so this test verifies
        # idempotency rather than relying on 2026-08-22 remaining current.
        now = utc_now()
        task = Task(
            name="可追溯完成任务", status="completed", estimated_minutes=45, actual_minutes=60,
            remaining_minutes=0, completed_at=now - timedelta(hours=1), due_at=now,
        )
        db.add(task)
        db.commit()
        review = build_weekly_review(db, evaluated_at=now)
        first = materialize_weekly_review(db, review, evaluated_at=now)
        # Retrying the same current window must update the same durable row,
        # not create a duplicate or fabricate a different weekly record.
        second = materialize_weekly_review(db, review, evaluated_at=now)
        payload = snapshot_read(second)
    finally:
        generator.close()

    assert first.id == second.id
    assert payload["review"]["completed_tasks"]["source_refs"][0]["source_id"] == task.id
    assert payload["review"]["calculation_basis"]["window_semantics"].startswith("seven China-local")
    assert len(client.get("/api/agent/weekly-reviews").json()["items"]) == 1
    refresh_one = client.post("/api/agent/weekly-review/refresh")
    refresh_two = client.post("/api/agent/weekly-review/refresh")
    assert refresh_one.status_code == refresh_two.status_code == 200
    assert refresh_one.json()["id"] == refresh_two.json()["id"]
    assert refresh_one.json()["evidence_digest"] == refresh_two.json()["evidence_digest"]
    assert len(client.get("/api/agent/weekly-reviews").json()["items"]) == 1


def test_m86_history_keeps_only_actual_windows_and_bounds_retention(client):
    from app.models.agent import WeeklyReviewSnapshot
    from app.services.weekly_review import build_weekly_review
    from app.services.weekly_review_history import WEEKLY_REVIEW_RETENTION_LIMIT, materialize_weekly_review

    generator, db = _db_from_client(client)
    try:
        latest = _fixed_now()
        # Calling the materializer on spaced evaluation instants creates only
        # those 13 concrete windows; it never fills the missing weeks between.
        for index in reversed(range(WEEKLY_REVIEW_RETENTION_LIMIT + 1)):
            now = latest - timedelta(days=index * 7)
            materialize_weekly_review(db, build_weekly_review(db, evaluated_at=now), evaluated_at=now)
        snapshots = list(db.scalars(select(WeeklyReviewSnapshot).order_by(WeeklyReviewSnapshot.window_end.desc())).all())
    finally:
        generator.close()

    assert len(snapshots) == WEEKLY_REVIEW_RETENTION_LIMIT
    assert all(".." in row.window_key for row in snapshots)
    history = client.get("/api/agent/weekly-reviews", params={"limit": 99})
    assert history.status_code == 422
    body = client.get("/api/agent/weekly-reviews", params={"limit": 2}).json()
    assert len(body["items"]) == 2
    assert {item["snapshot_status"] for item in body["items"]} <= {"current", "closed"}
    assert all(item["ruleset_version"] == "m8.6" for item in body["items"])
    assert body["retention_limit"] == WEEKLY_REVIEW_RETENTION_LIMIT
    assert "no missing windows are fabricated" in body["calculation_basis"]["storage_semantics"]


def test_m86_reminder_preferences_are_whitelisted_and_never_silently_hide_high_risk(client):
    from app.models.agent import AgentReminder

    generator, db = _db_from_client(client)
    try:
        now = _fixed_now()
        high = AgentReminder(
            status="active", risk_level="high", reason_code="weekly_overdue_tasks",
            source_type="task_collection", source_id="overdue", title="高风险事实", explanation="需人工处理",
            source_refs=[], calculation_basis={"source": "test"}, fingerprint="m86-high",
            created_at=now, updated_at=now,
        )
        medium = AgentReminder(
            status="active", risk_level="medium", reason_code="estimate_variance_trend",
            source_type="task_collection", source_id="variance", title="中风险提示", explanation="可复盘",
            source_refs=[], calculation_basis={"source": "test"}, fingerprint="m86-medium",
            created_at=now, updated_at=now,
        )
        db.add_all([high, medium])
        db.commit()
        high_id, medium_id = high.id, medium.id
    finally:
        generator.close()

    invalid = client.patch("/api/agent/reminder-preferences", json={"arbitrary": "nope"})
    assert invalid.status_code == 422
    duplicate = client.patch("/api/agent/reminder-preferences", json={"enabled_categories": ["plans", "plans"]})
    assert duplicate.status_code == 422
    updated = client.patch("/api/agent/reminder-preferences", json={
        "enabled_categories": [], "minimum_risk_level": "high", "digest_frequency": "weekly",
    })
    assert updated.status_code == 200
    assert updated.json()["high_risk_policy"] == "always_presented"
    assert updated.json()["digest_frequency"] == "weekly"

    # The full endpoint remains a record/audit view, while presentation opts
    # into the preference.  High factual evidence survives an empty category
    # set and a restrictive threshold.
    raw_ids = {item["id"] for item in client.get("/api/agent/reminders").json()}
    visible_ids = {item["id"] for item in client.get("/api/agent/reminders", params={"presentation": "true"}).json()}
    assert {high_id, medium_id} <= raw_ids
    assert high_id in visible_ids
    assert medium_id not in visible_ids

    # Explicit user dismissal remains the only way this high-risk reminder is
    # removed from the active presentation; repeated dismissal stays idempotent.
    dismissed = client.post(f"/api/agent/reminders/{high_id}/dismiss", json={"reason": "已知悉"})
    assert dismissed.status_code == 200
    assert client.post(f"/api/agent/reminders/{high_id}/dismiss", json={"reason": "重试"}).status_code == 200
    visible_after_dismiss = {item["id"] for item in client.get("/api/agent/reminders", params={"presentation": "true"}).json()}
    assert high_id not in visible_after_dismiss
    assert client.get("/api/agent/reminders", params={"status": "dismissed"}).json()[0]["id"] == high_id


def test_m86_briefing_exposes_preference_contract_without_changing_raw_review(client):
    preferences = client.get("/api/agent/reminder-preferences")
    assert preferences.status_code == 200
    assert preferences.json()["enabled_categories"] == ["deadlines", "plans", "materials", "estimation", "capacity"]
    assert preferences.json()["minimum_risk_level"] == "low"
    assert preferences.json()["digest_frequency"] == "immediate"

    briefing = client.get("/api/agent/briefing")
    assert briefing.status_code == 200
    assert briefing.json()["reminder_preferences"]["high_risk_policy"] == "always_presented"
    assert briefing.json()["reminder_presentation"]["presentation_scope"].startswith("in-app Agent Center")
    assert briefing.json()["weekly_review"]["timezone"] == "Asia/Shanghai"
    assert client.get("/api/agent/weekly-review").status_code == 200


def test_m86_daily_digest_frequency_is_consumed_server_side_but_high_risk_stays_visible(client):
    from app.models.task import Task

    generator, db = _db_from_client(client)
    try:
        now = utc_now()
        # These rows produce the ordinary M8.5 high overdue and medium
        # estimate-variance candidates.  Directly inserted reminders would be
        # correctly resolved by sync as unsupported evidence, so they would not
        # prove the actual page/refresh digest path.
        db.add(Task(name="真实逾期", status="not_started", due_at=now - timedelta(hours=1)))
        for index in range(3):
            db.add(Task(
                name=f"真实估时偏差-{index}", status="completed", estimated_minutes=30, actual_minutes=90,
                remaining_minutes=0, completed_at=now - timedelta(minutes=index + 1),
            ))
        db.commit()
    finally:
        generator.close()

    assert client.patch("/api/agent/reminder-preferences", json={"digest_frequency": "daily"}).status_code == 200
    first = client.get("/api/agent/briefing").json()
    second = client.get("/api/agent/briefing").json()
    assert {item["risk_level"] for item in first["reminders"]} == {"high", "medium"}
    assert first["reminder_presentation"]["digest_frequency"] == "daily"
    assert first["reminder_presentation"]["digest_consumed"] is True
    assert {item["risk_level"] for item in second["reminders"]} == {"high"}
    assert second["reminder_presentation"]["noncritical_digest_eligible"] is False
    assert second["reminder_presentation"]["high_risk_policy"] == "always_presented"


def test_m86_closed_history_freezes_payload_and_snapshot_storage_is_bounded(client):
    from app.models.task import Task
    from app.services.weekly_review import build_weekly_review
    from app.services.weekly_review_history import (
        MAX_SNAPSHOT_SOURCE_REFS,
        _snapshot_payload,
        materialize_weekly_review,
        snapshot_read,
    )

    generator, db = _db_from_client(client)
    try:
        now = _fixed_now()
        original_task = Task(name="最初事实", status="completed", estimated_minutes=30, actual_minutes=30,
                             completed_at=now - timedelta(hours=1))
        db.add(original_task)
        db.commit()
        original_review = build_weekly_review(db, evaluated_at=now)
        snapshot = materialize_weekly_review(db, original_review, evaluated_at=now)
        original = snapshot_read(snapshot)

        db.add(Task(name="稍后才出现的事实", status="completed", estimated_minutes=20, actual_minutes=40,
                    completed_at=now - timedelta(minutes=30)))
        db.commit()
        changed_review = build_weekly_review(db, evaluated_at=now)
        frozen = materialize_weekly_review(db, changed_review, evaluated_at=original_review["window_end"])
        frozen_read = snapshot_read(frozen)
    finally:
        generator.close()

    assert frozen_read["snapshot_status"] == "closed"
    assert frozen_read["ruleset_version"] == "m8.6"
    assert frozen_read["evidence_digest"] == original["evidence_digest"]
    assert frozen_read["review"] == original["review"]

    raw = {
        "window_start": now, "window_end": now + timedelta(days=7), "evaluated_at": now,
        "calculation_basis": {"capacity_snapshot": {"tasks": []}},
        "completed_tasks": {
            "source_refs": [{"source_type": "task", "source_id": index, "source_name": "x" * 800,
                             "snapshot": {"secret_token": "must-not-persist", "parsed_text": "must-not-persist"}}
                            for index in range(MAX_SNAPSHOT_SOURCE_REFS + 5)],
        },
    }
    bounded = _snapshot_payload(raw)
    refs = bounded["completed_tasks"]["source_refs"]
    assert len(refs) == MAX_SNAPSHOT_SOURCE_REFS
    assert "secret_token" not in refs[0]["snapshot"]
    assert "parsed_text" not in refs[0]["snapshot"]
    assert len(refs[0]["source_name"]) <= 501
    assert bounded["calculation_basis"]["snapshot_storage"]["source_refs_omitted"] == 5
