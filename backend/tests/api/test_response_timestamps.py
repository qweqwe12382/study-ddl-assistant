"""Persisted UTC records must not shift when a client reads them in China."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import TypeAdapter

from app.schemas.timestamps import UtcDateTime
from app.time import LOCAL_TIMEZONE, utc_now


def _body(response):
    assert response.status_code in (200, 201), response.text
    return response.json()


def _timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None, f"response lost its timezone: {value}"
    assert parsed.utcoffset() == timedelta(0)
    return parsed


def _audit_fields(record):
    for field in ("created_at", "updated_at"):
        _timestamp(record[field])


@pytest.mark.parametrize("value", [
    datetime(2026, 9, 20, 3, 35),
    datetime(2026, 9, 20, 3, 35, tzinfo=timezone.utc),
    datetime(2026, 9, 20, 11, 35, tzinfo=LOCAL_TIMEZONE),
])
def test_persisted_timestamp_preserves_instant_and_beijing_display(value):
    timestamp = TypeAdapter(UtcDateTime).validate_python(value)
    assert timestamp == datetime(2026, 9, 20, 3, 35, tzinfo=timezone.utc)
    assert timestamp.astimezone(LOCAL_TIMEZONE).strftime("%H:%M") == "11:35"


def test_sqlite_record_reads_keep_timezone_and_wall_time_input(client, isolated_upload_dir):
    course = _body(client.post("/api/courses", json={"name": "时区验收"}))
    _audit_fields(course)
    _audit_fields(_body(client.get("/api/courses"))[0])
    task = _body(client.post("/api/tasks", json={
        "name": "北京时间任务", "course_id": course["id"],
        "due_at": "2026-12-01T20:00:00", "estimated_minutes": 30,
    }))
    _audit_fields(task)
    assert _timestamp(task["due_at"]) == datetime(2026, 12, 1, 12, tzinfo=timezone.utc)
    _audit_fields(_body(client.get("/api/tasks"))[0])

    material = _body(client.post("/api/materials/upload", data={
        "course_id": str(course["id"]), "material_type": "复习资料",
        "source_time": "2026-09-20T11:35:00+08:00",
    }, files={"files": ("复习知识点.txt", "复习资料\n知识点：二叉树遍历与复杂度分析".encode(), "text/plain")}))[0]
    _audit_fields(material)
    _timestamp(material["extracted_at"])
    assert _timestamp(material["source_time"]).hour == 3
    _audit_fields(_body(client.get("/api/materials"))[0])
    _timestamp(_body(client.get(f"/api/materials/{material['id']}/extraction"))["extracted_at"])

    exam = _body(client.post("/api/academic-calendar/exams", json={
        "course_id": course["id"], "title": "北京时间考试",
        "starts_at": "2026-12-01T09:00:00", "exam_type": "final",
    }))
    _audit_fields(exam)
    assert _timestamp(exam["starts_at"]).hour == 1
    _audit_fields(_body(client.get("/api/academic-calendar/exams", params={"include_past": True}))[0])

    plan = _body(client.post("/api/study-plans/generate", json={
        "course_id": course["id"], "exam_date": (utc_now() + timedelta(days=7)).date().isoformat(),
        "daily_minutes": 60,
    }))
    _audit_fields(plan)
    _audit_fields(_body(client.get(f"/api/study-plans/{plan['id']}")))
    _audit_fields(_body(client.get("/api/study-preferences")))


def test_agent_receipt_briefing_and_activity_keep_timezone_after_reload(client):
    before = utc_now() - timedelta(seconds=1)
    task = _body(client.post("/api/tasks", json={
        "name": "回执时间验收", "due_at": (utc_now() + timedelta(hours=24)).isoformat(),
        "priority": 1,
    }))
    briefing = _body(client.post("/api/agent/refresh"))
    assert briefing["suggestions"]
    for suggestion in briefing["suggestions"]:
        _audit_fields(suggestion)
        _timestamp(suggestion["expires_at"])
    completed = _body(client.post(f"/api/agent/tasks/{task['id']}/complete", json={
        "idempotency_key": "timestamp-completion", "actual_minutes": 45,
    }, headers={"If-Match": f'"{task["navigation_key"]}:{task["revision"]}"'}))
    for value in (completed["receipt"]["executed_at"], completed["task"]["completed_at"]):
        assert before <= _timestamp(value) <= utc_now() + timedelta(seconds=1)
    history = _body(client.get("/api/agent/briefing"))
    _timestamp(history["generated_at"])
    assert history["recent_results"]
    for item in history["recent_results"]:
        _audit_fields(item)
        if item["receipt"]:
            _timestamp(item["receipt"]["executed_at"])
    activity = _body(client.get("/api/agent/activity"))
    assert activity["items"]
    for item in activity["items"]:
        assert before <= _timestamp(item["occurred_at"]) <= utc_now() + timedelta(seconds=1)
