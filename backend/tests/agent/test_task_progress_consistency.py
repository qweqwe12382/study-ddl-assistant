"""Task progress and accepted plan changes must preserve one consistent state."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.database import get_db
from app.models.agent import ActionReceipt, AgentEvent, AgentSuggestion
from app.models.task import Task
from app.time import as_local


NOW = datetime(2026, 10, 2, 1, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def frozen_business_time(monkeypatch):
    from app.api import study_plans, agent, dashboard
    from app.services import agent_feedback, focus_sessions, task_service

    for module in (study_plans, agent, dashboard, agent_feedback, focus_sessions, task_service):
        monkeypatch.setattr(module, "utc_now", lambda: NOW)


def tag(row):
    return {"If-Match": f'"{row["navigation_key"]}:{row["revision"]}"'}


def create_task(client, **overrides):
    response = client.post("/api/tasks", json={
        "name": "待处理任务", "estimated_minutes": 60, "remaining_minutes": 60,
        "due_at": (NOW + timedelta(days=2)).isoformat(), **overrides,
    })
    assert response.status_code == 201, response.text
    return response.json()


def course_plan(client, *, task_first=True):
    course = client.post("/api/courses", json={"name": "联动课程"}).json()
    material = client.post("/api/materials", json={
        "course_id": course["id"], "original_filename": "基础资料.md",
    })
    assert material.status_code == 201
    task = create_task(client, course_id=course["id"]) if task_first else None
    response = client.post("/api/study-plans/generate", json={
        "course_id": course["id"], "exam_date": (as_local(NOW).date() + timedelta(days=3)).isoformat(),
        "daily_minutes": 60,
    })
    assert response.status_code == 201, response.text
    return course, task, response.json()


def task_deltas(client, task):
    return [row for row in client.get("/api/agent/plan-deltas").json()
            if row["current_payload"]["task_id"] == task["id"]]


def accept(client, delta, key):
    response = client.post(f'/api/agent/plan-deltas/{delta["id"]}/accept', json={"idempotency_key": key})
    assert response.status_code == 200, response.text
    return response.json()


def test_focus_session_records_progress_without_completing_and_retries_once(client):
    task = create_task(client)
    payload = {"minutes": 25, "idempotency_key": "focus-first"}
    response = client.post(f'/api/tasks/{task["id"]}/focus-sessions', json=payload, headers=tag(task))
    assert response.status_code == 200, response.text
    recorded = response.json()
    assert recorded["actual_minutes"] == 25
    assert recorded["remaining_minutes"] == 35
    assert recorded["status"] == "in_progress"
    assert recorded["completed_at"] is None
    assert recorded["revision"] == task["revision"] + 1

    repeated = client.post(f'/api/tasks/{task["id"]}/focus-sessions', json=payload, headers=tag(task))
    assert repeated.status_code == 200
    assert repeated.json() == recorded
    refreshed = client.get(f'/api/tasks/{task["id"]}').json()
    assert client.post(f'/api/tasks/{task["id"]}/focus-sessions', json=payload, headers=tag(refreshed)).json() == recorded
    second = client.post(f'/api/tasks/{task["id"]}/focus-sessions', json={
        "minutes": 40, "idempotency_key": "focus-second",
    }, headers=tag(recorded))
    assert second.status_code == 200
    assert second.json()["actual_minutes"] == 65
    assert second.json()["remaining_minutes"] == 0
    assert second.json()["status"] == "in_progress"
    with contextmanager(client.app.dependency_overrides[get_db])() as db:
        receipts = db.scalars(select(ActionReceipt).where(ActionReceipt.action_type == "record_focus_session")).all()
        assert len(receipts) == 2
        assert [row.applied_payload["minutes"] for row in receipts] == [25, 40]
        assert not db.scalars(select(AgentEvent).where(AgentEvent.event_type == "task_completed")).all()


@pytest.mark.parametrize("route", ["/api/tasks/{id}/complete", "/api/agent/tasks/{id}/complete", "/api/tasks/{id}"])
def test_canceled_task_cannot_be_completed_without_reopening(client, route):
    task = create_task(client, status="canceled")
    if route.endswith("/{id}"):
        response = client.patch(route.format(id=task["id"]), json={"status": "completed"}, headers=tag(task))
    else:
        response = client.post(route.format(id=task["id"]), json={"actual_minutes": 45}, headers=tag(task))
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "TASK_CANCELED"
    assert client.get(f'/api/tasks/{task["id"]}').json() == task
    with contextmanager(client.app.dependency_overrides[get_db])() as db:
        assert db.scalars(select(ActionReceipt)).all() == []


def test_completion_with_minutes_keeps_terminal_plan_delta_and_feedback_never_readds_task(client):
    _course, task, plan = course_plan(client)
    completed = client.post(f'/api/agent/tasks/{task["id"]}/complete', json={"actual_minutes": 45}, headers=tag(task))
    assert completed.status_code == 200
    [delta] = task_deltas(client, task)
    assert delta["reason_code"] == "task_completed"
    for change in delta["proposed_payload"]["changes"]:
        assert task["id"] not in change["after"]["source_task_ids"]
        assert "已完成" in change["after"]["content"]
    accept(client, delta, "remove-completed")
    current = completed.json()["task"]
    updated = client.post(f'/api/agent/tasks/{task["id"]}/complete', json={"actual_minutes": 50}, headers=tag(current))
    assert updated.status_code == 200
    assert task_deltas(client, task) == []
    saved = client.get(f'/api/study-plans/{plan["id"]}').json()
    assert all(task["id"] not in row["source_task_ids"] for row in saved["items"])


def test_accepted_system_change_keeps_followup_link_and_manual_edits_stay_protected(client):
    course, _, plan = course_plan(client, task_first=False)
    task = create_task(client, course_id=course["id"])
    [delta] = task_deltas(client, task)
    accept(client, delta, "link-created")
    linked = client.get(f'/api/study-plans/{plan["id"]}').json()
    assert any(task["id"] in item["source_task_ids"] for item in linked["items"])
    completed = client.post(f'/api/tasks/{task["id"]}/complete', headers=tag(task))
    assert completed.status_code == 200
    [completion_delta] = task_deltas(client, task)
    assert completion_delta["reason_code"] == "task_completed"

    changed_items = linked["items"]
    changed_items[0]["content"] = "人工安排：保留本项复习内容"
    manual = client.patch(f'/api/study-plans/{plan["id"]}', json={"items": changed_items}, headers=tag(linked))
    assert manual.status_code == 200
    rejected = client.post(f'/api/agent/plan-deltas/{completion_delta["id"]}/accept', json={"idempotency_key": "keep-manual"})
    assert rejected.status_code == 409
    assert client.get(f'/api/study-plans/{plan["id"]}').json()["items"][0]["content"] == changed_items[0]["content"]


@pytest.mark.parametrize("new_due", [(NOW + timedelta(days=2)).isoformat(), None])
def test_deadline_edit_clears_overdue_and_rechecks_plan_without_duplicate_dashboard_buckets(client, new_due):
    course, _, plan = course_plan(client, task_first=False)
    task = create_task(client, course_id=course["id"], due_at=(NOW - timedelta(days=1)).isoformat())
    overdue = client.get(f'/api/tasks/{task["id"]}').json()
    assert overdue["status"] == "overdue"
    changed = client.patch(f'/api/tasks/{task["id"]}', json={"due_at": new_due}, headers=tag(overdue))
    assert changed.status_code == 200
    assert changed.json()["status"] == "not_started"
    assert client.get(f'/api/tasks/{task["id"]}').json()["status"] == "not_started"
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["overdue_count"] == 0
    assert dashboard["overdue_tasks"] == []
    assert dashboard["due_soon_count"] == (1 if new_due is not None else 0)
    [delta] = task_deltas(client, task)
    assert delta["reason_code"] == "deadline_changed"
    assert delta["source_id"] == plan["id"]


def test_read_repairs_preexisting_overdue_with_future_deadline(client):
    task = create_task(client, status="overdue")
    response = client.get(f'/api/tasks/{task["id"]}')
    assert response.status_code == 200
    assert response.json()["status"] == "not_started"


@pytest.mark.parametrize("overrides,remaining,status", [
    ({"estimated_minutes": None, "remaining_minutes": None}, None, "in_progress"),
    ({"remaining_minutes": None}, 35, "in_progress"),
    ({"remaining_minutes": 15}, 0, "in_progress"),
    ({"due_at": (NOW - timedelta(days=1)).isoformat()}, 35, "overdue"),
])
def test_focus_respects_unknown_remaining_and_preserves_overdue(client, overrides, remaining, status):
    task = create_task(client, **overrides)
    response = client.post(f'/api/tasks/{task["id"]}/focus-sessions', json={
        "minutes": 25, "idempotency_key": "progress-case",
    }, headers=tag(task))
    assert response.status_code == 200, response.text
    assert response.json()["estimated_minutes"] == task["estimated_minutes"]
    assert response.json()["remaining_minutes"] == remaining
    assert response.json()["status"] == status
    assert response.json()["completed_at"] is None


@pytest.mark.parametrize("status", ["completed", "canceled"])
def test_terminal_task_rejects_new_focus_sessions(client, status):
    task = create_task(client, status=status)
    response = client.post(f'/api/tasks/{task["id"]}/focus-sessions', json={
        "minutes": 25, "idempotency_key": "terminal-focus",
    }, headers=tag(task))
    assert response.status_code == 409
    assert client.get(f'/api/tasks/{task["id"]}').json() == task
    with contextmanager(client.app.dependency_overrides[get_db])() as db:
        assert db.scalars(select(ActionReceipt)).all() == []


def test_focus_requires_version_and_rejects_changed_retry_or_stale_new_request(client):
    task = create_task(client)
    url = f'/api/tasks/{task["id"]}/focus-sessions'
    payload = {"minutes": 25, "idempotency_key": "guarded-focus"}
    assert client.post(url, json=payload).status_code == 428
    assert client.post(url, json=payload, headers={"If-Match": "*"}).status_code == 400
    for invalid_minutes in (14, 10081):
        assert client.post(url, json={**payload, "minutes": invalid_minutes}, headers=tag(task)).status_code == 422
    saved = client.post(url, json=payload, headers=tag(task)).json()
    changed_retry = client.post(url, json={**payload, "minutes": 30}, headers=tag(task))
    assert changed_retry.status_code == 409
    assert changed_retry.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    stale = client.post(url, json={**payload, "idempotency_key": "new-session"}, headers=tag(task))
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "EDIT_CONFLICT"
    assert client.get(f'/api/tasks/{task["id"]}').json() == saved


def test_focus_retry_cannot_follow_reused_numeric_task_id(client):
    original = create_task(client)
    payload = {"minutes": 25, "idempotency_key": "deleted-focus"}
    url = f'/api/tasks/{original["id"]}/focus-sessions'
    recorded = client.post(url, json=payload, headers=tag(original)).json()
    assert client.delete(f'/api/tasks/{original["id"]}', headers=tag(recorded)).status_code == 204
    replacement = create_task(client)
    assert replacement["id"] == original["id"]
    assert replacement["navigation_key"] != original["navigation_key"]
    assert client.post(url, json=payload, headers=tag(original)).status_code == 409
    assert client.post(url, json=payload, headers=tag(replacement)).status_code == 409
    assert client.get(f'/api/tasks/{replacement["id"]}').json() == replacement


def test_focus_total_limit_is_rejected_without_losing_minutes_or_writing_receipt(client):
    task = create_task(client)
    with contextmanager(client.app.dependency_overrides[get_db])() as db:
        db.get(Task, task["id"]).actual_minutes = 10070
        db.commit()
    before = client.get(f'/api/tasks/{task["id"]}').json()
    response = client.post(f'/api/tasks/{task["id"]}/focus-sessions', json={
        "minutes": 15, "idempotency_key": "over-limit-focus",
    }, headers=tag(before))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TASK_ACTUAL_MINUTES_LIMIT"
    assert client.get(f'/api/tasks/{task["id"]}').json() == before
    with contextmanager(client.app.dependency_overrides[get_db])() as db:
        assert db.scalars(select(ActionReceipt)).all() == []


@pytest.mark.parametrize("completion_route", ["/api/tasks/{id}/complete", "/api/agent/tasks/{id}/complete"])
def test_focus_then_completion_uses_total_and_retries_original_version_once(client, completion_route):
    task = create_task(client)
    recorded = client.post(f'/api/tasks/{task["id"]}/focus-sessions', json={
        "minutes": 25, "idempotency_key": "first-focus-before-completion",
    }, headers=tag(task)).json()
    payload = {"actual_minutes": recorded["actual_minutes"] + 30, "idempotency_key": "complete-next-focus"}
    url = completion_route.format(id=task["id"])
    first = client.post(url, json=payload, headers=tag(recorded))
    repeated = client.post(url, json=payload, headers=tag(recorded))
    assert first.status_code == repeated.status_code == 200
    assert first.json() == repeated.json()
    saved = client.get(f'/api/tasks/{task["id"]}').json()
    assert saved["actual_minutes"] == 55
    assert saved["status"] == "completed"
    with contextmanager(client.app.dependency_overrides[get_db])() as db:
        assert len(db.scalars(select(ActionReceipt).where(ActionReceipt.action_type == "complete_task")).all()) == 1


def test_quick_completion_keeps_recorded_focus_total_and_new_feedback_stays_explicit(client):
    task = create_task(client)
    recorded = client.post(f'/api/tasks/{task["id"]}/focus-sessions', json={
        "minutes": 25, "idempotency_key": "keep-recorded-focus",
    }, headers=tag(task)).json()
    completed = client.post(f'/api/tasks/{task["id"]}/complete', headers=tag(recorded))
    assert completed.status_code == 200
    assert completed.json()["actual_minutes"] == 25
    assert completed.json()["status"] == "completed"


def test_multiple_accepted_system_changes_advance_baseline_through_completion(client):
    course, _, plan = course_plan(client, task_first=False)
    task = create_task(client, course_id=course["id"])
    [created] = task_deltas(client, task)
    accept(client, created, "system-link")
    assert client.post(f'/api/tasks/{task["id"]}/complete', headers=tag(task)).status_code == 200
    [completed] = task_deltas(client, task)
    accept(client, completed, "system-unlink")
    saved = client.get(f'/api/study-plans/{plan["id"]}').json()
    assert all(task["id"] not in item["source_task_ids"] for item in saved["items"])
    next_task = create_task(client, course_id=course["id"], name="下一项任务")
    [next_delta] = task_deltas(client, next_task)
    assert next_delta["proposed_payload"]["changes"][0]["before"] == saved["items"][0]


def test_focus_failure_rolls_back_progress_and_receipt(tmp_path, monkeypatch):
    from fastapi import HTTPException
    from sqlalchemy import create_engine
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session
    from app.api.tasks import record_task_focus_session
    from app.database import Base
    from app.schemas.task import TaskFocusSession

    engine = create_engine(f"sqlite:///{(tmp_path / 'focus-rollback.db').as_posix()}")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            task = Task(name="回滚专注", estimated_minutes=60, remaining_minutes=60)
            db.add(task)
            db.commit()
            task_id, key = task.id, task.navigation_key
        with Session(engine) as db:
            monkeypatch.setattr(db, "commit", lambda: (_ for _ in ()).throw(SQLAlchemyError("injected")))
            with pytest.raises(HTTPException) as failure:
                record_task_focus_session(task_id, TaskFocusSession(minutes=25, idempotency_key="rollback-focus"),
                                          if_match=f'"{key}:1"', db=db)
            assert failure.value.status_code == 500
        with Session(engine) as db:
            saved = db.get(Task, task_id)
            assert saved.actual_minutes is None
            assert saved.remaining_minutes == 60
            assert saved.status == "not_started"
            assert saved.revision == 1
            assert db.scalars(select(ActionReceipt)).all() == []
            assert db.scalars(select(AgentSuggestion)).all() == []
    finally:
        engine.dispose()


def test_concurrent_focus_requests_record_minutes_only_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi import HTTPException
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.api.tasks import record_task_focus_session
    from app.database import Base
    from app.schemas.task import TaskFocusSession

    engine = create_engine(f"sqlite:///{(tmp_path / 'focus-concurrent.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            task = Task(name="并发专注", estimated_minutes=60, remaining_minutes=60)
            db.add(task)
            db.commit()
            task_id, key = task.id, task.navigation_key
        barrier = Barrier(2)
        payload = TaskFocusSession(minutes=25, idempotency_key="same-focus-session")

        def save():
            with Session(engine) as db:
                original = db.get(Task, task_id)
                assert original.revision == 1
                barrier.wait()
                try:
                    result = record_task_focus_session(task_id, payload, if_match=f'"{key}:1"', db=db)
                    return result.actual_minutes
                except HTTPException as error:
                    return error.status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: save(), range(2)))
        assert 25 in results
        assert all(result in {25, 409} for result in results)
        with Session(engine) as db:
            saved = db.get(Task, task_id)
            assert saved.actual_minutes == 25
            assert saved.remaining_minutes == 35
            assert saved.revision == 2
            assert len(db.scalars(select(ActionReceipt)).all()) == 1
            retried = record_task_focus_session(task_id, payload, if_match=f'"{key}:1"', db=db)
            assert retried.actual_minutes == 25
    finally:
        engine.dispose()
