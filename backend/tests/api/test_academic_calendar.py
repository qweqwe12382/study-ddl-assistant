def _course(client, name="高等数学"):
    response = client.post("/api/courses", json={"name": name, "teacher": "周老师", "color": "#5964ed"})
    assert response.status_code == 201
    return response.json()


def _edit_headers(item):
    return {"If-Match": f'"{item["navigation_key"]}:{item["revision"]}"'}


def test_week_schedule_filters_patterns_and_rejects_real_conflicts(client):
    course = _course(client)
    odd = client.post(
        "/api/academic-calendar/class-sessions",
        json={
            "course_id": course["id"],
            "weekday": 1,
            "start_time": "09:00",
            "end_time": "10:35",
            "location": "博学楼 B203",
            "start_week": 1,
            "end_week": 16,
            "week_pattern": "odd",
        },
    )
    assert odd.status_code == 201
    odd_item = odd.json()
    assert odd_item["course_name"] == "高等数学"
    assert odd_item["teacher"] == "周老师"

    even = client.post(
        "/api/academic-calendar/class-sessions",
        json={
            "course_id": course["id"],
            "weekday": 1,
            "start_time": "09:00",
            "end_time": "10:35",
            "start_week": 2,
            "end_week": 16,
            "week_pattern": "even",
        },
    )
    assert even.status_code == 201
    assert len(client.get("/api/academic-calendar/class-sessions?week=2").json()) == 1
    assert len(client.get("/api/academic-calendar/class-sessions?week=3").json()) == 1

    conflict = client.post(
        "/api/academic-calendar/class-sessions",
        json={
            "course_id": course["id"],
            "weekday": 1,
            "start_time": "10:00",
            "end_time": "11:00",
            "start_week": 1,
            "end_week": 16,
            "week_pattern": "all",
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "CLASS_SESSION_CONFLICT"

    overview = client.get("/api/academic-calendar/overview?week=3")
    assert overview.status_code == 200
    assert overview.json()["week"] == 3
    assert overview.json()["class_sessions"][0]["location"] == "博学楼 B203"


def test_class_session_edit_precondition_and_delete(client):
    course = _course(client, "大学物理")
    created = client.post(
        "/api/academic-calendar/class-sessions",
        json={
            "course_id": course["id"],
            "weekday": 4,
            "start_time": "14:00",
            "end_time": "15:40",
            "start_week": 1,
            "end_week": 18,
        },
    ).json()
    updated = client.patch(
        f'/api/academic-calendar/class-sessions/{created["id"]}',
        json={"location": "格物楼 301"},
        headers=_edit_headers(created),
    )
    assert updated.status_code == 200
    updated_item = updated.json()
    assert updated_item["revision"] == 2

    stale_delete = client.delete(
        f'/api/academic-calendar/class-sessions/{created["id"]}', headers=_edit_headers(created)
    )
    assert stale_delete.status_code == 409
    deleted = client.delete(
        f'/api/academic-calendar/class-sessions/{created["id"]}', headers=_edit_headers(updated_item)
    )
    assert deleted.status_code == 204


def test_exam_listing_validation_and_account_workspace_crud(client):
    course = _course(client, "数据结构")
    future = client.post(
        "/api/academic-calendar/exams",
        json={
            "course_id": course["id"],
            "title": "数据结构期末考试",
            "exam_type": "final",
            "starts_at": "2099-01-18T09:00:00+08:00",
            "ends_at": "2099-01-18T11:00:00+08:00",
            "location": "第一教学楼 101",
            "seat_number": "A-18",
        },
    )
    assert future.status_code == 201
    future_item = future.json()
    assert future_item["course_name"] == "数据结构"
    assert future_item["starts_at"] == "2099-01-18T01:00:00Z"

    past = client.post(
        "/api/academic-calendar/exams",
        json={
            "course_id": course["id"],
            "title": "历史随堂测验",
            "exam_type": "quiz",
            "starts_at": "2000-01-01T09:00:00+08:00",
        },
    )
    assert past.status_code == 201
    assert [item["title"] for item in client.get("/api/academic-calendar/exams").json()] == [
        "数据结构期末考试"
    ]
    assert len(client.get("/api/academic-calendar/exams?include_past=true").json()) == 2

    invalid = client.patch(
        f'/api/academic-calendar/exams/{future_item["id"]}',
        json={"ends_at": "2099-01-18T08:30:00+08:00"},
        headers=_edit_headers(future_item),
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "EXAM_TIME_INVALID"

    updated = client.patch(
        f'/api/academic-calendar/exams/{future_item["id"]}',
        json={"location": "明德楼 201", "seat_number": "B-06"},
        headers=_edit_headers(future_item),
    )
    assert updated.status_code == 200
    assert updated.json()["location"] == "明德楼 201"
    assert updated.json()["revision"] == 2


def test_calendar_rejects_missing_course_and_cascades_with_course(client):
    missing = client.post(
        "/api/academic-calendar/class-sessions",
        json={
            "course_id": 999,
            "weekday": 2,
            "start_time": "08:00",
            "end_time": "09:30",
        },
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "COURSE_NOT_FOUND"

    course = _course(client, "离散数学")
    created_class = client.post(
        "/api/academic-calendar/class-sessions",
        json={
            "course_id": course["id"],
            "weekday": 2,
            "start_time": "08:00",
            "end_time": "09:30",
        },
    )
    assert created_class.status_code == 201
    created_exam = client.post(
        "/api/academic-calendar/exams",
        json={
            "course_id": course["id"],
            "title": "离散数学期末考试",
            "starts_at": "2099-02-01T14:00:00+08:00",
        },
    )
    assert created_exam.status_code == 201
    assert client.delete(f'/api/courses/{course["id"]}').status_code == 204
    assert client.get("/api/academic-calendar/class-sessions?week=1").json() == []
    assert client.get("/api/academic-calendar/exams").json() == []
