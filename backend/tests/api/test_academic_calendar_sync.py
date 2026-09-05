def _calendar(location="博学楼 B203", course_uid="math-2026"):
    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Campus Test//Academic Calendar//CN
X-WR-CALNAME:2026 秋季学期
BEGIN:VEVENT
UID:{course_uid}
DTSTART;TZID=Asia/Shanghai:20260907T080000
DTEND;TZID=Asia/Shanghai:20260907T094000
RRULE:FREQ=WEEKLY;COUNT=18;BYDAY=MO
SUMMARY:高等数学
LOCATION:{location}
DESCRIPTION:周老师
END:VEVENT
BEGIN:VEVENT
UID:english-odd-2026
DTSTART;TZID=Asia/Shanghai:20260908T100000
DTEND;TZID=Asia/Shanghai:20260908T114000
RRULE:FREQ=WEEKLY;INTERVAL=2;COUNT=9;BYDAY=TU
SUMMARY:大学英语
LOCATION:外语楼 302
END:VEVENT
BEGIN:VEVENT
UID:linear-exam-2026
DTSTART;TZID=Asia/Shanghai:20261120T140000
DTEND;TZID=Asia/Shanghai:20261120T153000
SUMMARY:线性代数期中考试
LOCATION:明德楼 201
END:VEVENT
END:VCALENDAR
"""


def _preview(client, calendar_text=None, source_name="学校教务处"):
    response = client.post(
        "/api/academic-calendar/integrations/preview",
        json={
            "source_type": "ical",
            "source_name": source_name,
            "semester_start": "2026-09-07",
            "semester_weeks": 18,
            "calendar_text": calendar_text or _calendar(),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _sync(client, preview, items=None):
    return client.post(
        "/api/academic-calendar/integrations/sync",
        json={
            "source_key": preview["source_key"],
            "source_type": preview["source_type"],
            "source_name": preview["source_name"],
            "items": items or preview["items"],
        },
    )


def _edit_headers(item):
    return {"If-Match": f'"{item["navigation_key"]}:{item["revision"]}"'}


def test_ical_preview_extracts_weekly_odd_week_and_exam_without_credentials(client):
    preview = _preview(client)
    assert preview["credential_policy"] == "not_collected"
    assert preview["class_count"] == 2
    assert preview["exam_count"] == 1
    math = next(item for item in preview["items"] if item["course_name"] == "高等数学")
    english = next(item for item in preview["items"] if item["course_name"] == "大学英语")
    exam = next(item for item in preview["items"] if item["kind"] == "exam")
    assert (math["weekday"], math["start_week"], math["end_week"], math["week_pattern"]) == (1, 1, 18, "all")
    assert math["teacher"] == "周老师"
    assert (english["weekday"], english["start_week"], english["end_week"], english["week_pattern"]) == (2, 1, 17, "odd")
    assert exam["course_name"] == "线性代数"
    assert exam["exam_type"] == "midterm"
    assert "calendar_text" not in preview

    rejected_credentials = client.post(
        "/api/academic-calendar/integrations/preview",
        json={
            "source_type": "ical",
            "source_name": "学校教务处",
            "semester_start": "2026-09-07",
            "calendar_text": _calendar(),
            "password": "must-not-be-collected",
        },
    )
    assert rejected_credentials.status_code == 422


def test_sync_creates_then_updates_without_overwriting_local_changes(client):
    preview = _preview(client)
    first = _sync(client, preview)
    assert first.status_code == 200, first.text
    assert first.json() == {
        "created": 3,
        "updated": 0,
        "unchanged": 0,
        "skipped": 0,
        "courses_created": 3,
        "conflicts": [],
    }
    assert len(client.get("/api/academic-calendar/class-sessions?week=1").json()) == 2
    assert client.get("/api/academic-calendar/class-sessions?week=1").json()[0]["teacher"] == "周老师"
    assert len(client.get("/api/academic-calendar/class-sessions?week=2").json()) == 1
    assert client.get("/api/academic-calendar/exams?include_past=true").json()[0]["starts_at"] == "2026-11-20T06:00:00Z"

    repeated = _sync(client, preview)
    assert repeated.status_code == 200
    assert repeated.json()["unchanged"] == 3

    changed_preview = _preview(client, _calendar(location="博学楼 B202"))
    changed_math = [item for item in changed_preview["items"] if item["course_name"] == "高等数学"]
    changed = _sync(client, changed_preview, changed_math)
    assert changed.status_code == 200
    assert changed.json()["updated"] == 1
    local_math = client.get("/api/academic-calendar/class-sessions?week=1").json()[0]
    assert local_math["location"] == "博学楼 B202"

    local_edit = client.patch(
        f'/api/academic-calendar/class-sessions/{local_math["id"]}',
        json={"location": "我改成的教室"},
        headers=_edit_headers(local_math),
    )
    assert local_edit.status_code == 200
    remote_again = _preview(client, _calendar(location="博学楼 B201"))
    remote_math = [item for item in remote_again["items"] if item["course_name"] == "高等数学"]
    protected = _sync(client, remote_again, remote_math)
    assert protected.status_code == 200
    assert protected.json()["skipped"] == 1
    assert protected.json()["conflicts"][0]["reason"] == "local_changed"
    assert client.get("/api/academic-calendar/class-sessions?week=1").json()[0]["location"] == "我改成的教室"


def test_sync_skips_schedule_conflict_and_does_not_create_or_restore_rows(client):
    course = client.post("/api/courses", json={"name": "人工课程"}).json()
    manual = client.post(
        "/api/academic-calendar/class-sessions",
        json={
            "course_id": course["id"],
            "weekday": 1,
            "start_time": "08:30",
            "end_time": "10:00",
            "start_week": 1,
            "end_week": 18,
        },
    )
    assert manual.status_code == 201
    preview = _preview(client)
    math = [item for item in preview["items"] if item["course_name"] == "高等数学"]
    result = _sync(client, preview, math)
    assert result.status_code == 200
    assert result.json()["skipped"] == 1
    assert result.json()["courses_created"] == 0
    assert result.json()["conflicts"][0]["reason"] == "schedule_conflict"
    assert [item["name"] for item in client.get("/api/courses").json()] == ["人工课程"]

    safe_preview = _preview(client, _calendar(course_uid="safe-math").replace("T080000", "T140000").replace("T094000", "T154000"), "第二教务来源")
    safe_math = [item for item in safe_preview["items"] if item["course_name"] == "高等数学"]
    created = _sync(client, safe_preview, safe_math)
    assert created.json()["created"] == 1
    imported = next(item for item in client.get("/api/academic-calendar/class-sessions?week=1").json() if item["course_name"] == "高等数学")
    assert client.delete(
        f'/api/academic-calendar/class-sessions/{imported["id"]}', headers=_edit_headers(imported)
    ).status_code == 204
    missing = _sync(client, safe_preview, safe_math)
    assert missing.json()["skipped"] == 1
    assert missing.json()["conflicts"][0]["reason"] == "target_unavailable"


def test_preview_rejects_invalid_and_unsupported_only_calendars(client):
    invalid = client.post(
        "/api/academic-calendar/integrations/preview",
        json={
            "source_name": "学校教务处",
            "semester_start": "2026-09-07",
            "calendar_text": "not-an-ical-file",
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] in {"CALENDAR_INVALID", "CALENDAR_EMPTY"}

    all_day = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:all-day
DTSTART;VALUE=DATE:20260907
DTEND;VALUE=DATE:20260908
SUMMARY:校庆放假
END:VEVENT
END:VCALENDAR
"""
    empty = client.post(
        "/api/academic-calendar/integrations/preview",
        json={
            "source_name": "学校教务处",
            "semester_start": "2026-09-07",
            "calendar_text": all_day,
        },
    )
    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "CALENDAR_EMPTY"
