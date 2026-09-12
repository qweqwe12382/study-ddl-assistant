"""Focused regression checks for student-action notification extraction."""

from datetime import datetime, timezone

from app.models.material import Material
from app.services.extraction import _normalize_result
from app.services.llm_provider import RuleBasedProvider
from app.time import as_local


REFERENCE = datetime(2026, 9, 10, 1, tzinfo=timezone.utc)


def extract_notice(text: str, filename: str = "课程通知.txt"):
    material = Material(
        original_filename=filename,
        extracted_text=text,
        source_time=REFERENCE,
        processing_status="processed",
    )
    raw = RuleBasedProvider().extract(text, filename)
    return _normalize_result(raw, material, provider_name="local-rules")


def local_minute(value):
    return as_local(value).replace(tzinfo=None).isoformat(timespec="minutes") if value else None


def test_event_date_is_inherited_by_following_participation_requirement():
    text = "研究方法线上说明会改到9月18日19:30。请选修该课程的同学参加。"
    result = extract_notice(text)

    assert len(result.tasks) == 1
    assert result.tasks[0].name == "参加研究方法线上说明会"
    assert local_minute(result.tasks[0].due_at) == "2026-09-18T19:30"
    assert result.tasks[0].source_quote == text
    assert "CONDITIONAL_AUDIENCE" in result.tasks[0].warnings


def test_action_like_nouns_do_not_override_the_student_action_or_duplicate_event():
    text = "实验室准入培训安排在下周，周一还是周三等待场地确认。首次进入实验室的同学需要参加。"
    result = extract_notice(text)

    assert len(result.tasks) == 1
    assert result.tasks[0].name == "参加实验室准入培训"
    assert result.tasks[0].due_at is None
    assert "AMBIGUOUS_TASK_DATE" in result.tasks[0].warnings


def test_form_noun_does_not_hide_the_fill_action_and_morning_time():
    result = extract_notice("请在9月19日早上7:05前填写住宿登记表。")

    assert len(result.tasks) == 1
    assert result.tasks[0].name == "填写住宿登记表"
    assert local_minute(result.tasks[0].due_at) == "2026-09-19T07:05"


def test_vague_submission_date_keeps_the_actual_work_item_for_review():
    result = extract_notice("《数字信号处理》课程小论文请近期完成，提交日期待课堂确认。")

    assert len(result.tasks) == 1
    assert result.tasks[0].name == "完成《数字信号处理》课程小论文"
    assert result.tasks[0].due_at is None
    assert result.tasks[0].need_review is True


def test_datetime_claim_conflicting_with_verbatim_source_is_rejected():
    text = "请在2026年9月20日18:00前上传演示录像。"
    material = Material(
        original_filename="课程通知.txt",
        extracted_text=text,
        source_time=REFERENCE,
        processing_status="processed",
    )
    raw = {
        "tasks": [{
            "name": "上传演示录像",
            "due_at": datetime(2026, 9, 21, 10, tzinfo=timezone.utc),
            "source_quote": text,
            "confidence": 0.9,
        }],
    }

    result = _normalize_result(raw, material, provider_name="openai-compatible")

    assert result.tasks[0].due_at is None
    assert "DATE_CONFLICT_WITH_SOURCE" in result.tasks[0].warnings


def test_task_filename_cannot_revive_a_cancelled_event():
    result = extract_notice("原定9月20日14:00的答辩已取消，请勿到场。", "高等数学-作业通知.md")

    assert result.tasks == []
