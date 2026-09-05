"""Read-only learning-rhythm evidence built from explicit completion feedback.

This module intentionally does not estimate future work or change a study plan.
It only summarizes the timing and load of completed tasks where the student
actually supplied both duration and difficulty, and shows existing per-course
calibration as context rather than applying it a second time.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task import Task
from app.services.agent_feedback import calibration_payload
from app.time import LOCAL_TIMEZONE, as_local, as_utc, utc_now


TREND_WINDOW_DAYS = 28
MIN_TREND_SAMPLES = 4
MIN_PACE_HALF_SAMPLES = 2
MAX_SOURCE_REFS = 50
MAX_ADJUSTMENT_CANDIDATES = 3
MAX_CALIBRATION_CONTEXTS = 50


def _trend_window(evaluated_at: datetime) -> tuple[datetime, datetime]:
    """Return the last 28 China-local calendar dates, including today."""

    local_now = as_local(evaluated_at)
    end = datetime.combine(local_now.date() + timedelta(days=1), time.min, tzinfo=LOCAL_TIMEZONE)
    start = end - timedelta(days=TREND_WINDOW_DAYS)
    return start.astimezone(evaluated_at.tzinfo), end.astimezone(evaluated_at.tzinfo)


def _completed_at_utc(value: object) -> datetime | None:
    """Treat malformed legacy completion timestamps as unknown evidence."""

    if not isinstance(value, datetime):
        return None
    try:
        return as_utc(value)
    except (ArithmeticError, OverflowError, ValueError):
        return None


def _has_valid_feedback(task: Task) -> bool:
    """Accept only the same explicit feedback range enforced by task writes."""

    return all((
        isinstance(task.actual_minutes, int) and not isinstance(task.actual_minutes, bool)
        and 15 <= task.actual_minutes <= 10080,
        isinstance(task.difficulty, int) and not isinstance(task.difficulty, bool)
        and 1 <= task.difficulty <= 5,
    ))


def _ref(task: Task, *, reason: str | None = None) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "course_id": task.course_id,
        "completed_at": (_completed_at_utc(task.completed_at).isoformat()
                         if _completed_at_utc(task.completed_at) else None),
        "actual_minutes": task.actual_minutes,
        "difficulty": task.difficulty,
    }
    if reason is not None:
        snapshot["reason"] = reason
    return {"source_type": "task", "source_id": task.id, "navigation_key": task.navigation_key, "source_name": task.name, "snapshot": snapshot}


def _status(*, known_count: int, unknown_count: int, minimum: int) -> str:
    if known_count == 0:
        return "unknown"
    if known_count < minimum or unknown_count:
        return "partial"
    return "known"


def _signal(
    *, code: str, status: str, window_start: datetime, window_end: datetime,
    sample_count: int, known_count: int, unknown_count: int, value: int | float | str | None,
    direction: str | None, explanation: str, limitations: list[str], refs: list[dict[str, Any]],
    calculation_basis: dict[str, Any],
) -> dict[str, Any]:
    return {
        "code": code, "status": status, "window_start": window_start, "window_end": window_end,
        "timezone": "Asia/Shanghai", "minimum_sample_count": MIN_TREND_SAMPLES,
        "sample_count": sample_count, "known_count": known_count, "unknown_count": unknown_count,
        "value": value, "direction": direction, "explanation": explanation,
        "limitations": limitations, "source_refs": refs[:MAX_SOURCE_REFS],
        "calculation_basis": calculation_basis,
    }


def _calibration_context(
    db: Session, samples: list[Task], *, window_start: datetime, window_end: datetime
) -> tuple[list[dict[str, Any]], int]:
    """Expose existing calibration facts without altering raw trend samples."""

    by_course: dict[int, list[Task]] = {}
    for task in samples:
        if task.course_id is not None:
            by_course.setdefault(task.course_id, []).append(task)
    contexts: list[dict[str, Any]] = []
    course_rows = sorted(by_course.items())
    for course_id, rows in course_rows[:MAX_CALIBRATION_CONTEXTS]:
        try:
            calibration = calibration_payload(db, course_id)
        except (ArithmeticError, OverflowError, TypeError, ValueError):
            # Existing calibration is optional display context.  A malformed
            # legacy calibration sample must not block the primary read-only
            # rhythm evidence or trigger a repair write from this GET.
            contexts.append({
                "course_id": course_id, "status": "partial", "window_start": window_start,
                "window_end": window_end, "timezone": "Asia/Shanghai",
                "minimum_sample_count": MIN_TREND_SAMPLES, "sample_count": 0,
                "known_count": 0, "unknown_count": len(rows), "factor": None,
                "limitations": ["该课程的既有校准数据无法安全读取；趋势保留原始完成反馈，未尝试修复或写回。"],
                "source_refs": [_ref(task) for task in rows][:MAX_SOURCE_REFS],
            })
            continue
        factor = calibration["factor"]
        # Calibration has a stricter source condition (estimated + actual),
        # so its sample count is retained separately from rhythm evidence.
        contexts.append({
            "course_id": course_id,
            "status": "known" if factor is not None else "partial",
            "window_start": window_start,
            "window_end": window_end,
            "timezone": "Asia/Shanghai",
            "minimum_sample_count": calibration["minimum_sample_count"],
            "sample_count": calibration["sample_count"],
            "known_count": calibration["sample_count"] if factor is not None else 0,
            "unknown_count": 0 if factor is not None else len(rows),
            "factor": factor,
            "limitations": [] if factor is not None else [
                "该课程尚无足够的实际/预计时长配对样本；趋势仍保留原始实际用时，不推导校准系数。"
            ],
            "source_refs": [_ref(task) for task in rows][:MAX_SOURCE_REFS],
        })
    return contexts, max(0, len(course_rows) - MAX_CALIBRATION_CONTEXTS)


def build_learning_trends(db: Session, *, evaluated_at: datetime | None = None) -> dict[str, Any]:
    """Build one deterministic, non-persisted local rhythm snapshot."""

    now = as_utc(evaluated_at or utc_now())
    window_start, window_end = _trend_window(now)
    completed_rows = list(db.scalars(select(Task).where(Task.status == "completed").order_by(Task.completed_at.asc(), Task.id.asc())).all())
    completed_times = {task.id: _completed_at_utc(task.completed_at) for task in completed_rows}
    in_window = [
        task for task in completed_rows
        if completed_times[task.id] is not None and window_start <= completed_times[task.id] < window_end
    ]
    missing_time = [task for task in completed_rows if completed_times[task.id] is None]
    samples = [task for task in in_window if _has_valid_feedback(task)]
    incomplete = [task for task in in_window if task not in samples]
    sample_count, known_count, unknown_count = len(in_window), len(samples), len(incomplete)
    base_status = _status(known_count=known_count, unknown_count=unknown_count, minimum=MIN_TREND_SAMPLES)
    refs = [_ref(task) for task in samples] + [
        _ref(task, reason="actual_minutes_or_difficulty_missing_or_invalid") for task in incomplete
    ]
    common_limits: list[str] = []
    if known_count < MIN_TREND_SAMPLES:
        common_limits.append(f"至少需要 {MIN_TREND_SAMPLES} 个同时填写实际用时和难度的完成任务；当前为 {known_count} 个。")
    if incomplete:
        common_limits.append(f"窗口内有 {len(incomplete)} 个完成任务缺少或填写了无效的实际用时/难度，未按默认值补齐。")
    if missing_time:
        common_limits.append(f"另有 {len(missing_time)} 个已完成任务缺少完成时间或含无效值，无法归入本观察窗口。")

    local_days = sorted({as_local(completed_times[task.id]).date() for task in samples})
    observation_days = TREND_WINDOW_DAYS
    distribution_value = round(len(local_days) / observation_days, 3) if known_count >= MIN_TREND_SAMPLES else None
    distribution_status = base_status if len(local_days) >= 2 else ("unknown" if not local_days else "partial")
    distribution_limits = [*common_limits]
    if len(local_days) < 2:
        distribution_limits.append("学习日分布至少需要两个不同的完成日期。")
    distribution = _signal(
        code="learning_day_distribution", status=distribution_status, window_start=window_start, window_end=window_end,
        sample_count=sample_count, known_count=known_count, unknown_count=unknown_count, value=distribution_value,
        direction=None,
        explanation=(f"{observation_days} 个本地日中有 {len(local_days)} 个学习日。" if distribution_value is not None else "完成反馈不足，无法判断学习日分布。"),
        limitations=distribution_limits, refs=refs,
        calculation_basis={"formula": "distinct local completion dates / 28 China-local calendar dates", "active_learning_days": len(local_days)},
    )

    idle_value: int | None = None
    idle_status = distribution_status
    idle_limits = [*distribution_limits]
    if distribution_value is not None:
        start_date = as_local(window_start).date()
        active = set(local_days)
        run = longest = 0
        for offset in range(observation_days):
            if start_date + timedelta(days=offset) in active:
                longest = max(longest, run)
                run = 0
            else:
                run += 1
        idle_value = max(longest, run)
    idle = _signal(
        code="longest_idle_gap", status=idle_status, window_start=window_start, window_end=window_end,
        sample_count=sample_count, known_count=known_count, unknown_count=unknown_count, value=idle_value,
        direction=None,
        explanation=(f"观察窗口内最长连续无完成反馈间隔为 {idle_value} 天。" if idle_value is not None else "完成反馈不足，无法判断连续空档。"),
        limitations=idle_limits, refs=refs,
        calculation_basis={"formula": "maximum consecutive China-local dates without eligible completed-task feedback", "active_learning_days": len(local_days)},
    )

    daily_effort_units: dict[str, int] = {}
    for task in samples:
        key = as_local(completed_times[task.id]).date().isoformat()
        # Difficulty is an explicit 1–5 completion feedback value, not an
        # inferred productivity score.  It only weights this descriptive
        # concentration signal; the raw actual minutes remain in source refs.
        daily_effort_units[key] = daily_effort_units.get(key, 0) + task.actual_minutes * task.difficulty
    concentration_value = None
    concentration_status = distribution_status
    concentration_limits = [*distribution_limits]
    if distribution_value is not None:
        total_effort = sum(daily_effort_units.values())
        concentration_value = round(max(daily_effort_units.values()) / total_effort, 3) if total_effort else None
    concentration = _signal(
        code="load_concentration", status=concentration_status, window_start=window_start, window_end=window_end,
        sample_count=sample_count, known_count=known_count, unknown_count=unknown_count, value=concentration_value,
        direction=None,
        explanation=(f"难度加权学习负荷最多的一天占已知总负荷的 {concentration_value:.1%}。" if concentration_value is not None else "完成反馈不足，无法判断负荷集中度。"),
        limitations=concentration_limits, refs=refs,
        calculation_basis={"formula": "max(local-date sum(actual_minutes * explicit difficulty)) / sum(actual_minutes * explicit difficulty)", "unit": "difficulty-weighted minutes", "daily_effort_units": daily_effort_units},
    )

    midpoint = window_start + (window_end - window_start) / 2
    first_half = [task for task in samples if completed_times[task.id] < midpoint]
    second_half = [task for task in samples if completed_times[task.id] >= midpoint]
    pace_status = base_status
    pace_direction: str | None = None
    pace_value: str | None = None
    pace_limits = [*common_limits]
    if len(first_half) < MIN_PACE_HALF_SAMPLES or len(second_half) < MIN_PACE_HALF_SAMPLES:
        pace_status = "partial" if known_count else "unknown"
        pace_limits.append(f"完成节奏方向需要观察窗口前后各至少 {MIN_PACE_HALF_SAMPLES} 个有效样本。")
    elif base_status != "unknown":
        first_rate = len(first_half) / (TREND_WINDOW_DAYS / 2)
        second_rate = len(second_half) / (TREND_WINDOW_DAYS / 2)
        if second_rate > first_rate * 1.2:
            pace_direction, pace_value = "accelerating", "accelerating"
        elif second_rate < first_rate * 0.8:
            pace_direction, pace_value = "slowing", "slowing"
        else:
            pace_direction, pace_value = "stable", "stable"
    pace = _signal(
        code="completion_pace", status=pace_status, window_start=window_start, window_end=window_end,
        sample_count=sample_count, known_count=known_count, unknown_count=unknown_count, value=pace_value,
        direction=pace_direction,
        explanation=(f"后 14 天与前 14 天的有效完成任务日均数量相比，节奏为 {pace_value}。" if pace_value else "完成反馈不足，无法判断完成节奏方向。"),
        limitations=pace_limits, refs=refs,
        calculation_basis={"formula": "compare eligible completed-task counts per day in first and second 14 China-local days; 20% threshold", "first_half_sample_count": len(first_half), "second_half_sample_count": len(second_half)},
    )
    signals = [distribution, idle, concentration, pace]

    calibration_context, omitted_calibration_contexts = _calibration_context(
        db, samples, window_start=window_start, window_end=window_end
    )
    calibration_missing = sum(1 for item in calibration_context if item["status"] != "known")
    status = base_status
    if status == "known" and (calibration_missing or omitted_calibration_contexts):
        status = "partial"

    candidates: list[dict[str, Any]] = []
    for signal in (idle, concentration, pace):
        should_review = (
            signal["status"] != "unknown" and (
                (signal["code"] == "longest_idle_gap" and isinstance(signal["value"], int) and signal["value"] >= 7)
                or (signal["code"] == "load_concentration" and isinstance(signal["value"], float) and signal["value"] >= 0.7)
                or (signal["code"] == "completion_pace" and signal["direction"] == "slowing")
            )
        )
        if should_review:
            candidates.append({
                "action_type": "review_learning_rhythm", "target_type": "learning_trend", "target_id": signal["code"],
                "status": signal["status"], "window_start": window_start, "window_end": window_end,
                "timezone": "Asia/Shanghai", "title": "复核学习节奏", "execution_mode": "review", "allowed_input": {},
                "explanation": "这是基于已完成任务反馈的只读提示；请人工查看现有任务和计划，不会自动写入或调整安排。",
                "source_refs": signal["source_refs"],
            })
    limitations = [
        "仅使用当前本地单用户数据中的真实完成任务；不读取资料正文、描述、位置或外部账户数据。",
        "趋势不预测未来用时，不新增任务，不自动写入任务、计划或课程校准。",
        *common_limits,
    ]
    if calibration_missing:
        limitations.append(f"{calibration_missing} 个涉及课程尚无足够现有校准样本；其原始完成反馈未被校准值替换。")
    if omitted_calibration_contexts:
        limitations.append(
            f"涉及课程超过 {MAX_CALIBRATION_CONTEXTS} 个；仅按课程标识排序展示前 {MAX_CALIBRATION_CONTEXTS} 个既有校准上下文，未写入或省略趋势原始样本。"
        )
    return {
        "status": status, "window_start": window_start, "window_end": window_end, "evaluated_at": now,
        "timezone": "Asia/Shanghai", "minimum_sample_count": MIN_TREND_SAMPLES,
        "sample_count": sample_count, "known_count": known_count, "unknown_count": unknown_count,
        "signals": signals, "calibration_context": calibration_context,
        "adjustment_candidates": candidates[:MAX_ADJUSTMENT_CANDIDATES],
        "limitations": limitations[:15], "source_refs": refs[:MAX_SOURCE_REFS],
        "calculation_basis": {
            "window_semantics": "last 28 China-local calendar dates, [window_start, window_end)",
            "timezone": "Asia/Shanghai", "sample_rule": "status=completed, completed_at in window, actual_minutes and difficulty explicitly supplied",
            "unknown_policy": "missing actual_minutes, difficulty, or completed_at stays unknown/excluded; no default duration or difficulty is inferred",
            "calibration_semantics": "existing per-course calibration is read as context only and never applied to alter raw trend evidence",
            "scope": "current local single-user database only",
        },
    }
