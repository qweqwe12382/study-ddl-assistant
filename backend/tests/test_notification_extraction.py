from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.material import Material
from app.services import extraction
from app.services.extraction import _normalize_result
from app.services.llm_provider import RuleBasedProvider

from extraction_benchmark import CORPUS_KIND, evaluate_cases, load_cases


def test_benchmark_counts_omitted_deadlines_and_false_positives(monkeypatch):
    import extraction_benchmark

    monkeypatch.setattr(extraction_benchmark, "extract_case", lambda _: {
        "course_name": "数据结构", "review": True, "tasks": [
            {"name": "实验一", "due_local": "2026-09-11T19:00"},
            {"name": "多报的任务", "due_local": "2026-09-12T18:00"},
        ],
    })
    result = evaluate_cases([{"id": "metric-audit", "expected": {
        "course_name": "数据结构", "review": True, "tasks": [
            {"name": "实验一", "due_local": "2026-09-11T18:00"},
            {"name": "遗漏的任务", "due_local": "2026-09-12T18:00"},
            {"name": "遗漏的歧义任务", "due_local": None},
        ],
    }}])
    assert result["task_detection"] == {"tp": 1, "fp": 1, "fn": 2, "precision": .5, "recall": 1 / 3}
    assert result["dated_deadline_exact"] == {"correct": 0, "total": 2, "accuracy": 0}
    assert result["ambiguous_null_deadline"] == {"correct": 0, "total": 1, "accuracy": 0}


def test_frozen_synthetic_notification_benchmark_is_repeatable_and_exact():
    cases = load_cases()
    assert len(cases) == 42
    assert len({case["id"] for case in cases}) == 42

    first = evaluate_cases(cases)
    second = evaluate_cases(cases)
    assert first == second
    assert first["corpus"] == CORPUS_KIND
    assert first["task_detection"] == {"tp": 43, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0}
    assert first["dated_deadline_exact"] == {"correct": 39, "total": 39, "accuracy": 1.0}
    assert first["ambiguous_null_deadline"] == {"correct": 4, "total": 4, "accuracy": 1.0}
    assert first["course_name_exact"] == {"correct": 42, "total": 42}
    assert first["review_decision_exact"] == {"correct": 42, "total": 42}


def test_relative_deadline_uses_material_source_time_when_clock_moves(monkeypatch):
    frozen_source_time = datetime(2026, 9, 9, 2, tzinfo=timezone.utc)
    material = Material(
        original_filename="高等数学-作业通知.md",
        extracted_text="本周五18:00提交作业一",
        source_time=frozen_source_time,
        processing_status="processed",
    )
    raw = RuleBasedProvider().extract(material.extracted_text, material.original_filename)
    monkeypatch.setattr(extraction, "utc_now", lambda: datetime(2035, 1, 1, tzinfo=timezone.utc))

    result = _normalize_result(raw, material, provider_name="local-rules")

    assert result.tasks[0].due_at == datetime(2026, 9, 11, 10, tzinfo=timezone.utc)


def test_multiline_quote_is_verbatim_and_keeps_each_deadline_with_its_task():
    text = "课程：数据结构\n实验二报告\n截止：2026-09-11 18:00\n作业三\n截止：2026-09-12 19:30"
    raw = RuleBasedProvider().extract(text, "实验通知.txt")
    material = Material(
        original_filename="实验通知.txt",
        extracted_text=text,
        source_time=datetime(2026, 9, 9, 2, tzinfo=timezone.utc),
        processing_status="processed",
    )

    result = _normalize_result(raw, material, provider_name="local-rules")

    assert [(task.name, task.source_quote) for task in result.tasks] == [
        ("实验二报告", "实验二报告\n截止：2026-09-11 18:00"),
        ("作业三", "作业三\n截止：2026-09-12 19:30"),
    ]
    assert [task.due_at for task in result.tasks] == [
        datetime(2026, 9, 11, 10, tzinfo=timezone.utc),
        datetime(2026, 9, 12, 11, 30, tzinfo=timezone.utc),
    ]


def test_same_day_reschedule_keeps_verbatim_quote_and_requires_review():
    text = "作业一原截止9月12日18:00，延期到9月12日20:00"
    raw = RuleBasedProvider().extract(text, "高等数学-作业通知.md")
    material = Material(
        original_filename="高等数学-作业通知.md",
        extracted_text=text,
        source_time=datetime(2026, 9, 9, 2, tzinfo=timezone.utc),
        processing_status="processed",
    )

    result = _normalize_result(raw, material, provider_name="local-rules")

    assert len(result.tasks) == 1
    assert result.tasks[0].source_quote == text
    assert result.tasks[0].due_at is None
    assert "AMBIGUOUS_TASK_DATE" in result.tasks[0].warnings
    assert result.tasks[0].need_review is True


@pytest.mark.parametrize(
    ("text", "expected_utc"),
    [
        ("实验一2026年9月11日晚上8点30分提交", datetime(2026, 9, 11, 12, 30, tzinfo=timezone.utc)),
        ("实验二2026年9月11日18时30分提交", datetime(2026, 9, 11, 10, 30, tzinfo=timezone.utc)),
        ("实验三2026-09-11T18:30提交", datetime(2026, 9, 11, 10, 30, tzinfo=timezone.utc)),
        ("实验四2026年9月11日上午12点提交", datetime(2026, 9, 10, 16, tzinfo=timezone.utc)),
    ],
)
def test_deadline_minutes_and_midnight_are_not_silently_lost(text, expected_utc):
    raw = RuleBasedProvider().extract(text, "数字逻辑-实验通知.md")
    material = Material(
        original_filename="数字逻辑-实验通知.md",
        extracted_text=text,
        source_time=datetime(2026, 9, 9, 2, tzinfo=timezone.utc),
        processing_status="processed",
    )

    result = _normalize_result(raw, material, provider_name="local-rules")

    assert result.tasks[0].due_at == expected_utc
    assert "TIME_DEFAULTED_TO_END_OF_DAY" not in result.tasks[0].warnings
