import importlib.util
import json
from pathlib import Path


spec = importlib.util.spec_from_file_location("independent_evaluation", Path(__file__).resolve().parents[2] / "scripts/evaluate_independent_notices.py")
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def test_missing_names_and_wrong_dates_remain_in_denominators():
    expected = [{"name": "报告", "due_local": "2026-09-11T18:00"}, {"name": "遗漏", "due_local": "2026-09-12T18:00"}, {"name": "待定", "due_local": None}]
    predicted = [{"name": "报告", "due_local": "2026-09-11T20:00"}, {"name": "误报", "due_local": None}]
    assert evaluation.score(expected, predicted) == {"exact_name_tp": 1, "exact_name_fp": 1, "exact_name_fn": 2, "dated_correct": 0, "dated_total": 2, "null_correct": 0, "null_total": 1}


def test_duplicate_names_cannot_reuse_one_prediction():
    task = {"name": "作业", "due_local": None}
    assert evaluation.score([task, task], [task]) == {"exact_name_tp": 1, "exact_name_fp": 0, "exact_name_fn": 1, "dated_correct": 0, "dated_total": 0, "null_correct": 1, "null_total": 2}


def test_evaluation_collects_a_case_error_and_scores_its_expected_task_as_missed(monkeypatch, tmp_path):
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(json.dumps({"provenance": {"kind": "test"}, "cases": [{
        "id": "bad-date", "category": "test", "text": "bad", "source_time": "2026-09-10T01:00:00+00:00",
        "expected_tasks": [
            {"name": "提交报告", "due_at": "2026-09-11T10:00:00+00:00"},
            {"name": "待定任务", "due_at": None},
        ], "annotation_note": "test",
    }]}), encoding="utf-8")

    def fail_for_case(_case):
        raise RuntimeError("invalid historical time")

    monkeypatch.setattr(evaluation, "extract_case", fail_for_case)
    result = evaluation.evaluate(corpus_path)

    assert result["totals"] == {"exact_name_tp": 0, "exact_name_fp": 0, "exact_name_fn": 2, "dated_correct": 0, "dated_total": 1, "null_correct": 0, "null_total": 1}
    assert result["coverage"]["case_errors"] == 1
    assert result["case_results"][0]["predicted"] == {"tasks": []}
    assert result["case_results"][0]["error"] == {"type": "RuntimeError", "code": None, "message": "invalid historical time"}
