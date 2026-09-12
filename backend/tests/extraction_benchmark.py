"""Deterministic metrics for the frozen synthetic notification corpus.

This helper intentionally reports detection counts separately from deadline
normalization.  The fixture is a synthetic regression corpus, so these numbers
must not be described as accuracy on real student notifications.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.material import Material
from app.services.extraction import _normalize_result
from app.services.llm_provider import RuleBasedProvider
from app.time import as_local


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "extraction" / "notification_cases.json"
CORPUS_KIND = "frozen_synthetic_notification_cases"
CORPUS_LIMITATION = "Synthetic development regression corpus, not an independent holdout or real-user/OCR accuracy evaluation."


def load_cases(path: Path = FIXTURE_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_case(case: dict[str, Any]) -> dict[str, Any]:
    """Run one case using only its frozen reference timestamp."""

    source_time = datetime.fromisoformat(case["source_time"].replace("Z", "+00:00"))
    material = Material(
        original_filename=case["filename"],
        extracted_text=case["text"],
        source_time=source_time,
        processing_status="processed",
    )
    raw = RuleBasedProvider().extract(case["text"], case["filename"])
    result = _normalize_result(raw, material, provider_name="local-rules")
    return {
        "course_name": result.course_name,
        "review": result.needs_review,
        "tasks": [
            {
                "name": task.name,
                "due_local": (
                    as_local(task.due_at).replace(tzinfo=None).isoformat(timespec="minutes")
                    if task.due_at is not None
                    else None
                ),
                "source_quote": task.source_quote,
            }
            for task in result.tasks
        ],
    }


def evaluate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    tp = fp = fn = 0
    dated_correct = dated_total = 0
    null_correct = null_total = 0
    course_correct = review_correct = 0
    case_results: list[dict[str, Any]] = []

    for case in cases:
        predicted = extract_case(case)
        expected = case["expected"]
        expected_by_name = Counter(task["name"] for task in expected["tasks"])
        predicted_by_name = Counter(task["name"] for task in predicted["tasks"])
        case_tp = sum((expected_by_name & predicted_by_name).values())
        case_fp = sum((predicted_by_name - expected_by_name).values())
        case_fn = sum((expected_by_name - predicted_by_name).values())
        tp += case_tp
        fp += case_fp
        fn += case_fn

        remaining_predictions = list(predicted["tasks"])
        case_dated_correct = case_dated_total = 0
        case_null_correct = case_null_total = 0
        for expected_task in expected["tasks"]:
            # Omitted tasks are failed deadlines too, not exclusions from the
            # denominator. Detection and date scores must expose lost tasks.
            if expected_task["due_local"] is None:
                case_null_total += 1
            else:
                case_dated_total += 1
            match_index = next(
                (index for index, task in enumerate(remaining_predictions) if task["name"] == expected_task["name"]),
                None,
            )
            if match_index is None:
                continue
            actual_task = remaining_predictions.pop(match_index)
            if expected_task["due_local"] is None:
                case_null_correct += actual_task["due_local"] is None
            else:
                case_dated_correct += actual_task["due_local"] == expected_task["due_local"]
        dated_correct += case_dated_correct
        dated_total += case_dated_total
        null_correct += case_null_correct
        null_total += case_null_total
        course_correct += predicted["course_name"] == expected["course_name"]
        review_correct += predicted["review"] == expected["review"]
        case_results.append(
            {
                "id": case["id"],
                "tp": case_tp,
                "fp": case_fp,
                "fn": case_fn,
                "dated_deadlines_correct": case_dated_correct,
                "dated_deadlines_total": case_dated_total,
                "null_deadlines_correct": case_null_correct,
                "null_deadlines_total": case_null_total,
                "course_correct": predicted["course_name"] == expected["course_name"],
                "review_correct": predicted["review"] == expected["review"],
                "predicted": predicted,
            }
        )

    precision_denominator = tp + fp
    recall_denominator = tp + fn
    return {
        "corpus": CORPUS_KIND,
        "limitation": CORPUS_LIMITATION,
        "cases": len(cases),
        "task_detection": {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": tp / precision_denominator if precision_denominator else None,
            "recall": tp / recall_denominator if recall_denominator else None,
        },
        "dated_deadline_exact": {
            "correct": dated_correct,
            "total": dated_total,
            "accuracy": dated_correct / dated_total if dated_total else None,
        },
        "ambiguous_null_deadline": {
            "correct": null_correct,
            "total": null_total,
            "accuracy": null_correct / null_total if null_total else None,
        },
        "course_name_exact": {"correct": course_correct, "total": len(cases)},
        "review_decision_exact": {"correct": review_correct, "total": len(cases)},
        "case_results": case_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    args = parser.parse_args()
    print(json.dumps(evaluate_cases(load_cases(args.fixture)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
