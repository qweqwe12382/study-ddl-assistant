from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

from app.time import utc_now


def _db_from_client(client):
    from app.database import get_db

    generator = client.app.dependency_overrides[get_db]()
    return generator, next(generator)


def _materialize(db, *, evaluated_at):
    from app.services.weekly_review import build_weekly_review
    from app.services.weekly_review_history import materialize_weekly_review

    return materialize_weekly_review(
        db, build_weekly_review(db, evaluated_at=evaluated_at), evaluated_at=evaluated_at
    )


def _add_eligible_tasks(db, *, prefix: str, completed_at, count: int = 4):
    from app.models.task import Task

    for index in range(count):
        db.add(Task(
            name=f"{prefix}-{index}", status="completed", actual_minutes=30 + index,
            difficulty=2 + index % 3, remaining_minutes=0,
            completed_at=completed_at + timedelta(days=index),
        ))
    db.commit()


def _two_closed_snapshots(db, *, task_count: int = 4):
    """Create two closed snapshots and one excluded current snapshot."""

    now = utc_now()
    older_at, newer_at = now - timedelta(days=14), now - timedelta(days=7)
    _add_eligible_tasks(db, prefix="older", completed_at=now - timedelta(days=25), count=task_count)
    older = _materialize(db, evaluated_at=older_at)
    _add_eligible_tasks(db, prefix="newer", completed_at=now - timedelta(days=12), count=task_count)
    newer = _materialize(db, evaluated_at=newer_at)
    current = _materialize(db, evaluated_at=now)
    db.refresh(older)
    db.refresh(newer)
    db.refresh(current)
    assert older.snapshot_status == newer.snapshot_status == "closed"
    assert current.snapshot_status == "current"
    return older, newer, current


def test_m89_current_summary_updates_then_closed_summary_never_rewrites(client):
    from app.models.agent import WeeklyReviewSnapshot
    from app.models.task import Task
    from app.services.weekly_review import build_weekly_review
    from app.services.weekly_review_history import materialize_weekly_review

    now = utc_now()
    generator, db = _db_from_client(client)
    try:
        _add_eligible_tasks(db, prefix="initial", completed_at=now - timedelta(days=4))
        initial_review = build_weekly_review(db, evaluated_at=now)
        current = materialize_weekly_review(db, initial_review, evaluated_at=now)
        initial_summary = deepcopy(current.rhythm_summary)

        db.add(Task(
            name="only-current-refresh", status="completed", actual_minutes=75, difficulty=5,
            remaining_minutes=0, completed_at=now - timedelta(hours=1),
        ))
        db.commit()
        refreshed = materialize_weekly_review(
            db, build_weekly_review(db, evaluated_at=now), evaluated_at=now
        )
        refreshed_summary = deepcopy(refreshed.rhythm_summary)
        assert refreshed.snapshot_status == "current"
        assert refreshed_summary["sample_count"] == initial_summary["sample_count"] + 1
        assert refreshed_summary["summary_version"] == "m8.9.m8.8-rhythm-v1"
        assert "only-current-refresh" not in str(refreshed_summary)

        # Moving into the next weekly window closes the old row without
        # recalculating it at the boundary.
        _materialize(db, evaluated_at=initial_review["window_end"])
        frozen = db.get(WeeklyReviewSnapshot, current.id)
        assert frozen.snapshot_status == "closed"
        frozen_summary = deepcopy(frozen.rhythm_summary)

        db.add(Task(
            name="would-change-live-trend", status="completed", actual_minutes=120, difficulty=5,
            remaining_minutes=0, completed_at=now - timedelta(minutes=30),
        ))
        db.commit()
        materialize_weekly_review(db, build_weekly_review(db, evaluated_at=now), evaluated_at=now)
        db.refresh(frozen)
        assert frozen.rhythm_summary == frozen_summary
    finally:
        generator.close()


def test_m89_compares_two_same_version_closed_summaries_and_excludes_current(client):
    from app.models.agent import AgentEvent, WeeklyReviewSnapshot
    from app.models.calibration import CourseCalibrationState
    from app.models.study_plan import StudyPlan
    from app.models.task import Task

    generator, db = _db_from_client(client)
    try:
        older, newer, current = _two_closed_snapshots(db)
        before = {
            "snapshots": db.query(WeeklyReviewSnapshot).count(),
            "events": db.query(AgentEvent).count(),
            "plans": db.query(StudyPlan).count(),
            "calibrations": db.query(CourseCalibrationState).count(),
            "tasks": db.query(Task).count(),
        }
    finally:
        generator.close()

    response = client.get("/api/agent/learning-rhythm-history")
    assert response.status_code == 200
    body = response.json()
    comparison = body["comparison"]
    assert body["status"] == comparison["status"] == "known"
    assert comparison["comparable"] is True
    assert comparison["compared_snapshot_ids"] == [newer.id, older.id]
    assert current.id not in comparison["compared_snapshot_ids"]
    assert comparison["source_refs"] == body["source_refs"] == []
    assert comparison["known_count"] >= 8
    assert comparison["calculation_basis"]["summary_version"] == "m8.9.m8.8-rhythm-v1"
    assert len(comparison["calculation_basis"]["changes"]) == 4
    assert all(item["rhythm_summary_version"] == "m8.9.m8.8-rhythm-v1" for item in body["available_windows"])

    generator, db = _db_from_client(client)
    try:
        assert before == {
            "snapshots": db.query(WeeklyReviewSnapshot).count(),
            "events": db.query(AgentEvent).count(),
            "plans": db.query(StudyPlan).count(),
            "calibrations": db.query(CourseCalibrationState).count(),
            "tasks": db.query(Task).count(),
        }
    finally:
        generator.close()


def test_m89_legacy_closed_snapshot_is_explicitly_not_comparable(client):
    generator, db = _db_from_client(client)
    try:
        older, newer, _current = _two_closed_snapshots(db)
        # This models a real M8.6 row after the additive column migration:
        # its JSON default is empty, rather than a reconstructed M8.9 value.
        older.rhythm_summary = {}
        db.commit()
    finally:
        generator.close()

    body = client.get("/api/agent/learning-rhythm-history").json()
    assert body["status"] == "unknown"
    assert body["comparison"]["comparable"] is False
    assert body["comparison"]["reason_codes"] == ["legacy_snapshot_missing_rhythm_summary"]
    assert body["comparison"]["compared_snapshot_ids"] == [newer.id, older.id]
    assert body["source_refs"] == []


def test_m89_mismatched_summary_caliber_is_explicitly_not_comparable(client):
    generator, db = _db_from_client(client)
    try:
        older, newer, _current = _two_closed_snapshots(db)
        # A future version must not silently compare against the first M8.9
        # definition, even if its raw signal field names happen to match.
        newer.rhythm_summary = {**newer.rhythm_summary, "summary_version": "future-rhythm-v2"}
        db.commit()
    finally:
        generator.close()

    body = client.get("/api/agent/learning-rhythm-history").json()
    assert body["status"] == "unknown"
    assert body["comparison"]["comparable"] is False
    assert body["comparison"]["reason_codes"] == ["rhythm_summary_caliber_mismatch"]
    assert body["comparison"]["compared_snapshot_ids"] == [newer.id, older.id]


def test_m89_malformed_persisted_summary_degrades_to_not_comparable_without_repair_writes(client):
    from app.models.agent import AgentEvent, WeeklyReviewSnapshot

    generator, db = _db_from_client(client)
    try:
        _older, newer, _current = _two_closed_snapshots(db)
        newer.rhythm_summary = {**newer.rhythm_summary, "signals": "not-a-signal-map", "unknown_count": []}
        db.commit()
        before = {
            "snapshots": db.query(WeeklyReviewSnapshot).count(),
            "events": db.query(AgentEvent).count(),
            "summary": newer.rhythm_summary,
        }
    finally:
        generator.close()

    response = client.get("/api/agent/learning-rhythm-history")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unknown"
    assert body["comparison"]["comparable"] is False
    assert body["comparison"]["reason_codes"] == ["invalid_rhythm_summary"]

    generator, db = _db_from_client(client)
    try:
        stored = db.get(WeeklyReviewSnapshot, newer.id)
        assert db.query(WeeklyReviewSnapshot).count() == before["snapshots"]
        assert db.query(AgentEvent).count() == before["events"]
        assert stored.rhythm_summary == before["summary"]
    finally:
        generator.close()


def test_m89_insufficient_persisted_summary_samples_are_not_comparable(client):
    generator, db = _db_from_client(client)
    try:
        _two_closed_snapshots(db, task_count=3)
    finally:
        generator.close()

    body = client.get("/api/agent/learning-rhythm-history").json()
    assert body["status"] == "unknown"
    assert body["comparison"]["comparable"] is False
    assert body["comparison"]["reason_codes"] == ["insufficient_rhythm_summary_samples"]
    # The newer 28-day observation sees both real task groups (3 + 3), while
    # the older one sees its own three; each individual summary is still below
    # the minimum and must not be rescued by combining them.
    assert body["comparison"]["known_count"] == 9
    assert body["calculation_basis"]["read_only"] is True
