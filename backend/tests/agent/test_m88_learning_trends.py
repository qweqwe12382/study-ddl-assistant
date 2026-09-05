from datetime import timedelta

from app.time import utc_now


def _db_from_client(client):
    from app.database import get_db

    generator = client.app.dependency_overrides[get_db]()
    return generator, next(generator)


def test_m88_learning_trends_reports_unknown_without_completion_feedback_or_writes(client):
    from app.models.agent import AgentEvent, AgentReminder, WeeklyReviewSnapshot
    from app.models.calibration import CourseCalibrationState
    from app.models.study_plan import StudyPlan
    from app.models.task import Task

    generator, db = _db_from_client(client)
    try:
        before = {
            "events": db.query(AgentEvent).count(),
            "reminders": db.query(AgentReminder).count(),
            "plans": db.query(StudyPlan).count(),
            "snapshots": db.query(WeeklyReviewSnapshot).count(),
            "calibration_states": db.query(CourseCalibrationState).count(),
            "tasks": db.query(Task).count(),
        }
    finally:
        generator.close()

    response = client.get("/api/agent/learning-trends")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unknown"
    assert body["timezone"] == "Asia/Shanghai"
    assert body["minimum_sample_count"] == 4
    assert body["sample_count"] == body["known_count"] == body["unknown_count"] == 0
    assert len(body["signals"]) == 4
    assert all(signal["status"] == "unknown" for signal in body["signals"])
    assert all(signal["window_start"] and signal["window_end"] and signal["limitations"] is not None for signal in body["signals"])
    assert body["adjustment_candidates"] == []

    generator, db = _db_from_client(client)
    try:
        assert before == {
            "events": db.query(AgentEvent).count(),
            "reminders": db.query(AgentReminder).count(),
            "plans": db.query(StudyPlan).count(),
            "snapshots": db.query(WeeklyReviewSnapshot).count(),
            "calibration_states": db.query(CourseCalibrationState).count(),
            "tasks": db.query(Task).count(),
        }
    finally:
        generator.close()


def test_m88_learning_trends_uses_real_feedback_existing_calibration_and_review_only_candidates(client):
    from app.models.course import Course
    from app.models.task import Task

    now = utc_now()
    generator, db = _db_from_client(client)
    try:
        course = Course(name="趋势证据课程")
        db.add(course)
        db.flush()
        # Four explicit paired samples support the existing per-course
        # calibration, while the large cross-day gap produces a review card.
        for index, offset in enumerate((25, 24, 23, 2)):
            db.add(Task(
                name=f"真实完成-{index}", course_id=course.id, status="completed",
                estimated_minutes=30, actual_minutes=30 + index * 5, difficulty=2 + index % 3,
                completed_at=now - timedelta(days=offset), remaining_minutes=0,
            ))
        db.commit()
    finally:
        generator.close()

    response = client.get("/api/agent/learning-trends")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "known"
    assert body["sample_count"] == body["known_count"] == 4
    assert body["unknown_count"] == 0
    assert body["calculation_basis"]["sample_rule"].startswith("status=completed")
    calibration = body["calibration_context"]
    assert len(calibration) == 1
    assert calibration[0]["course_id"] == course.id
    assert calibration[0]["status"] == "known"
    assert calibration[0]["factor"] == 1.25
    assert calibration[0]["window_start"] == body["window_start"]
    assert calibration[0]["timezone"] == "Asia/Shanghai"
    assert {ref["source_type"] for ref in body["source_refs"]} == {"task"}
    signals = {item["code"]: item for item in body["signals"]}
    assert signals["learning_day_distribution"]["status"] == "known"
    assert signals["longest_idle_gap"]["value"] >= 7
    assert signals["load_concentration"]["value"] is not None
    assert {item["target_id"] for item in body["adjustment_candidates"]} >= {"longest_idle_gap"}
    assert all(item["execution_mode"] == "review" and item["allowed_input"] == {} for item in body["adjustment_candidates"])
    assert all(item["window_start"] == body["window_start"] for item in body["adjustment_candidates"])


def test_m88_learning_trends_keeps_incomplete_feedback_partial_and_never_substitutes_defaults(client):
    from app.models.task import Task

    now = utc_now()
    generator, db = _db_from_client(client)
    try:
        for index in range(4):
            db.add(Task(
                name=f"完整样本-{index}", status="completed", actual_minutes=40, difficulty=3,
                completed_at=now - timedelta(days=index + 1),
            ))
        db.add(Task(name="缺难度", status="completed", actual_minutes=40, completed_at=now - timedelta(days=5)))
        db.add(Task(name="缺完成时间", status="completed", actual_minutes=40, difficulty=3))
        db.commit()
    finally:
        generator.close()

    body = client.get("/api/agent/learning-trends").json()
    assert body["status"] == "partial"
    assert (body["sample_count"], body["known_count"], body["unknown_count"]) == (5, 4, 1)
    assert any("缺少完成时间" in item for item in body["limitations"])
    assert any("未按默认值补齐" in item for item in body["limitations"])
    assert any(ref["snapshot"].get("reason") == "actual_minutes_or_difficulty_missing_or_invalid" for ref in body["source_refs"])


def test_m88_learning_trends_degrades_invalid_persisted_feedback_without_writes(client):
    from app.models.agent import AgentEvent, WeeklyReviewSnapshot
    from app.models.task import Task

    now = utc_now()
    generator, db = _db_from_client(client)
    try:
        for index in range(4):
            db.add(Task(
                name=f"有效反馈-{index}", status="completed", actual_minutes=30, difficulty=3,
                completed_at=now - timedelta(days=index + 1),
            ))
        # These values cannot be entered through the current write contract,
        # but old/manual data must not make this read endpoint fail or get
        # silently corrected by it.
        db.add(Task(
            name="畸形反馈", status="completed", actual_minutes=0, difficulty=9,
            completed_at=now - timedelta(days=5),
        ))
        db.commit()
        before = {
            "events": db.query(AgentEvent).count(),
            "snapshots": db.query(WeeklyReviewSnapshot).count(),
            "tasks": db.query(Task).count(),
        }
    finally:
        generator.close()

    response = client.get("/api/agent/learning-trends")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert (body["sample_count"], body["known_count"], body["unknown_count"]) == (5, 4, 1)
    assert any("无效的实际用时/难度" in item for item in body["limitations"])
    assert any(ref["source_name"] == "畸形反馈" and ref["snapshot"].get("reason") == "actual_minutes_or_difficulty_missing_or_invalid"
               for ref in body["source_refs"])

    generator, db = _db_from_client(client)
    try:
        assert before == {
            "events": db.query(AgentEvent).count(),
            "snapshots": db.query(WeeklyReviewSnapshot).count(),
            "tasks": db.query(Task).count(),
        }
    finally:
        generator.close()


def test_m88_learning_trends_bounds_calibration_contexts_instead_of_failing_response_validation(client):
    from app.models.course import Course
    from app.models.task import Task

    now = utc_now()
    generator, db = _db_from_client(client)
    try:
        courses = [Course(name=f"课程-{index}") for index in range(51)]
        db.add_all(courses)
        db.flush()
        db.add_all([
            Task(
                name=f"课程反馈-{index}", course_id=course.id, status="completed", actual_minutes=30,
                difficulty=3, completed_at=now - timedelta(days=index % 7 + 1),
            )
            for index, course in enumerate(courses)
        ])
        db.commit()
    finally:
        generator.close()

    response = client.get("/api/agent/learning-trends")
    assert response.status_code == 200
    body = response.json()
    assert len(body["calibration_context"]) == 50
    assert body["status"] == "partial"
    assert any("仅按课程标识排序展示前 50 个" in item for item in body["limitations"])
