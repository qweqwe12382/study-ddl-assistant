"""Study streak: consecutive local days with at least one completed task."""

from __future__ import annotations

from datetime import date, timedelta


def compute_study_streak(completed_dates: set[date], today: date) -> int:
    """Count consecutive days ending today, or yesterday if today has no completion yet.

    A streak stays "alive" through the current day until it ends, so a student
    who studied yesterday but has not finished anything yet today still sees
    their running streak instead of a discouraging zero.
    """

    if not completed_dates:
        return 0
    cursor = today if today in completed_dates else today - timedelta(days=1)
    if cursor not in completed_dates:
        return 0
    streak = 0
    while cursor in completed_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
