from datetime import datetime

import pytest

from app.services import task_service


REFERENCE_TIME = "2026-09-11T01:00:00Z"


def _create_task(
    client,
    *,
    name: str = "数据结构实验报告",
    due_at: str = "2026-09-16T04:00:00Z",
    estimated_minutes: int = 90,
):
    response = client.post(
        "/api/tasks",
        json={
            "name": name,
            "due_at": due_at,
            "estimated_minutes": estimated_minutes,
            "remaining_minutes": estimated_minutes,
        },
    )
    assert response.status_code == 201
    return response.json()


def _radar_payload(task, notice_text: str) -> dict:
    return {
        "task_id": task["id"],
        "task_navigation_key": task["navigation_key"],
        "task_revision": task["revision"],
        "notice_text": notice_text,
        "reference_time": REFERENCE_TIME,
    }


@pytest.mark.parametrize(
    "wall_time",
    [REFERENCE_TIME, "2030-01-01T00:00:00Z"],
    ids=["before-deadlines", "after-deadlines"],
)
def test_deadline_radar_previews_an_earlier_deadline_without_mutating_task(client, monkeypatch, wall_time):
    monkeypatch.setattr(task_service, "utc_now", lambda: datetime.fromisoformat(wall_time))
    configured = client.put(
        "/api/study-preferences",
        json={"weekly_available_minutes": 600, "daily_limit_minutes": 120, "buffer_ratio": 0},
    )
    task = _create_task(client)
    other_task = _create_task(
        client,
        name="同日课程展示",
        due_at="2026-09-13T05:00:00Z",
        estimated_minutes=60,
    )
    notice = "课程群通知：数据结构实验报告提交时间提前至2026年9月13日12:00，请互相转告。"
    activity_before = client.get("/api/agent/activity").json()["items"]

    response = client.post("/api/deadline-radar/preview", json=_radar_payload(task, notice))

    assert configured.status_code == 200
    assert response.status_code == 200
    preview = response.json()
    assert preview["intent"] == "reschedule"
    assert preview["task"]["current_due_at"] == "2026-09-16T04:00:00Z"
    assert preview["task"]["proposed_due_at"] == "2026-09-13T04:00:00Z"
    assert preview["impact"]["direction"] == "earlier"
    assert preview["impact"]["day_shift"] == -3
    changed_day = next(day for day in preview["pressure_days"] if day["local_date"] == "2026-09-13")
    assert changed_day["before_minutes"] == 60
    assert changed_day["after_minutes"] == 150
    assert changed_day["after_overload_minutes"] == 30
    assert changed_day["affected"] is True
    assert "提前至2026年9月13日12:00" in preview["evidence"]["quote"]

    # Observe the preview before GET /tasks/{id}, which independently persists
    # overdue transitions for every task using the wall clock.
    activity_after = client.get("/api/agent/activity").json()["items"]
    assert [item["activity_id"] for item in activity_after] == [
        item["activity_id"] for item in activity_before
    ]

    # Keep the observation requests from introducing their own transitions.
    # A mutation by preview is still caught by full snapshots of both tasks.
    monkeypatch.setattr(task_service, "utc_now", lambda: datetime.fromisoformat(REFERENCE_TIME))
    for original in (task, other_task):
        saved = client.get(f"/api/tasks/{original['id']}")
        assert saved.status_code == 200
        assert saved.json() == original


def test_deadline_radar_apply_is_confirmed_auditable_and_idempotent(client):
    task = _create_task(client)
    notice = "教学平台通知：本次实验报告截止时间延期至2026年9月18日20:30。"
    payload = {
        **_radar_payload(task, notice),
        "idempotency_key": "deadline-radar-reschedule-1",
    }

    response = client.post("/api/deadline-radar/apply", json=payload)
    repeated = client.post("/api/deadline-radar/apply", json=payload)

    assert response.status_code == repeated.status_code == 200
    result = response.json()
    replay = repeated.json()
    assert result["status"] == "executed"
    assert result["intent"] == "reschedule"
    assert result["task"]["due_at"] == "2026-09-18T12:30:00Z"
    assert result["task"]["revision"] == task["revision"] + 1
    assert result["receipt"]["before_payload"]["due_at"] == "2026-09-16T04:00:00+00:00"
    assert result["receipt"]["after_payload"]["due_at"] == "2026-09-18T12:30:00+00:00"
    assert replay["receipt"]["id"] == result["receipt"]["id"]
    assert replay["task"]["revision"] == result["task"]["revision"]

    activity = client.get("/api/agent/activity").json()["items"]
    assert len([
        item for item in activity
        if item["kind"] == "suggestion" and item["title"] == "通知截止时间变更"
    ]) == 1
    assert len([
        item for item in activity
        if item["kind"] == "receipt" and item["title"] == "通知截止时间变更执行回执"
    ]) == 1
    assert all("notice_digest" not in item for item in activity)


def test_deadline_radar_rejects_stale_task_identity_before_execution(client):
    task = _create_task(client)
    changed = client.patch(
        f"/api/tasks/{task['id']}",
        json={"priority": 5},
        headers={"If-Match": f'"{task["navigation_key"]}:{task["revision"]}"'},
    )
    payload = {
        **_radar_payload(task, "截止时间调整至2026年9月17日18:00。"),
        "idempotency_key": "deadline-radar-stale-1",
    }

    response = client.post("/api/deadline-radar/apply", json=payload)

    assert changed.status_code == 200
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EDIT_CONFLICT"
    saved = client.get(f"/api/tasks/{task['id']}").json()
    assert saved["due_at"] == task["due_at"]
    assert saved["priority"] == 5


def test_deadline_radar_requires_an_explicit_unambiguous_change(client):
    task = _create_task(client)
    cases = [
        ("请于2026年9月18日20:00提交报告。", "DEADLINE_CHANGE_NOT_FOUND"),
        ("提交时间延期，具体日期另行通知。", "DEADLINE_CHANGE_DATE_UNCLEAR"),
        ("作业取消，截止时间调整至2026年9月18日20:00。", "DEADLINE_CHANGE_AMBIGUOUS"),
        ("截止时间调整至2026年9月16日12:00。", "DEADLINE_CHANGE_NO_EFFECT"),
    ]

    for notice, code in cases:
        response = client.post("/api/deadline-radar/preview", json=_radar_payload(task, notice))
        assert response.status_code == 422
        assert response.json()["error"]["code"] == code


def test_deadline_radar_cancel_removes_task_from_active_workload_without_counting_completion(client):
    task = _create_task(client, estimated_minutes=75)
    payload = {
        **_radar_payload(task, "课程通知：本次实验报告任务取消，无需提交。"),
        "idempotency_key": "deadline-radar-cancel-1",
    }

    preview = client.post("/api/deadline-radar/preview", json={key: value for key, value in payload.items() if key != "idempotency_key"})
    applied = client.post("/api/deadline-radar/apply", json=payload)

    assert preview.status_code == 200
    assert preview.json()["intent"] == "cancel"
    assert preview.json()["impact"]["after_known_minutes"] == 0
    assert applied.status_code == 200
    result = applied.json()
    assert result["intent"] == "cancel"
    assert result["task"]["status"] == "canceled"
    assert result["task"]["remaining_minutes"] == 0
    assert result["task"]["completed_at"] is None

    dashboard = client.get("/api/dashboard").json()
    capacity = client.get("/api/agent/capacity").json()
    calendar_text = client.get("/api/exports/tasks.ics").text
    assert dashboard["active_task_count"] == 0
    assert dashboard["completed_task_count"] == 0
    assert task["id"] not in [item["id"] for item in capacity["tasks"]]
    assert task["navigation_key"] not in calendar_text


def test_deadline_radar_rejects_idempotency_key_reuse_for_another_notice(client):
    task = _create_task(client)
    first = {
        **_radar_payload(task, "截止时间延期至2026年9月18日20:00。"),
        "idempotency_key": "deadline-radar-conflict-1",
    }
    applied = client.post("/api/deadline-radar/apply", json=first)
    current = applied.json()["task"]
    conflicting = {
        **_radar_payload(current, "截止时间延期至2026年9月19日20:00。"),
        "idempotency_key": first["idempotency_key"],
    }

    response = client.post("/api/deadline-radar/apply", json=conflicting)

    assert applied.status_code == 200
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


def test_canceled_task_is_terminal_until_the_user_explicitly_reopens_it(client):
    created = client.post(
        "/api/tasks",
        json={
            "name": "已撤销的课堂展示",
            "status": "canceled",
            "estimated_minutes": 45,
            "remaining_minutes": 30,
        },
    )

    assert created.status_code == 201
    canceled = created.json()
    assert canceled["remaining_minutes"] == 0

    completion = client.post(f"/api/tasks/{canceled['id']}/complete")
    assert completion.status_code == 409
    assert completion.json()["error"]["code"] == "TASK_CANCELED"

    reopened = client.patch(
        f"/api/tasks/{canceled['id']}",
        json={"status": "not_started"},
        headers={"If-Match": f'"{canceled["navigation_key"]}:{canceled["revision"]}"'},
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "not_started"
    assert reopened.json()["remaining_minutes"] == 45
