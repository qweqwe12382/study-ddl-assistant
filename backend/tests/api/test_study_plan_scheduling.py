from datetime import date, datetime, time, timedelta, timezone

from app.time import LOCAL_TIMEZONE


def _due_at(local_date: date, hour: int = 18) -> str:
    return datetime.combine(local_date, time(hour, 0), tzinfo=LOCAL_TIMEZONE).isoformat()


def test_plan_start_date_uses_shanghai_day_at_utc_day_boundary(client, monkeypatch):
    from app.api import study_plans as study_plans_api

    # 2026-09-10 16:30 UTC is already 2026-09-11 in Asia/Shanghai.
    evaluated_at = datetime(2026, 9, 10, 16, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(study_plans_api, "utc_now", lambda: evaluated_at)
    course = client.post("/api/courses", json={"name": "上海日期课程"}).json()
    material = client.post(
        "/api/materials",
        json={"course_id": course["id"], "original_filename": "日期边界资料.md"},
    )
    assert material.status_code == 201

    response = client.post(
        "/api/study-plans/generate",
        json={"course_id": course["id"], "exam_date": "2026-09-11", "daily_minutes": 60},
    )

    assert response.status_code == 201
    plan = response.json()
    assert len(plan["items"]) == 1
    assert plan["items"][0]["date"] == "2026-09-11"


def test_plan_does_not_schedule_task_after_todays_exact_deadline(client, monkeypatch):
    from app.api import study_plans as study_plans_api

    # 02:00 UTC is 10:00 in Shanghai; the task deadline was 09:00 today.
    evaluated_at = datetime(2026, 9, 10, 2, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(study_plans_api, "utc_now", lambda: evaluated_at)
    local_today = date(2026, 9, 10)
    course = client.post("/api/courses", json={"name": "精确截止课程"}).json()
    task = client.post(
        "/api/tasks",
        json={
            "course_id": course["id"],
            "name": "上午九点提交",
            "due_at": _due_at(local_today, hour=9),
            "estimated_minutes": 45,
            "remaining_minutes": 45,
        },
    ).json()

    response = client.post(
        "/api/study-plans/generate",
        json={"course_id": course["id"], "exam_date": local_today.isoformat(), "daily_minutes": 60},
    )

    assert response.status_code == 201
    plan = response.json()
    assert plan["items"] == []
    assert plan["total_minutes"] == 0
    assert plan["unscheduled_items"] == [
        {
            "source_type": "task",
            "source_id": task["id"],
            "navigation_key": task["navigation_key"],
            "label": "上午九点提交",
            "requested_minutes": 45,
            "scheduled_minutes": 0,
            "unscheduled_minutes": 45,
            "latest_date": local_today.isoformat(),
            "reason": "deadline_passed",
            "message": plan["unscheduled_items"][0]["message"],
        }
    ]
    assert "截止时间 2026-09-10T09:00+08:00 已过" in plan["unscheduled_items"][0]["message"]


def test_plan_schedules_deadline_task_before_six_materials(client):
    """Regression: materials must not push a near DDL to the exam date."""

    course = client.post("/api/courses", json={"name": "截止优先课程"}).json()
    for index in range(6):
        response = client.post(
            "/api/materials",
            json={
                "course_id": course["id"],
                "original_filename": f"复习资料-{index + 1}.md",
                "summary": f"第 {index + 1} 份资料重点",
            },
        )
        assert response.status_code == 201

    start_date = date.today()
    due_date = start_date + timedelta(days=1)
    task = client.post(
        "/api/tasks",
        json={
            "course_id": course["id"],
            "name": "明晚提交报告",
            "due_at": _due_at(due_date),
            "estimated_minutes": 60,
            "remaining_minutes": 60,
        },
    ).json()

    response = client.post(
        "/api/study-plans/generate",
        json={
            "course_id": course["id"],
            "exam_date": (start_date + timedelta(days=6)).isoformat(),
            "daily_minutes": 60,
        },
    )

    assert response.status_code == 201
    plan = response.json()
    task_items = [item for item in plan["items"] if task["id"] in item["source_task_ids"]]
    assert len(task_items) == 1
    assert task_items[0]["date"] <= due_date.isoformat()
    assert "60 分钟" in task_items[0]["content"]
    assert all(item["minutes"] <= 60 for item in plan["items"])
    assert not any("明晚提交报告" in warning and "未排入" in warning for warning in plan["warnings"])


def test_plan_splits_minutes_once_and_reports_deadline_overflow(client):
    course = client.post("/api/courses", json={"name": "容量守恒课程"}).json()
    start_date = date.today()
    due_date = start_date + timedelta(days=1)
    tasks = []
    for name in ("任务甲", "任务乙"):
        response = client.post(
            "/api/tasks",
            json={
                "course_id": course["id"],
                "name": name,
                "due_at": _due_at(due_date),
                "estimated_minutes": 60,
                "remaining_minutes": 60,
            },
        )
        assert response.status_code == 201
        tasks.append(response.json())

    response = client.post(
        "/api/study-plans/generate",
        json={
            "course_id": course["id"],
            "exam_date": due_date.isoformat(),
            "daily_minutes": 30,
        },
    )

    assert response.status_code == 201
    plan = response.json()
    first_task_items = [item for item in plan["items"] if tasks[0]["id"] in item["source_task_ids"]]
    second_task_items = [item for item in plan["items"] if tasks[1]["id"] in item["source_task_ids"]]
    assert len(first_task_items) == 2
    assert sum(item["minutes"] for item in first_task_items) == 60
    assert second_task_items == []
    assert sum(item["minutes"] for item in plan["items"]) == 60
    assert any(
        "任务乙" in warning and "60 分钟未排入" in warning and "每日容量不足" in warning
        for warning in plan["warnings"]
    )
    assert any("仅按 Asia/Shanghai 自然日排期" in warning for warning in plan["warnings"])
    assert plan["unscheduled_items"][0]["source_id"] == tasks[1]["id"]
    assert plan["unscheduled_items"][0]["requested_minutes"] == 60
    assert plan["unscheduled_items"][0]["scheduled_minutes"] == 0
    assert plan["unscheduled_items"][0]["unscheduled_minutes"] == 60
    assert plan["unscheduled_items"][0]["reason"] == "daily_capacity"


def test_plan_combines_sources_without_inventing_or_losing_minutes(client, monkeypatch):
    from app.api import study_plans as study_plans_api

    evaluated_at = datetime(2026, 9, 10, 2, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(study_plans_api, "utc_now", lambda: evaluated_at)
    local_today = date(2026, 9, 10)
    course = client.post("/api/courses", json={"name": "同日多来源课程"}).json()
    task_ids = []
    for name, minutes in (("短任务甲", 20), ("短任务乙", 25)):
        response = client.post(
            "/api/tasks",
            json={
                "course_id": course["id"],
                "name": name,
                "estimated_minutes": minutes,
                "remaining_minutes": minutes,
            },
        )
        assert response.status_code == 201
        task_ids.append(response.json()["id"])

    response = client.post(
        "/api/study-plans/generate",
        json={"course_id": course["id"], "exam_date": local_today.isoformat(), "daily_minutes": 60},
    )

    assert response.status_code == 201
    plan = response.json()
    assert len(plan["items"]) == 1
    assert plan["items"][0]["minutes"] == 45
    assert plan["total_minutes"] == 45
    assert plan["items"][0]["source_task_ids"] == task_ids
    assert "短任务甲”20 分钟" in plan["items"][0]["content"]
    assert "短任务乙”25 分钟" in plan["items"][0]["content"]
    assert plan["unscheduled_items"] == []


def test_plan_zero_remaining_task_creates_no_filler_work(client, monkeypatch):
    from app.api import study_plans as study_plans_api

    evaluated_at = datetime(2026, 9, 10, 2, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(study_plans_api, "utc_now", lambda: evaluated_at)
    local_today = date(2026, 9, 10)
    course = client.post("/api/courses", json={"name": "零剩余课程"}).json()
    task = client.post(
        "/api/tasks",
        json={
            "course_id": course["id"],
            "name": "已经无需继续投入",
            "estimated_minutes": 60,
            "remaining_minutes": 0,
        },
    ).json()

    response = client.post(
        "/api/study-plans/generate",
        json={
            "course_id": course["id"],
            "exam_date": (local_today + timedelta(days=2)).isoformat(),
            "daily_minutes": 60,
        },
    )

    assert response.status_code == 201
    plan = response.json()
    assert plan["items"] == []
    assert plan["total_minutes"] == 0
    assert plan["unscheduled_items"] == []
    assert all(task["id"] not in item["source_task_ids"] for item in plan["items"])
    assert any("剩余时长为 0 分钟" in warning for warning in plan["warnings"])
    assert not any("预计复习内容约需" in warning for warning in plan["warnings"])


def test_plan_exposes_missing_estimate_and_past_deadline(client):
    course = client.post("/api/courses", json={"name": "边界说明课程"}).json()
    start_date = date.today()
    task = client.post(
        "/api/tasks",
        json={
            "course_id": course["id"],
            "name": "未估时且已过期",
            "due_at": _due_at(start_date - timedelta(days=1)),
        },
    ).json()

    response = client.post(
        "/api/study-plans/generate",
        json={
            "course_id": course["id"],
            "exam_date": (start_date + timedelta(days=2)).isoformat(),
            "daily_minutes": 60,
        },
    )

    assert response.status_code == 201
    plan = response.json()
    assert all(task["id"] not in item["source_task_ids"] for item in plan["items"])
    assert any("未估时且已过期" in warning and "按 30 分钟假设" in warning for warning in plan["warnings"])
    assert any(
        "未估时且已过期" in warning and "30 分钟未排入" in warning and "早于计划开始日期" in warning
        for warning in plan["warnings"]
    )


def test_plan_names_focus_limit_when_minutes_would_otherwise_fit(client, monkeypatch):
    from app.api import study_plans as study_plans_api

    evaluated_at = datetime(2026, 9, 10, 2, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(study_plans_api, "utc_now", lambda: evaluated_at)
    local_today = date(2026, 9, 10)
    course = client.post("/api/courses", json={"name": "主题上限课程"}).json()
    for index in range(4):
        response = client.post(
            "/api/materials",
            json={"course_id": course["id"], "original_filename": f"主题-{index + 1}.md"},
        )
        assert response.status_code == 201

    response = client.post(
        "/api/study-plans/generate",
        json={"course_id": course["id"], "exam_date": local_today.isoformat(), "daily_minutes": 240},
    )

    assert response.status_code == 201
    plan = response.json()
    assert plan["total_minutes"] == 180
    assert any(
        "主题-4.md" in warning and "60 分钟未排入" in warning and "每天最多 3 个主题" in warning
        for warning in plan["warnings"]
    )
    assert plan["unscheduled_items"] == [
        {
            "source_type": "material",
            "source_id": plan["unscheduled_items"][0]["source_id"],
            "navigation_key": plan["unscheduled_items"][0]["navigation_key"],
            "label": "主题-4.md",
            "requested_minutes": 60,
            "scheduled_minutes": 0,
            "unscheduled_minutes": 60,
            "latest_date": local_today.isoformat(),
            "reason": "daily_focus_limit",
            "message": plan["unscheduled_items"][0]["message"],
        }
    ]


def test_old_plan_content_has_empty_structured_unscheduled_feedback():
    import json

    from app.services.study_plan import decode_plan_unscheduled_items

    assert decode_plan_unscheduled_items(json.dumps({"version": 2, "items": [], "warnings": []})) == []
