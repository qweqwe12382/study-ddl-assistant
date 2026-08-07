"""Time helpers used by database models and API services."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current time as timezone-aware UTC."""

    return datetime.now(timezone.utc)
