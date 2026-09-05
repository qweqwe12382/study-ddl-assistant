from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from app.time import utc_now


def _course_and_plan(client):
    course = client.post("/api/courses", json={"name": "M8.4 课程"}).json()
    plan = client.post("/api/study-plans/generate", json={
        "course_id": course["id"], "exam_date": (date.today() + timedelta(days=5)).isoformat(), "daily_minutes": 60,
    }).json()
    return course, plan


def _task(client, course_id, name="任务", estimated=60):
    return client.post("/api/tasks", json={
        "course_id": course_id, "name": name, "estimated_minutes": estimated, "remaining_minutes": estimated,
        "due_at": (utc_now() + timedelta(days=2)).isoformat(),
    }).json()


def test_m84_completion_feedback_is_optional_bounded_idempotent_and_calibrates_after_three_samples(client):
    course, _plan = _course_and_plan(client)
    tasks = [_task(client, course["id"], f"样本-{index}", 100) for index in range(3)]
    for index, (task, actual) in enumerate(zip(tasks, (200, 100, 15))):
        completed = client.post(f"/api/agent/tasks/{task['id']}/complete", json={
            "actual_minutes": actual, "difficulty": index + 2, "idempotency_key": f"feedback-{index}",
        })
        assert completed.status_code == 200
        assert completed.json()["status"] == "executed"
        assert completed.json()["task"]["status"] == "completed"
        assert completed.json()["task"]["actual_minutes"] == actual
        assert completed.json()["receipt"]["outcome"] == "executed"

    duplicate = client.post(f"/api/agent/tasks/{tasks[0]['id']}/complete", json={
        "actual_minutes": 90, "idempotency_key": "feedback-0",
    })
    assert duplicate.status_code == 200
    assert duplicate.json()["task"]["actual_minutes"] == 200
    assert duplicate.json()["receipt"]["applied_payload"]["actual_minutes"] == 200
    calibration = client.get("/api/agent/calibration", params={"course_id": course["id"]})
    assert calibration.status_code == 200
    body = calibration.json()
    assert body["minimum_sample_count"] == 3
    assert body["sample_count"] == 3
    assert body["eligible"] is True
    # 2.0, 1.0 and 0.15 clipped to 0.25 -> median = 1.0
    assert body["factor"] == 1.0
    assert body["ratio_bounds"] == {"minimum": 0.25, "maximum": 4.0}

    regenerated = client.post("/api/study-plans/generate", json={
        "course_id": course["id"], "exam_date": (date.today() + timedelta(days=4)).isoformat(), "daily_minutes": 60,
    })
    assert regenerated.status_code == 201
    assert any("校准系数" in warning for warning in regenerated.json()["warnings"])

    reset = client.post(f"/api/agent/calibration/{course['id']}/reset", json={"idempotency_key": "reset-course"})
    assert reset.status_code == 200
    assert reset.json()["sample_count"] == 0
    # Completion evidence was retained; only the calibration window was reset.
    assert client.get(f"/api/tasks/{tasks[0]['id']}").json()["actual_minutes"] == 200


def test_m84_feedback_fields_cannot_bypass_the_completion_entrypoint(client):
    course, _plan = _course_and_plan(client)
    rejected_create = client.post("/api/tasks", json={"course_id": course["id"], "name": "不可绕过", "actual_minutes": 40})
    assert rejected_create.status_code == 422
    task = _task(client, course["id"], "完成入口", 40)
    rejected_patch = client.patch(f"/api/tasks/{task['id']}", json={"actual_minutes": 40, "difficulty": 3})
    assert rejected_patch.status_code == 422
    # The original route still completes without a body and writes the same
    # durable completion event path as the agent route.
    legacy = client.post(f"/api/tasks/{task['id']}/complete")
    assert legacy.status_code == 200 and legacy.json()["status"] == "completed"


def test_m84_plan_delta_revalidates_snapshot_and_preserves_manual_or_completed_items(client):
    course, plan = _course_and_plan(client)
    task = _task(client, course["id"], "新增任务", 45)
    deltas = client.get("/api/agent/plan-deltas").json()
    candidate = next(item for item in deltas if item["current_payload"]["task_id"] == task["id"])
    briefing = client.get("/api/agent/briefing").json()
    assert briefing["pending_count"] >= 1
    assert any(item["id"] == candidate["id"] for item in briefing["plan_deltas"])
    assert candidate["reason_code"] == "task_created"
    assert candidate["proposed_payload"]["changes"]

    accepted = client.post(f"/api/agent/plan-deltas/{candidate['id']}/accept", json={"idempotency_key": "apply-first"})
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "executed"
    assert accepted.json()["receipt"]["before_payload"]["plan_snapshot"] != accepted.json()["receipt"]["after_payload"]["plan_snapshot"]
    updated = client.get(f"/api/study-plans/{plan['id']}").json()
    assert any(task["id"] in item["source_task_ids"] for item in updated["items"])

    # A second candidate based on the previous plan snapshot must disappear
    # from read surfaces immediately after the first delta changes the plan.
    stale_source = _task(client, course["id"], "旧快照候选", 25)
    stale_candidate = next(item for item in client.get("/api/agent/plan-deltas").json()
                           if item["current_payload"]["task_id"] == stale_source["id"])
    newest_source = _task(client, course["id"], "更新快照候选", 20)
    newest_candidate = next(item for item in client.get("/api/agent/plan-deltas").json()
                            if item["current_payload"]["task_id"] == newest_source["id"])
    assert client.post(
        f"/api/agent/plan-deltas/{newest_candidate['id']}/accept",
        json={"idempotency_key": "apply-newest"},
    ).status_code == 200
    visible_ids = {item["id"] for item in client.get("/api/agent/plan-deltas").json()}
    assert stale_candidate["id"] not in visible_ids
    assert all(item["id"] != stale_candidate["id"] for item in client.get("/api/agent/briefing").json()["plan_deltas"])

    second = _task(client, course["id"], "人工保护任务", 30)
    candidate = next(item for item in client.get("/api/agent/plan-deltas").json()
                     if item["current_payload"]["task_id"] == second["id"])
    changed_items = updated["items"]
    changed_items[-1]["title"] = "人工修改后的安排"
    assert client.patch(f"/api/study-plans/{plan['id']}", json={"items": changed_items}).status_code == 200
    stale = client.post(f"/api/agent/plan-deltas/{candidate['id']}/accept", json={"idempotency_key": "must-stale"})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "PLAN_DELTA_EXPIRED"
    saved = client.get(f"/api/study-plans/{plan['id']}").json()
    assert saved["items"][-1]["title"] == "人工修改后的安排"


def test_m84_all_task_change_triggers_leave_auditable_event_evidence(client):
    course, _plan = _course_and_plan(client)
    created = _task(client, course["id"], "待完成", 50)
    # Completion with an actual time records task_completed + actual_minutes_changed.
    assert client.post(f"/api/tasks/{created['id']}/complete", json={"actual_minutes": 70}).status_code == 200
    overdue = _task(client, course["id"], "逾期", 30)
    assert client.patch(f"/api/tasks/{overdue['id']}", json={"status": "overdue"}).status_code == 200

    from app.database import get_db
    from app.models.agent import AgentEvent
    # API tests deliberately expose the dependency only inside this assertion;
    # events are the durable trigger evidence, not a UI-only side effect.
    override = client.app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        kinds = {event.event_type for event in db.query(AgentEvent).all()}
    finally:
        generator.close()
    assert {"plan_delta_evaluated", "task_completed", "task_overdue"} <= kinds


def test_m84_task_patch_completion_records_the_completion_event(client):
    course, _plan = _course_and_plan(client)
    task = _task(client, course["id"], "编辑完成", 50)
    assert client.patch(f"/api/tasks/{task['id']}", json={"status": "completed"}).status_code == 200

    from app.database import get_db
    from app.models.agent import AgentEvent
    override = client.app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        events = [event for event in db.query(AgentEvent).all()
                  if event.event_type == "task_completed" and event.entity_id == task["id"]]
    finally:
        generator.close()
    assert len(events) == 1
    assert events[0].payload["completion_path"] == "task_update"


def test_m84_concurrent_delta_accept_commits_one_receipt(tmp_path):
    """Use independent SQLite connections; TestClient's StaticPool is not concurrent-safe."""
    from fastapi import HTTPException
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.api.agent import accept_plan_delta
    from app.database import Base
    from app.models.agent import ActionReceipt, AgentSuggestion
    from app.models.course import Course
    from app.models.study_plan import StudyPlan
    from app.models.task import Task
    from app.schemas.agent import AgentPlanDeltaAccept
    from app.services.agent_feedback import create_plan_delta_candidates
    from app.services.study_plan import encode_plan_content, generate_review_items

    engine = create_engine(f"sqlite:///{tmp_path / 'concurrency.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            course = Course(name="并发课程")
            db.add(course)
            db.flush()
            items, warnings = generate_review_items(
                start_date=date.today(), exam_date=date.today() + timedelta(days=3), daily_minutes=60,
                materials=[], tasks=[],
            )
            plan = StudyPlan(course_id=course.id, title="并发计划", exam_date=date.today() + timedelta(days=3),
                             daily_minutes=60, plan_content=encode_plan_content(items, warnings), status="active")
            task = Task(course_id=course.id, name="并发任务", estimated_minutes=30, remaining_minutes=30, status="not_started")
            db.add_all([plan, task])
            db.flush()
            [candidate] = create_plan_delta_candidates(db, task, "task_created")
            suggestion_id = candidate.id
            db.commit()

        barrier = Barrier(2)
        def accept(key):
            with Session(engine) as db:
                barrier.wait()
                try:
                    result = accept_plan_delta(suggestion_id, AgentPlanDeltaAccept(idempotency_key=key), db)
                    return result.status
                except HTTPException as error:
                    return error.status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(accept, ("concurrent-one", "concurrent-two")))
        assert all(outcome in {"executed", 409} for outcome in outcomes)
        with Session(engine) as db:
            assert db.scalar(select(AgentSuggestion.status).where(AgentSuggestion.id == suggestion_id)) == "executed"
            assert db.scalar(select(ActionReceipt).where(ActionReceipt.suggestion_id == suggestion_id)) is not None
    finally:
        engine.dispose()


def test_m84_delta_database_failure_rolls_back_plan_and_receipt(tmp_path, monkeypatch):
    from fastapi import HTTPException
    from sqlalchemy import create_engine, select
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session

    from app.api.agent import accept_plan_delta
    from app.database import Base
    from app.models.agent import ActionReceipt
    from app.models.course import Course
    from app.models.study_plan import StudyPlan
    from app.models.task import Task
    from app.schemas.agent import AgentPlanDeltaAccept
    from app.services.agent_feedback import create_plan_delta_candidates
    from app.services.study_plan import encode_plan_content, generate_review_items

    engine = create_engine(f"sqlite:///{tmp_path / 'rollback.db'}")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            course = Course(name="回滚课程")
            db.add(course); db.flush()
            items, warnings = generate_review_items(start_date=date.today(), exam_date=date.today() + timedelta(days=2),
                                                     daily_minutes=60, materials=[], tasks=[])
            plan = StudyPlan(course_id=course.id, title="回滚计划", exam_date=date.today() + timedelta(days=2),
                             daily_minutes=60, plan_content=encode_plan_content(items, warnings), status="active")
            task = Task(course_id=course.id, name="回滚任务", estimated_minutes=30, remaining_minutes=30)
            db.add_all([plan, task]); db.flush()
            [candidate] = create_plan_delta_candidates(db, task, "task_created")
            db.commit()
            plan_id, suggestion_id, original = plan.id, candidate.id, plan.plan_content

        with Session(engine) as db:
            monkeypatch.setattr(db, "commit", lambda: (_ for _ in ()).throw(SQLAlchemyError("injected")))
            try:
                accept_plan_delta(suggestion_id, AgentPlanDeltaAccept(idempotency_key="rollback-key"), db)
                assert False, "expected an atomic execution failure"
            except HTTPException as error:
                assert error.status_code == 500
        with Session(engine) as db:
            assert db.get(StudyPlan, plan_id).plan_content == original
            assert db.scalar(select(ActionReceipt).where(ActionReceipt.suggestion_id == suggestion_id)) is None
    finally:
        engine.dispose()
