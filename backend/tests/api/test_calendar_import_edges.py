"""Calendar import regressions use synthetic ICS/HTML and the isolated API DB."""

from datetime import date
from html import escape

import pytest

from app.api import academic_calendar as calendar_api
from app.services.njust_academic import _week_ranges, normalize_njust_calendar


def _event(extra="", *, uid="course", start="20260907T080000", end="20260907T090000", name="数学"):
    return f"""BEGIN:VEVENT
UID:{uid}
DTSTART;TZID=Asia/Shanghai:{start}
DTEND;TZID=Asia/Shanghai:{end}
SUMMARY:{name}
{extra}
END:VEVENT"""


def _preview(client, *events):
    response = client.post("/api/academic-calendar/integrations/preview", json={
        "source_name": "边界测试课表", "semester_start": "2026-09-07", "semester_weeks": 18,
        "calendar_text": "BEGIN:VCALENDAR\nVERSION:2.0\n" + "\n".join(events) + "\nEND:VCALENDAR\n",
    })
    assert response.status_code == 200, response.text
    return response.json()


def _sync(client, preview, replace_source=None):
    payload = {key: preview[key] for key in ("source_key", "source_type", "source_name", "items")}
    if replace_source is not None:
        payload["replace_source"] = replace_source
    return client.post("/api/academic-calendar/integrations/sync", json=payload)


def _occurrences(items):
    return {
        (week, item["weekday"])
        for item in items if item["kind"] == "class_session"
        for week in range(item["start_week"], item["end_week"] + 1)
        if item["week_pattern"] == "all"
        or (item["week_pattern"] == "odd" and week % 2 == 1)
        or (item["week_pattern"] == "even" and week % 2 == 0)
    }


@pytest.mark.parametrize("exdate", [
    "EXDATE;TZID=Asia/Shanghai:20260914T080000",
    "EXDATE:20260914T000000Z",
])
def test_exdate_removes_exact_occurrence_and_sync_does_not_restore_it(client, exdate):
    preview = _preview(client, _event(f"RRULE:FREQ=WEEKLY;COUNT=4\n{exdate}"))
    assert _occurrences(preview["items"]) == {(1, 1), (3, 1), (4, 1)}
    assert _sync(client, preview).status_code == 200
    assert _sync(client, preview).json()["unchanged"] == len(preview["items"])
    for week, count in [(1, 1), (2, 0), (3, 1), (4, 1), (5, 0)]:
        rows = client.get(f"/api/academic-calendar/class-sessions?week={week}")
        assert rows.status_code == 200
        assert len(rows.json()) == count


def test_multiple_exdates_and_count_do_not_add_replacement_occurrences(client):
    preview = _preview(client, _event(
        "RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=6\n"
        "EXDATE;TZID=Asia/Shanghai:20260909T080000,20260914T080000\n"
        "EXDATE:20260923T000000Z"
    ))
    assert _occurrences(preview["items"]) == {(1, 1), (2, 3), (3, 1)}


@pytest.mark.parametrize("start,end,rule,expected", [
    ("20260907T080000", "20260907T090000", "FREQ=WEEKLY;BYDAY=MO,WE;COUNT=4", {(1, 1), (1, 3), (2, 1), (2, 3)}),
    ("20260909T080000", "20260909T090000", "FREQ=WEEKLY;BYDAY=MO,WE;COUNT=3", {(1, 3), (2, 1), (2, 3)}),
    ("20260831T080000", "20260831T090000", "FREQ=WEEKLY;BYDAY=MO,WE;COUNT=4", {(1, 1), (1, 3)}),
    ("20260906T080000", "20260906T090000", "FREQ=WEEKLY;INTERVAL=2;WKST=SU;BYDAY=MO,SU;COUNT=4", {(1, 1), (2, 7), (3, 1)}),
    ("20260907T080000", "20260907T090000", "FREQ=WEEKLY;BYDAY=MO,WE;UNTIL=20260916T000000Z", {(1, 1), (1, 3), (2, 1), (2, 3)}),
    ("20260907T080000", "20260907T090000", "FREQ=WEEKLY;BYDAY=MO,WE;UNTIL=20260915T235959Z", {(1, 1), (1, 3), (2, 1)}),
    # A DATE-valued UNTIL is invalid against a datetime DTSTART per RFC 5545,
    # but real exporters emit it; the final day itself must still happen.
    ("20260907T080000", "20260907T090000", "FREQ=WEEKLY;BYDAY=MO,WE;UNTIL=20260921", {(1, 1), (1, 3), (2, 1), (2, 3), (3, 1)}),
    ("20260907T080000", "20260907T090000", "FREQ=WEEKLY;BYDAY=MO;UNTIL=20260913", {(1, 1)}),
])
def test_count_and_until_bound_actual_occurrences(client, start, end, rule, expected):
    preview = _preview(client, _event(f"RRULE:{rule}", start=start, end=end))
    assert _occurrences(preview["items"]) == expected


def test_duration_only_event_imports_with_derived_end(client):
    event = _event("RRULE:FREQ=WEEKLY;COUNT=2").replace(
        "DTEND;TZID=Asia/Shanghai:20260907T090000", "DURATION:PT1H30M"
    )
    preview = _preview(client, event, _event(uid="safe", name="安全课程", start="20260908T100000", end="20260908T110000"))
    duration_item = next(item for item in preview["items"] if item["course_name"] == "数学")
    assert (duration_item["start_time"], duration_item["end_time"]) == ("08:00:00", "09:30:00")
    assert _occurrences(preview["items"]) == {(1, 1), (2, 1), (1, 2)}
    assert _sync(client, preview).json()["created"] == len(preview["items"])


def test_dtend_and_duration_together_prefers_dtend_and_warns(client):
    preview = _preview(client, _event("DURATION:PT2H"), _event(uid="safe", name="安全课程"))
    item = next(item for item in preview["items"] if item["course_name"] == "数学")
    assert (item["start_time"], item["end_time"]) == ("08:00:00", "09:00:00")
    assert any("DTEND 与 DURATION" in message for message in preview["warnings"])


def test_duration_pushing_past_midnight_is_rejected_like_overnight_classes(client):
    event = _event("DURATION:PT3H", start="20260907T230000").replace(
        "DTEND;TZID=Asia/Shanghai:20260907T090000", ""
    )
    preview = _preview(client, event, _event(uid="safe", name="安全课程"))
    assert [item["course_name"] for item in preview["items"]] == ["安全课程"]
    assert any("跨午夜" in message for message in preview["warnings"])


def test_override_series_reports_one_group_warning_instead_of_one_per_component(client):
    preview = _preview(client,
        _event("RRULE:FREQ=WEEKLY;COUNT=4"),
        _event("RECURRENCE-ID;TZID=Asia/Shanghai:20260914T080000", start="20260914T100000", end="20260914T113000"),
        _event("RECURRENCE-ID;TZID=Asia/Shanghai:20260921T080000", start="20260921T100000", end="20260921T113000"),
    )
    assert preview["items"] == []
    override_warnings = [message for message in preview["warnings"] if "RECURRENCE-ID" in message]
    assert len(override_warnings) == 1


def test_changing_split_ranges_requires_visible_review_without_leaving_silent_stale_rows(client):
    first = _preview(client, _event("RRULE:FREQ=WEEKLY;COUNT=6\nEXDATE;TZID=Asia/Shanghai:20260914T080000"))
    assert _sync(client, first).json()["created"] == len(first["items"])
    second = _preview(client, _event("RRULE:FREQ=WEEKLY;COUNT=6\nEXDATE;TZID=Asia/Shanghai:20260928T080000"))
    result = _sync(client, second)
    assert result.status_code == 200
    assert result.json()["created"] == result.json()["updated"] == 0
    assert result.json()["skipped"] == len(second["items"])
    assert {item["reason"] for item in result.json()["conflicts"]} == {"recurrence_changed"}
    assert all("未改写" in item["message"] for item in result.json()["conflicts"])
    # Rejection is atomic for the series, and never silently deletes local data.
    assert client.get("/api/academic-calendar/class-sessions?week=2").json() == []
    assert len(client.get("/api/academic-calendar/class-sessions?week=4").json()) == 1


def test_replace_source_rebuilds_the_whole_schedule_including_manual_rows(client):
    course = client.post("/api/courses", json={"name": "手工课程"}).json()
    assert client.post("/api/academic-calendar/class-sessions", json={
        "course_id": course["id"], "weekday": 4, "start_time": "08:00", "end_time": "09:40",
        "start_week": 1, "end_week": 18,
    }).status_code == 201

    first = _preview(client, _event("RRULE:FREQ=WEEKLY;COUNT=4"), _event(uid="dropped", name="停开课程", start="20260908T100000", end="20260908T113000"))
    result = _sync(client, first, replace_source=True)
    assert result.json()["removed"] == 1  # the manual session was cleared
    assert result.json()["created"] == len(first["items"])
    assert {item["course_name"] for item in client.get("/api/academic-calendar/class-sessions?week=1").json()} == {"数学", "停开课程"}

    second = _preview(client, _event("RRULE:FREQ=WEEKLY;COUNT=2", start="20260907T140000", end="20260907T153000"))
    result = _sync(client, second, replace_source=True)
    assert result.status_code == 200
    body = result.json()
    assert (body["removed"], body["created"], body["skipped"]) == (2, 1, 0)
    week_two = client.get("/api/academic-calendar/class-sessions?week=2").json()
    assert [(row["course_name"], row["start_time"][:5]) for row in week_two] == [("数学", "14:00")]


def test_replace_source_rebuilds_changed_split_ranges_without_conflicts(client):
    first = _preview(client, _event("RRULE:FREQ=WEEKLY;COUNT=6\nEXDATE;TZID=Asia/Shanghai:20260914T080000"))
    assert _sync(client, first, replace_source=True).json()["created"] == len(first["items"])

    second = _preview(client, _event("RRULE:FREQ=WEEKLY;COUNT=6\nEXDATE;TZID=Asia/Shanghai:20260928T080000"))
    result = _sync(client, second, replace_source=True)
    assert result.status_code == 200
    body = result.json()
    assert body["skipped"] == 0 and body["conflicts"] == []
    assert body["created"] == len(second["items"])
    # The new partitioning wins: weeks 1-3 and 5-6, with week 4 excluded.
    rows = {week: client.get(f"/api/academic-calendar/class-sessions?week={week}").json() for week in (2, 4)}
    assert len(rows[2]) == 1 and rows[2][0]["location"] is None
    assert rows[4] == []


@pytest.mark.parametrize("name", ["数学", "数学期末考试"])
def test_cancelled_events_are_not_imported(client, name):
    preview = _preview(client, _event("STATUS:CANCELLED", name=name))
    assert preview["items"] == []
    assert any("已取消" in message for message in preview["warnings"])


def test_cancelled_event_without_uid_is_not_imported(client):
    preview = _preview(client, _event("STATUS:CANCELLED", uid=""))
    assert preview["items"] == []
    assert any("已取消" in message for message in preview["warnings"])


def test_unrecognized_timezone_is_not_silently_assumed_to_be_shanghai(client):
    event = _event().replace("TZID=Asia/Shanghai", "TZID=Unrecognized/Zone")
    preview = _preview(client, event, _event(uid="safe", name="安全课程"))
    assert [item["course_name"] for item in preview["items"]] == ["安全课程"]
    assert any("时区" in message for message in preview["warnings"])


def test_cancelled_override_does_not_resurrect_master_occurrence(client):
    preview = _preview(client,
        _event("RRULE:FREQ=WEEKLY;COUNT=4"),
        _event("RECURRENCE-ID;TZID=Asia/Shanghai:20260914T080000\nSTATUS:CANCELLED", start="20260914T080000", end="20260914T090000"),
        _event(uid="safe", name="安全课程"),
    )
    assert [item["course_name"] for item in preview["items"]] == ["安全课程"]
    assert any("RECURRENCE-ID" in message for message in preview["warnings"])


@pytest.mark.parametrize("extra,reason", [
    ("RRULE:FREQ=DAILY;COUNT=4", "仅支持"),
    ("RRULE:FREQ=WEEKLY;BYDAY=1MO", "BYDAY"),
    ("RRULE:FREQ=WEEKLY;BYDAY=WE", "BYDAY"),
    ("RRULE:FREQ=WEEKLY;BYMONTH=9", "BYMONTH"),
    ("RRULE:FREQ=WEEKLY;COUNT=2;UNTIL=20260916T000000Z", "COUNT"),
    ("RRULE:FREQ=WEEKLY;COUNT=0", "COUNT"),
    ("RDATE;TZID=Asia/Shanghai:20260914T080000", "RDATE"),
    ("EXDATE;VALUE=DATE:20260914", "EXDATE"),
])
def test_unsupported_recurrence_is_visible_and_keeps_other_preview_rows(client, extra, reason):
    preview = _preview(client, _event(extra), _event(uid="safe", name="安全课程"))
    assert [item["course_name"] for item in preview["items"]] == ["安全课程"]
    assert any(reason in message for message in preview["warnings"])


def test_overnight_class_has_usable_empty_preview_instead_of_500(client):
    preview = _preview(client, _event(start="20260907T230000", end="20260908T010000"))
    assert preview["items"] == []
    assert any("跨午夜" in message for message in preview["warnings"])


def test_overnight_exam_remains_supported_and_other_class_still_previews(client):
    preview = _preview(client,
        _event(uid="night-class", start="20260907T230000", end="20260908T010000"),
        _event(uid="exam", name="英语考试", start="20260907T230000", end="20260908T010000"),
        _event(uid="safe", name="安全课程"),
    )
    assert (preview["class_count"], preview["exam_count"]) == (1, 1)
    assert any("跨午夜" in message for message in preview["warnings"])


def _schedule_html(weeks):
    return f'''<table id="kbtable">
      <tr><th>时段</th><th>节次</th><th>星期一</th></tr>
      <tr><td>上午</td><td>1-3</td><td><div class="kbcontent">数学<br>
      <span title="老师">王老师</span><br><span title="周次(节次)">{escape(weeks)}</span>
      <br><span title="教室">A101</span></div></td></tr></table>'''


@pytest.mark.parametrize("weeks,reason", [
    ("20-22周", "超出"), ("16-22周", "超出"), ("0-2周", "超出"),
    ("周次待定", "无法识别"), ("", "未提供"), ("第2-2周(单)", "单双周"),
    ("18-1周", "顺序"), ("1-2节", "无法识别"),
])
def test_school_uncertain_or_out_of_range_weeks_never_become_full_semester(weeks, reason):
    assert _week_ranges(weeks, 18) == []
    _, _, items, warnings = normalize_njust_calendar(
        schedule_html=_schedule_html(weeks), exams_html="", term="2026-2027-1",
        semester_start=date(2026, 9, 7), semester_weeks=18,
    )
    assert items == []
    assert any(reason in message for message in warnings)


@pytest.mark.parametrize("weeks,expected", [
    ("全学期", set(range(1, 19))),
    ("1-16(周)[01-03节]", set(range(1, 17))),
    ("第1–8周（双）", {2, 4, 6, 8}),
    ("1,3,5,8周", {1, 3, 5, 8}),
    ("全学期(单周)", set(range(1, 19, 2))),
])
def test_school_explicit_weeks_preserve_exact_occurrence_set(weeks, expected):
    ranges = _week_ranges(weeks, 18)
    assert {
        week for start, end, pattern in ranges for week in range(start, end + 1)
        if pattern == "all" or (pattern == "odd" and week % 2) or (pattern == "even" and not week % 2)
    } == expected


def test_school_empty_preview_keeps_warning_and_closes_session(client, monkeypatch):
    class Session:
        closed = False
        def close(self):
            self.closed = True
    session = Session()
    monkeypatch.setattr(calendar_api.njust_session_store, "consume", lambda *_: (session, "test"))
    monkeypatch.setattr(calendar_api, "fetch_njust_pages", lambda *_args, **_kwargs: (_schedule_html("周次待定"), ""))
    response = client.post("/api/academic-calendar/integrations/njust/preview", json={
        "session_id": "a" * 43, "username": "test", "password": "not-reflected", "captcha": "1234",
        "term": "2026-2027-1", "semester_start": "2026-09-07", "acknowledge_insecure_transport": True,
    })
    assert response.status_code == 200, response.text
    assert response.json()["items"] == [] and response.json()["warnings"]
    assert session.closed and "not-reflected" not in response.text
    assert response.headers["cache-control"].startswith("no-store")


@pytest.mark.parametrize("start,end,pattern", [(2, 2, "odd"), (3, 3, "even")])
def test_no_occurrence_class_rejected_on_create_and_import(client, start, end, pattern):
    course = client.post("/api/courses", json={"name": "数学"}).json()
    payload = {"course_id": course["id"], "weekday": 1, "start_time": "08:00", "end_time": "09:00",
               "start_week": start, "end_week": end, "week_pattern": pattern}
    response = client.post("/api/academic-calendar/class-sessions", json=payload)
    assert response.status_code == 422
    preview = _preview(client, _event())
    preview["items"][0].update(start_week=start, end_week=end, week_pattern=pattern)
    assert _sync(client, preview).status_code == 422
    assert all(client.get(f"/api/academic-calendar/class-sessions?week={week}").json() == [] for week in range(1, 5))


def test_partial_patch_cannot_turn_visible_course_into_zero_occurrences(client):
    course = client.post("/api/courses", json={"name": "数学"}).json()
    created = client.post("/api/academic-calendar/class-sessions", json={
        "course_id": course["id"], "weekday": 1, "start_time": "08:00", "end_time": "09:00",
        "start_week": 2, "end_week": 2, "week_pattern": "even",
    }).json()
    response = client.patch(f'/api/academic-calendar/class-sessions/{created["id"]}',
        json={"week_pattern": "odd"}, headers={"If-Match": f'"{created["navigation_key"]}:{created["revision"]}"'})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CLASS_WEEK_PATTERN_EMPTY"
    rows = client.get("/api/academic-calendar/class-sessions?week=2").json()
    assert len(rows) == 1 and rows[0]["revision"] == created["revision"]


def test_malformed_normalized_row_is_explained_in_preview(client, monkeypatch):
    preview = _preview(client, _event())
    bad = {**preview["items"][0], "end_time": "07:00"}
    monkeypatch.setattr(calendar_api, "parse_ical_calendar", lambda **_: (preview["source_key"], [bad], []))
    response = _preview(client, _event())
    assert response["items"] == []
    assert any("时间或周次" in message for message in response["warnings"])
