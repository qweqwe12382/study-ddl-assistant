"""Guard against turning completed, cancelled and informational notices into tasks."""
import pytest
from datetime import datetime

from extraction_benchmark import extract_case
from app.models.material import Material
from app.services.extraction import _normalize_result
from app.services.llm_provider import RuleBasedProvider, parse_deadline_text


def run_notice(text):
    return extract_case({"filename": "课程通知.txt", "text": text, "source_time": "2026-09-10T09:00:00+08:00"})


@pytest.mark.parametrize("text", [
    "老师已于9月9日18:00上传实验报告参考答案，无需同学再次提交。",
    "原定9月15日14:00的课程说明会已取消，请勿前往，暂不另行安排。",
    "9月12日20:00前不要上传个人信息，课程平台不要求填写此表。",
    "资料上传功能将于9月12日20:00恢复，这是系统维护时间，不是提交截止时间。",
    "请注意：本课程不要求提交读书报告，也没有安排在线测验。",
    "课程公告：9月8日的线下培训已经结束，感谢大家参加。",
])
def test_informational_or_cancelled_actions_do_not_create_tasks(text):
    assert run_notice(text)["tasks"] == []


def test_conditional_registration_keeps_eligibility_in_source():
    text = "仅需补做实验的同学，请于9月14日17:00前登记补做时段；已完成实验者无需登记。"
    result = run_notice(text)
    assert len(result["tasks"]) == 1
    assert result["tasks"][0]["due_local"] == "2026-09-14T17:00"
    assert "仅需补做实验的同学" in result["tasks"][0]["source_quote"]
    assert result["review"] is True


def test_cancelled_requirement_does_not_hide_separate_live_requirement():
    text = "本次无需提交实验报告。请于9月16日19:00前上传课堂展示视频。"
    tasks = run_notice(text)["tasks"]
    assert len(tasks) == 1
    assert "课堂展示视频" in tasks[0]["name"]
    assert tasks[0]["due_local"] == "2026-09-16T19:00"
    assert tasks[0]["source_quote"] in text


def test_independent_actions_retain_their_own_deadlines():
    text = "请于9月16日19:00前上传课堂展示视频；请于9月17日12:00前登记小组答辩时段。"
    tasks = run_notice(text)["tasks"]
    assert len(tasks) == 2
    video = next(task for task in tasks if "课堂展示视频" in task["name"])
    registration = next(task for task in tasks if "小组答辩时段" in task["name"])
    assert video["due_local"] == "2026-09-16T19:00"
    assert registration["due_local"] == "2026-09-17T12:00"
    assert all(task["source_quote"] in text for task in tasks)


def test_changed_submission_method_is_not_a_changed_deadline():
    text = "报告截止9月15日18:00，提交方式改为线上，答疑安排在9月16日19:00。"
    due, warnings = parse_deadline_text(text, datetime(2026, 9, 10, 9))
    assert due is None
    assert "AMBIGUOUS_TASK_DATE" in warnings


def test_clock_colon_does_not_discard_conflicting_source_date():
    text = "作业一原截止9月12日18:00，9月13日20:00前提交，具体待确认。"
    tasks = run_notice(text)["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["due_local"] is None
    assert "9月12日18:00" in tasks[0]["source_quote"]


def test_revoked_invalid_historical_time_keeps_new_explicit_deadline_reviewable():
    text = "更正《操作系统》实验二：此前“10月31日24:00前提交”的说法作废，请于11月2日09:30前提交实验报告。"
    material = Material(
        original_filename="课程通知.txt",
        extracted_text=text,
        source_time=datetime(2026, 10, 30, 9),
        processing_status="processed",
    )
    raw = RuleBasedProvider().extract(text, material.original_filename)

    result = _normalize_result(raw, material, provider_name="local-rules")

    assert len(result.tasks) == 1
    task = result.tasks[0]
    assert task.due_at.isoformat() == "2026-11-02T01:30:00+00:00"
    assert task.source_quote == "请于11月2日09:30前提交实验报告。"
    assert task.source_quote in material.extracted_text
    assert "INVALID_TIME" in task.warnings
    assert task.need_review is True


def test_invalid_time_in_a_cancelled_notice_does_not_create_a_candidate():
    text = "原定10月31日24:00的操作系统实验安全测验取消，请勿前往。"

    assert run_notice(text)["tasks"] == []


@pytest.mark.parametrize("text", [
    "作业9月12日24:00截止，答疑9月11日18:00。",
    "作业9月12日24:00截止，答疑9月11日18:00，补交9月13日20:00。",
])
def test_invalid_deadline_with_other_valid_mentions_stays_ambiguous(text):
    due, warnings = parse_deadline_text(text, datetime(2026, 9, 10, 9))

    assert due is None
    assert "INVALID_TIME" in warnings
    assert "MULTIPLE_DATES_IN_SOURCE" in warnings
    assert "AMBIGUOUS_TASK_DATE" in warnings


@pytest.mark.parametrize("text", [
    "请于9月18日中午前提交实验报告。",
    "请于9月18日上课前提交实验报告。",
    "请于9月18日课前提交实验报告。",
    "请于9月18日下午前提交实验报告。",
])
def test_unquantified_time_constraints_do_not_default_to_end_of_day(text):
    due, warnings = parse_deadline_text(text, datetime(2026, 9, 10, 9))
    result = run_notice(text)

    assert due is None
    assert "AMBIGUOUS_TASK_DATE" in warnings
    assert "TIME_DEFAULTED_TO_END_OF_DAY" not in warnings
    assert result["tasks"][0]["due_local"] is None
    assert result["review"] is True


def test_plain_date_keeps_the_existing_end_of_day_contract():
    due, warnings = parse_deadline_text("请于9月18日前提交实验报告。", datetime(2026, 9, 10, 9))

    assert due == datetime(2026, 9, 18, 23, 59)
    assert "TIME_DEFAULTED_TO_END_OF_DAY" in warnings
    assert "AMBIGUOUS_TASK_DATE" not in warnings


def test_explicit_time_is_not_made_ambiguous_by_a_later_course_after_clause():
    text = "请在明天16:30前填写职业发展问卷，未提交者也可课后补填。"
    due, warnings = parse_deadline_text(text, datetime(2026, 9, 10, 9))
    result = run_notice(text)

    assert due == datetime(2026, 9, 11, 16, 30)
    assert "AMBIGUOUS_TASK_DATE" not in warnings
    assert result["tasks"][0]["due_local"] == "2026-09-11T16:30"
