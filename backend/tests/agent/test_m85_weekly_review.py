from datetime import datetime, time, timedelta, timezone

from app.time import LOCAL_TIMEZONE, utc_now


def _db_from_client(client):
    from app.database import get_db

    generator = client.app.dependency_overrides[get_db]()
    return generator, next(generator)


def _fixed_now():
    return datetime(2026, 8, 22, 4, 0, tzinfo=timezone.utc)  # 12:00 China time


def test_m85_empty_review_has_explicit_zero_and_unknown_evidence(client):
    from app.services.weekly_review import build_weekly_review

    generator, db = _db_from_client(client)
    try:
        review = build_weekly_review(db, evaluated_at=_fixed_now())
    finally:
        generator.close()
    assert review["timezone"] == "Asia/Shanghai"
    assert review["window_start"].isoformat() == "2026-08-15T16:00:00+00:00"
    assert review["window_end"].isoformat() == "2026-08-22T16:00:00+00:00"
    assert review["completed_tasks"]["status"] == "known"
    assert review["completed_tasks"]["value"] == 0
    assert review["completed_tasks"]["source_refs"] == []
    assert review["overdue_tasks"]["status"] == "known"
    assert review["overdue_tasks"]["value"] == 0
    assert review["review_materials"]["status"] == "known"
    assert review["review_materials"]["value"] == 0
    assert review["estimate_variance"]["status"] == "unknown"
    assert review["next_week_actions"] == []


def test_m85_weekly_review_keeps_boundaries_sources_and_missing_variance_honest(client):
    from app.models.agent import ActionReceipt, AgentSuggestion
    from app.models.material import Material
    from app.models.study_plan import StudyPlan
    from app.models.task import Task
    from app.schemas.study_plan import StudyPlanItem
    from app.services.study_plan import encode_plan_content
    from app.services.weekly_review import build_weekly_review

    generator, db = _db_from_client(client)
    try:
        now = _fixed_now()
        start = datetime(2026, 8, 15, 16, 0, tzinfo=timezone.utc)
        end = datetime(2026, 8, 22, 16, 0, tzinfo=timezone.utc)
        completed = Task(name="边界内完成", status="completed", estimated_minutes=60, actual_minutes=90,
                         remaining_minutes=0, completed_at=start, due_at=start + timedelta(days=1))
        missing = Task(name="无反馈完成", status="completed", estimated_minutes=30, remaining_minutes=0,
                       completed_at=start + timedelta(minutes=1), due_at=start + timedelta(days=1))
        excluded = Task(name="边界外完成", status="completed", estimated_minutes=20, actual_minutes=20,
                        remaining_minutes=0, completed_at=end, due_at=start + timedelta(days=1))
        overdue = Task(name="未完成逾期", status="not_started", due_at=now - timedelta(days=1))
        on_time = Task(name="准时完成", status="completed", due_at=now - timedelta(days=2),
                       completed_at=now - timedelta(days=3))
        db.add_all([completed, missing, excluded, overdue, on_time])
        db.flush()
        item = StudyPlanItem(id="day-1", date=now.astimezone(LOCAL_TIMEZONE).date() - timedelta(days=2),
                             phase="复习", title="逾期计划项", content="复习", minutes=45, status="not_started")
        plan = StudyPlan(title="本周计划", status="active", plan_content=encode_plan_content([item], []))
        db.add_all([
            plan,
            Material(original_filename="待复核.txt", processing_status="processed", extraction_status="needs_review"),
            Material(original_filename="失败.txt", processing_status="failed", extraction_status="failed"),
        ])
        db.flush()
        suggestion = AgentSuggestion(action_type="complete_task", status="executed", source_type="task", source_id=completed.id,
                                     source_name=completed.name, title="完成", explanation="", reason_code="completion_quick",
                                     current_payload={}, proposed_payload={}, risk_level="low", confidence=1,
                                     expires_at=now, fingerprint="weekly-receipt")
        db.add(suggestion); db.flush()
        db.add(ActionReceipt(suggestion_id=suggestion.id, action_type="complete_task", source_type="task", source_id=completed.id,
                             outcome="executed", applied_payload={}, before_payload={}, after_payload={}, message="完成", executed_at=now))
        db.commit()

        review = build_weekly_review(db, evaluated_at=now)
    finally:
        generator.close()

    assert review["completed_tasks"]["count"] == 3
    assert review["completed_tasks"]["source_refs"][0]["source_id"] == completed.id
    assert review["estimate_variance"]["value"] == 30
    assert review["estimate_variance"]["status"] == "partial"
    assert review["estimate_variance"]["unknown_count"] == 2
    assert review["overdue_tasks"]["count"] == 1
    assert review["overdue_tasks"]["source_refs"][0]["source_id"] == overdue.id
    assert review["plan_item_status"]["calculation_basis"]["current_delayed_item_count"] == 1
    assert "current statuses" in review["plan_item_status"]["calculation_basis"]["formula"]
    assert review["review_materials"]["count"] == review["failed_materials"]["count"] == 1
    assert review["execution_receipts"]["count"] == 1
    assert review["execution_receipts"]["source_refs"][0]["snapshot"]["suggestion_id"] == suggestion.id
    assert review["estimate_variance"]["sample_count"] == 1
    assert review["estimate_variance"]["missing_count"] == 2
    assert review["estimate_variance"]["direction"] == "overrun"


def test_m85_actions_are_bounded_to_existing_candidates_or_fixed_review_cards(client):
    from app.models.task import Task
    from app.services.agent import refresh_suggestions
    from app.services.weekly_review import build_weekly_review

    generator, db = _db_from_client(client)
    try:
        now = _fixed_now()
        for index in range(5):
            db.add(Task(name=f"临期-{index}", status="not_started", priority=3, estimated_minutes=30,
                        remaining_minutes=30, due_at=now + timedelta(hours=12 + index)))
        db.add(Task(name="本周逾期", status="not_started", due_at=now - timedelta(days=1)))
        db.commit()
        refresh_suggestions(db, now=now)
        review = build_weekly_review(db, evaluated_at=now)
    finally:
        generator.close()
    actions = review["next_week_actions"]
    assert len(actions) == 3
    assert {action["execution_mode"] for action in actions} <= {"accept", "review", "navigate"}
    assert all(
        (action["execution_mode"] == "accept" and action["suggestion_id"] is not None)
        or action["action_type"] in {"review_overdue_tasks", "review_plan_delays", "review_material_inbox"}
        for action in actions
    )
    assert all(not action.get("allowed_input") for action in actions)


def test_m85_historical_completion_and_negative_variance_remain_explicit(client):
    from app.models.task import Task
    from app.services.weekly_review import build_weekly_review

    generator, db = _db_from_client(client)
    try:
        now = _fixed_now()
        db.add_all([
            Task(name="旧记录无完成时刻", status="completed", estimated_minutes=100, actual_minutes=60),
            Task(name="本周实际更短", status="completed", estimated_minutes=100, actual_minutes=40,
                 completed_at=now - timedelta(hours=1)),
        ])
        db.commit()
        review = build_weekly_review(db, evaluated_at=now)
    finally:
        generator.close()
    assert review["completed_tasks"]["count"] == 2
    assert review["completed_tasks"]["known_count"] == 1
    assert review["completed_tasks"]["unknown_count"] == 1
    assert review["completed_tasks"]["status"] == "partial"
    assert review["estimate_variance"]["value"] == -60
    assert review["estimate_variance"]["direction"] == "underrun"
    assert review["estimate_variance"]["sample_count"] == 1


def test_m85_capacity_reminder_uses_existing_capacity_and_does_not_invent_minutes(client):
    from app.models.study_preference import StudyPreference
    from app.models.task import Task
    from app.services.weekly_review import build_weekly_review, sync_weekly_reminders

    generator, db = _db_from_client(client)
    try:
        now = _fixed_now()
        # Explicit capacity configuration is persisted before review; one task
        # has no estimate and must remain null in the reminder source evidence.
        preference = db.get(StudyPreference, 1)
        if preference is None:
            preference = StudyPreference(id=1, weekly_available_minutes=300, daily_limit_minutes=60, buffer_ratio=0)
            db.add(preference)
        else:
            preference.weekly_available_minutes = 300; preference.daily_limit_minutes = 60; preference.buffer_ratio = 0
        known = Task(name="已知超载", status="not_started", estimated_minutes=100, remaining_minutes=100, due_at=now + timedelta(hours=24))
        missing = Task(name="缺失估时", status="not_started", due_at=now + timedelta(hours=25))
        db.add_all([known, missing]); db.commit()
        review = build_weekly_review(db, evaluated_at=now)
        reminders = sync_weekly_reminders(db, review, evaluated_at=now)
    finally:
        generator.close()
    capacity = review["calculation_basis"]["capacity_snapshot"]
    assert capacity["risk_level"] == "high"
    reminder = next(item for item in reminders if item.reason_code == "capacity_overload")
    missing_ref = next(item for item in reminder.source_refs if item["source_id"] == missing.id)
    assert missing_ref["snapshot"]["counted_minutes"] is None
    assert missing.id in reminder.calculation_basis["missing_estimate_task_ids"]


def test_m85_reminders_are_deduplicated_dismissible_and_preserve_source_state(client):
    from app.services.weekly_review import build_weekly_review, sync_weekly_reminders
    from app.models.task import Task

    generator, db = _db_from_client(client)
    try:
        now = _fixed_now()
        task = Task(name="提醒来源", status="not_started", due_at=now - timedelta(hours=1))
        db.add(task); db.commit()
        review = build_weekly_review(db, evaluated_at=now)
        first = sync_weekly_reminders(db, review, evaluated_at=now)
        second = sync_weekly_reminders(db, review, evaluated_at=now)
        assert len(first) == len(second) == 1
        assert [item.id for item in first] == [item.id for item in second]
        repeated_review = build_weekly_review(db, evaluated_at=now)
        assert repeated_review["overdue_tasks"]["source_refs"] == review["overdue_tasks"]["source_refs"]
        assert repeated_review["next_week_actions"] == review["next_week_actions"]
        reminder_id = first[0].id
    finally:
        generator.close()

    dismissed = client.post(f"/api/agent/reminders/{reminder_id}/dismiss", json={"reason": "本周稍后处理"})
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"
    assert dismissed.json()["reason_code"] == "weekly_overdue_tasks"
    assert dismissed.json()["source_refs"][0]["source_type"] == "task"
    repeated = client.post(f"/api/agent/reminders/{reminder_id}/dismiss", json={"reason": "网络重试"})
    assert repeated.status_code == 200
    assert repeated.json()["id"] == reminder_id
    assert repeated.json()["dismissal_reason"] == "本周稍后处理"
    # Refreshing exactly the same evidence must not resurrect the ignored item.
    generator, db = _db_from_client(client)
    try:
        review = build_weekly_review(db, evaluated_at=now)
        assert sync_weekly_reminders(db, review, evaluated_at=now) == []
    finally:
        generator.close()
    assert client.get("/api/agent/reminders", params={"status": "dismissed"}).json()[0]["id"] == reminder_id


def test_m85_briefing_includes_review_and_only_active_reminders(client):
    task = client.post("/api/tasks", json={
        "name": "首页提醒来源", "due_at": (utc_now() - timedelta(hours=1)).isoformat(),
    }).json()
    briefing = client.get("/api/agent/briefing")
    assert briefing.status_code == 200
    body = briefing.json()
    assert body["weekly_review"]["timezone"] == "Asia/Shanghai"
    assert body["weekly_review"]["overdue_tasks"]["count"] == 1
    reminder = next(item for item in body["reminders"] if item["reason_code"] == "weekly_overdue_tasks")
    assert reminder["source_refs"][0]["source_id"] == task["id"]
    direct_review = client.get("/api/agent/weekly-review")
    assert direct_review.status_code == 200
    assert direct_review.json()["calculation_basis"]["timezone"] == "Asia/Shanghai"
