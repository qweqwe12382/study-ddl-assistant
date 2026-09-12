"""Run a frozen independent synthetic corpus without turning results into tests."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "tests"))
from extraction_benchmark import extract_case
from app.time import as_local


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(expected, predicted):
    names = Counter(task["name"] for task in expected)
    actual_names = Counter(task["name"] for task in predicted)
    exact = sum((names & actual_names).values())
    remaining = list(predicted)
    dated_total = dated_correct = null_total = null_correct = 0
    for task in expected:
        due = task["due_local"]
        dated_total += due is not None
        null_total += due is None
        match = next((i for i, item in enumerate(remaining) if item["name"] == task["name"]), None)
        if match is None:
            continue
        actual = remaining.pop(match)
        dated_correct += due is not None and actual["due_local"] == due
        null_correct += due is None and actual["due_local"] is None
    return {"exact_name_tp": exact, "exact_name_fp": sum(actual_names.values()) - exact,
            "exact_name_fn": sum(names.values()) - exact, "dated_correct": dated_correct,
            "dated_total": dated_total, "null_correct": null_correct, "null_total": null_total}


def evaluate(path):
    corpus = json.loads(path.read_text(encoding="utf-8"))
    cases = corpus["cases"]
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Case IDs must be unique")
    results = []
    for case in cases:
        expected = [{"name": item["name"], "due_local": as_local(datetime.fromisoformat(item["due_at"])).replace(tzinfo=None).isoformat(timespec="minutes") if item["due_at"] else None} for item in case["expected_tasks"]]
        error = None
        try:
            predicted = extract_case({**case, "filename": "课程通知.txt"})
        except Exception as caught:  # Keep a frozen corpus evaluable when one input is malformed.
            predicted = {"tasks": []}
            error = {
                "type": type(caught).__name__,
                "code": getattr(caught, "code", None),
                "message": str(caught),
            }
        results.append({"id": case["id"], "category": case["category"], "expected": expected,
                        "predicted": predicted, "scores": score(expected, predicted["tasks"]),
                        "annotation_note": case["annotation_note"], "error": error})
    totals = dict(Counter({key: sum(row["scores"][key] for row in results) for key in results[0]["scores"]}))
    coverage = {
        "positive_notices": sum(bool(row["expected"]) for row in results),
        "positive_notices_without_candidates": sum(bool(row["expected"]) and not row["predicted"]["tasks"] for row in results),
        "negative_notices": sum(not row["expected"] for row in results),
        "negative_notices_without_candidates": sum(not row["expected"] and not row["predicted"]["tasks"] for row in results),
        "expected_tasks": sum(len(row["expected"]) for row in results),
        "predicted_candidates": sum(len(row["predicted"]["tasks"]) for row in results),
        "case_errors": sum(row["error"] is not None for row in results),
    }
    code = [ROOT / "backend/app/services/llm_provider.py", ROOT / "backend/app/services/extraction.py", ROOT / "backend/tests/extraction_benchmark.py", Path(__file__)]
    return {"evaluated_at": datetime.now(timezone.utc).isoformat(), "corpus_sha256": sha(path),
            "code_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in code},
            "provenance": corpus["provenance"], "cases": len(cases),
            "limitation": "Independently authored synthetic text only; exact task-name matching is not semantic task detection. Missing/name-mismatched tasks count against date scores. No OCR, real students, external model, or human correction timing measured. Do not tune and then relabel this corpus as unseen.",
            "totals": totals, "coverage": coverage, "case_results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.corpus)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"cases": result["cases"], "totals": result["totals"], "coverage": result["coverage"], "corpus_sha256": result["corpus_sha256"]}, ensure_ascii=False))
