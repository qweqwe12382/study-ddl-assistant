"""Frozen, versioned learning-rhythm summaries and comparisons.

The live M8.8 calculation remains read-only. M8.9 saves a deliberately small,
aggregate projection only while a weekly snapshot is current; it becomes
evidence when that snapshot closes. No historical summary is reconstructed.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import WeeklyReviewSnapshot
from app.services.learning_trends import MIN_TREND_SAMPLES, TREND_WINDOW_DAYS, build_learning_trends
from app.time import as_utc, utc_now


MAX_HISTORY_WINDOWS = 12
MIN_COMPARABLE_WINDOWS = 2
M8_8_RHYTHM_RULESET = "m8.8"
RHYTHM_SUMMARY_VERSION = "m8.9.m8.8-rhythm-v1"
RHYTHM_SUMMARY_UNKNOWN_POLICY = (
    "missing actual_minutes, difficulty, or completed_at stays unknown/excluded; "
    "no default duration or difficulty is inferred"
)
_COMPARISON_SIGNAL_CODES = (
    "learning_day_distribution", "longest_idle_gap", "load_concentration", "completion_pace",
)


def build_persisted_rhythm_summary(db: Session, *, evaluated_at) -> dict[str, Any]:
    """Build an M8.8-compatible aggregate with no task-level identity or text."""

    trends = build_learning_trends(db, evaluated_at=evaluated_at)
    signals = {
        signal["code"]: {
            "status": signal["status"], "value": signal["value"], "direction": signal["direction"],
        }
        for signal in trends["signals"] if signal["code"] in _COMPARISON_SIGNAL_CODES
    }
    return {
        "summary_version": RHYTHM_SUMMARY_VERSION,
        "rhythm_ruleset": M8_8_RHYTHM_RULESET,
        "status": trends["status"],
        "window_start": trends["window_start"].isoformat(),
        "window_end": trends["window_end"].isoformat(),
        "window_days": TREND_WINDOW_DAYS,
        "minimum_sample_count": MIN_TREND_SAMPLES,
        "sample_count": trends["sample_count"],
        "known_count": trends["known_count"],
        "unknown_count": trends["unknown_count"],
        "signals": signals,
        "calculation_basis": {
            "window_semantics": "last 28 China-local calendar dates, [window_start, window_end)",
            "sample_rule": "status=completed, completed_at in window, actual_minutes and difficulty explicitly supplied",
            "unknown_policy": RHYTHM_SUMMARY_UNKNOWN_POLICY,
            "source_policy": "aggregate-only; task names, ids, descriptions, paths and raw payloads are not persisted",
        },
    }


def _summary(snapshot: WeeklyReviewSnapshot) -> dict[str, Any] | None:
    value = snapshot.rhythm_summary
    return value if isinstance(value, dict) and value else None


def _summary_status(summary: dict[str, Any] | None) -> str | None:
    value = summary.get("status") if summary else None
    return value if isinstance(value, str) and value in {"known", "partial", "unknown"} else None


def _nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _well_formed_summary(summary: dict[str, Any]) -> bool:
    """Validate persisted JSON before using it in a comparison response.

    Snapshot JSON is historical evidence and may outlive an older application
    version or a manual recovery.  It is never repaired from this GET; an
    invalid shape is simply not comparable.
    """

    signals = summary.get("signals")
    if not isinstance(signals, dict) or not isinstance(summary.get("calculation_basis"), dict):
        return False
    if not all(_nonnegative_int(summary.get(field)) for field in ("sample_count", "known_count", "unknown_count")):
        return False
    for code in _COMPARISON_SIGNAL_CODES:
        signal = signals.get(code)
        if not isinstance(signal, dict) or _summary_status(signal) is None:
            return False
        value = signal.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float, str, type(None))):
            return False
        direction = signal.get("direction")
        if direction is not None and not isinstance(direction, str):
            return False
    return True


def _closed_window(snapshot: WeeklyReviewSnapshot) -> dict[str, Any]:
    summary = _summary(snapshot)
    return {
        "snapshot_id": snapshot.id,
        "window_key": snapshot.window_key,
        "window_start": as_utc(snapshot.window_start),
        "window_end": as_utc(snapshot.window_end),
        "snapshot_status": snapshot.snapshot_status,
        "ruleset_version": snapshot.ruleset_version,
        "evidence_digest": snapshot.evidence_digest,
        "rhythm_summary_version": summary.get("summary_version") if summary and isinstance(summary.get("summary_version"), str) else None,
        "rhythm_summary_status": _summary_status(summary),
    }


def _same_caliber(first: dict[str, Any], second: dict[str, Any]) -> bool:
    first_basis = first.get("calculation_basis") if isinstance(first.get("calculation_basis"), dict) else {}
    second_basis = second.get("calculation_basis") if isinstance(second.get("calculation_basis"), dict) else {}
    return all((
        first.get("summary_version") == second.get("summary_version") == RHYTHM_SUMMARY_VERSION,
        first.get("rhythm_ruleset") == second.get("rhythm_ruleset") == M8_8_RHYTHM_RULESET,
        first.get("window_days") == second.get("window_days") == TREND_WINDOW_DAYS,
        first.get("minimum_sample_count") == second.get("minimum_sample_count") == MIN_TREND_SAMPLES,
        first_basis.get("window_semantics") == second_basis.get("window_semantics"),
        first_basis.get("sample_rule") == second_basis.get("sample_rule"),
        first_basis.get("unknown_policy") == second_basis.get("unknown_policy") == RHYTHM_SUMMARY_UNKNOWN_POLICY,
    ))


def _has_minimum_samples(summary: dict[str, Any]) -> bool:
    return isinstance(summary.get("known_count"), int) and summary["known_count"] >= MIN_TREND_SAMPLES


def _unavailable_comparison(
    reasons: list[str], *, closed_count: int, first: WeeklyReviewSnapshot | None = None,
    second: WeeklyReviewSnapshot | None = None, first_summary: dict[str, Any] | None = None,
    second_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summaries = [summary for summary in (first_summary, second_summary) if summary]
    return {
        "status": "unknown", "comparable": False, "reason_codes": list(dict.fromkeys(reasons)),
        "sample_count": sum(summary.get("sample_count", 0) for summary in summaries if _nonnegative_int(summary.get("sample_count"))),
        "known_count": sum(summary.get("known_count", 0) for summary in summaries if _nonnegative_int(summary.get("known_count"))),
        "unknown_count": sum(summary.get("unknown_count", 0) for summary in summaries if _nonnegative_int(summary.get("unknown_count"))),
        "compared_snapshot_ids": [snapshot.id for snapshot in (first, second) if snapshot is not None],
        "source_refs": [],
        "limitations": [
            "旧快照、当前窗口、摘要口径不一致或样本不足时均不可比；不会补造、重算或回写历史摘要。",
            "不会使用实时 M8.8 趋势、周回顾指标或当前任务反馈替代缺失的冻结摘要。",
            "比较接口只读，不会写入任务、计划、课程校准或自动动作。",
        ],
        "calculation_basis": {
            "required_snapshot_status": "closed", "required_summary_version": RHYTHM_SUMMARY_VERSION,
            "required_minimum_sample_count": MIN_TREND_SAMPLES,
            "current_window_policy": "current snapshots and live M8.8 trends are excluded from historical comparison",
            "closed_snapshot_count": closed_count,
        },
    }


def _comparison(first: WeeklyReviewSnapshot | None, second: WeeklyReviewSnapshot | None, *, closed_count: int) -> dict[str, Any]:
    """Compare exactly the two newest closed snapshots, or explicitly refuse."""

    reasons: list[str] = []
    if closed_count < MIN_COMPARABLE_WINDOWS:
        reasons.append("insufficient_closed_snapshots")
    if first is None or second is None:
        return _unavailable_comparison(reasons or ["insufficient_closed_snapshots"], closed_count=closed_count)

    first_summary, second_summary = _summary(first), _summary(second)
    if first_summary is None or second_summary is None:
        reasons.append("legacy_snapshot_missing_rhythm_summary")
    elif not _well_formed_summary(first_summary) or not _well_formed_summary(second_summary):
        reasons.append("invalid_rhythm_summary")
    elif not _same_caliber(first_summary, second_summary):
        reasons.append("rhythm_summary_caliber_mismatch")
    elif not _has_minimum_samples(first_summary) or not _has_minimum_samples(second_summary):
        reasons.append("insufficient_rhythm_summary_samples")
    if reasons:
        return _unavailable_comparison(
            reasons, closed_count=closed_count, first=first, second=second,
            first_summary=first_summary, second_summary=second_summary,
        )

    assert first_summary is not None and second_summary is not None
    changes: list[dict[str, Any]] = []
    for code in _COMPARISON_SIGNAL_CODES:
        newer, older = first_summary["signals"].get(code, {}), second_summary["signals"].get(code, {})
        newer_value, older_value = newer.get("value"), older.get("value")
        delta = None
        if isinstance(newer_value, (int, float)) and not isinstance(newer_value, bool) and isinstance(older_value, (int, float)) and not isinstance(older_value, bool):
            delta = round(newer_value - older_value, 3)
        changes.append({
            "code": code, "newer_status": newer.get("status"), "older_status": older.get("status"),
            "newer_value": newer_value, "older_value": older_value, "delta": delta,
            "newer_direction": newer.get("direction"), "older_direction": older.get("direction"),
        })
    partial = first_summary["unknown_count"] > 0 or second_summary["unknown_count"] > 0
    return {
        "status": "partial" if partial else "known", "comparable": True,
        "reason_codes": ["unknown_samples_retained"] if partial else [],
        "sample_count": first_summary["sample_count"] + second_summary["sample_count"],
        "known_count": first_summary["known_count"] + second_summary["known_count"],
        "unknown_count": first_summary["unknown_count"] + second_summary["unknown_count"],
        "compared_snapshot_ids": [first.id, second.id], "source_refs": [],
        "limitations": [
            "仅比较两个已关闭且摘要版本、窗口、样本规则与未知值规则一致的冻结聚合摘要。",
            "摘要不含任务名称、标识、正文、路径或原始反馈；比较不会写入任务、计划或校准。",
        ] + (["两个窗口都保留了未知样本；数值只代表各自已知样本。"] if partial else []),
        "calculation_basis": {
            "summary_version": RHYTHM_SUMMARY_VERSION,
            "comparison_order": "newer closed snapshot minus older closed snapshot",
            "changes": changes,
            "source_policy": "aggregate-only; no task source references are returned",
        },
    }


def build_learning_rhythm_history(db: Session) -> dict[str, Any]:
    """Read frozen evidence only; never closes, creates, recalculates or writes."""

    snapshots = list(db.scalars(
        select(WeeklyReviewSnapshot).where(WeeklyReviewSnapshot.snapshot_status == "closed")
        .order_by(WeeklyReviewSnapshot.window_end.desc(), WeeklyReviewSnapshot.id.desc())
        .limit(MAX_HISTORY_WINDOWS)
    ).all())
    windows = [_closed_window(snapshot) for snapshot in snapshots]
    comparison = _comparison(
        snapshots[0] if len(snapshots) > 0 else None,
        snapshots[1] if len(snapshots) > 1 else None, closed_count=len(snapshots),
    )
    return {
        "status": comparison["status"], "timezone": "Asia/Shanghai", "evaluated_at": as_utc(utc_now()),
        "minimum_comparable_window_count": MIN_COMPARABLE_WINDOWS,
        "closed_snapshot_count": len(snapshots), "available_windows": windows, "comparison": comparison,
        "limitations": comparison["limitations"], "source_refs": [],
        "calculation_basis": {
            "history_selection": "only persisted WeeklyReviewSnapshot rows with snapshot_status=closed, newest first",
            "window_policy": "available windows are reported exactly as stored; no missing windows are fabricated",
            "comparison_policy": "only the two newest closed snapshots are compared when their persisted M8.9 rhythm summaries have the same caliber",
            "read_only": True,
        },
    }
