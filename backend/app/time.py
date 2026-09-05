"""Shared timezone semantics for API input, SQLite storage, and display."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")


def utc_now() -> datetime:
    """Return the current time as timezone-aware UTC."""

    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """Read a persisted timestamp as UTC (SQLite may have dropped tzinfo)."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def as_local(value: datetime) -> datetime:
    """Convert persisted UTC data to the product's Asia/Shanghai wall time."""

    return as_utc(value).astimezone(LOCAL_TIMEZONE)


def deadline_to_utc(value: datetime) -> datetime:
    """Normalize external deadline input for persistence.

    Naive API/provider dates denote Asia/Shanghai local wall time. Aware input
    (including ISO timestamps ending in ``Z``) keeps its instant unchanged.
    """

    if value.tzinfo is None:
        return value.replace(tzinfo=LOCAL_TIMEZONE).astimezone(timezone.utc)
    return value.astimezone(timezone.utc)
