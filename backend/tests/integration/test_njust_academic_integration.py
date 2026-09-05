from datetime import date

from app.api import academic_calendar as academic_calendar_api
from app.services.njust_academic import normalize_njust_calendar, parse_njust_exams, parse_njust_schedule


def _schedule_html():
    return """
    <html><body>
      <table id="dataList">
        <tr><th>#</th><th>课程号</th><th>序号</th><th>课程名</th><th>教师</th><th>时间</th><th>学分</th><th>地点</th><th>类型</th><th>阶段</th></tr>
        <tr><td>1</td><td>MATH101</td><td>01</td><td>高等数学</td><td>张老师</td><td>星期一(01-03小节)</td><td>5</td><td>Ⅳ-A101</td><td>必修</td><td>正常</td></tr>
        <tr><td>2</td><td>PHYS201</td><td>01</td><td>大学物理</td><td>李老师</td><td>星期三(08-10小节)</td><td>4</td><td>Ⅱ-203</td><td>必修</td><td>正常</td></tr>
      </table>
      <table id="kbtable">
        <tr><th>时间</th><th>星期一</th><th>星期二</th><th>星期三</th><th>星期四</th><th>星期五</th><th>星期六</th><th>星期日</th></tr>
        <tr><th>第一大节</th><td><div class="kbcontent1">高等数学<br>1-16(周)</div></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
        <tr><th>第四大节</th><td></td><td></td><td><div class="kbcontent1">大学物理<br>1,3,5,7,9,11,13,15(周)</div></td><td></td><td></td><td></td><td></td></tr>
      </table>
    </body></html>
    """


def _exams_html():
    return """
    <table id="dataList">
      <tr><th>#</th><th>场次</th><th>课程号</th><th>课程</th><th>时间</th><th>考场</th><th>座位</th></tr>
      <tr><td>1</td><td>期末考试</td><td>MATH101</td><td>高等数学</td><td>2027-01-06 09:00~11:00</td><td>Ⅳ-A201</td><td>32</td></tr>
    </table>
    """


def test_njust_parser_uses_data_list_week_hints_and_official_section_times():
    courses = parse_njust_schedule(_schedule_html())
    assert len(courses) == 2
    assert courses[0] == {
        "course_id": "MATH101",
        "name": "高等数学",
        "teacher": "张老师",
        "weeks": "1-16(周)",
        "room": "Ⅳ-A101",
        "weekday": 1,
        "start_section": 1,
        "end_section": 3,
    }
    assert courses[1]["weeks"] == "1,3,5,7,9,11,13,15(周)"
    assert parse_njust_exams(_exams_html())[0]["seat"] == "32"

    key, source_name, items, warnings = normalize_njust_calendar(
        schedule_html=_schedule_html(),
        exams_html=_exams_html(),
        term="2026-2027-1",
        semester_start=date(2026, 9, 7),
        semester_weeks=18,
    )
    assert len(key) == 64
    assert source_name == "南京理工大学教务系统 · 2026-2027-1"
    assert warnings == []
    math = next(item for item in items if item["kind"] == "class_session" and item["course_name"] == "高等数学")
    physics = next(item for item in items if item["kind"] == "class_session" and item["course_name"] == "大学物理")
    exam = next(item for item in items if item["kind"] == "exam")
    assert (math["start_time"].isoformat(), math["end_time"].isoformat()) == ("08:00:00", "10:25:00")
    assert (math["start_week"], math["end_week"], math["week_pattern"]) == (1, 16, "all")
    assert (physics["start_week"], physics["end_week"], physics["week_pattern"]) == (1, 15, "odd")
    assert exam["starts_at"].isoformat() == "2027-01-06T09:00:00+08:00"
    assert exam["seat_number"] == "32"


def test_njust_api_is_one_shot_no_store_and_never_reflects_credentials(client, monkeypatch):
    session_id = "a" * 43
    monkeypatch.setattr(
        academic_calendar_api.njust_session_store,
        "create",
        lambda owner_key: (session_id, "data:image/png;base64,AA=="),
    )
    captcha = client.post("/api/academic-calendar/integrations/njust/captcha")
    assert captcha.status_code == 200
    assert captcha.headers["cache-control"].startswith("no-store")
    assert captcha.json()["session_id"] == session_id

    class FakeSession:
        closed = False

        def close(self):
            self.closed = True

    remote_session = FakeSession()
    monkeypatch.setattr(
        academic_calendar_api.njust_session_store,
        "consume",
        lambda supplied, owner_key: (remote_session, "portal_post"),
    )
    captured = {}

    def fake_fetch(session, **kwargs):
        captured.update(kwargs)
        return _schedule_html(), _exams_html()

    monkeypatch.setattr(academic_calendar_api, "fetch_njust_pages", fake_fetch)
    response = client.post(
        "/api/academic-calendar/integrations/njust/preview",
        json={
            "session_id": session_id,
            "username": "123456789",
            "password": "do-not-store-this",
            "captcha": "AB12",
            "term": "2026-2027-1",
            "semester_start": "2026-09-07",
            "semester_weeks": 18,
            "acknowledge_insecure_transport": True,
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"].startswith("no-store")
    preview = response.json()
    assert preview["credential_policy"] == "ephemeral_memory"
    assert preview["class_count"] == 2
    assert preview["exam_count"] == 1
    assert remote_session.closed is True
    assert captured["strategy"] == "portal_post"
    assert "password" not in preview and "username" not in preview and "session_id" not in preview
    assert "do-not-store-this" not in response.text

    invalid = client.post(
        "/api/academic-calendar/integrations/njust/preview",
        json={
            "session_id": session_id,
            "username": "123456789",
            "password": "validation-secret",
            "captcha": "包含非法字符",
            "term": "bad-term",
            "semester_start": "2026-09-07",
            "acknowledge_insecure_transport": True,
        },
    )
    assert invalid.status_code == 422
    assert invalid.headers["cache-control"].startswith("no-store")
    assert "validation-secret" not in invalid.text
    assert '"input"' not in invalid.text
