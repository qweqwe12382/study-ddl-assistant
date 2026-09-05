"""Durable weekly-review history and safe reminder-presentation preferences.

The snapshot store has a deliberately small contract: materialize only the
current, already-calculated local review; never backfill missing weeks.  A
stable China-local window key makes refreshes idempotent even on SQLite, where
timezone-aware datetime comparison is otherwise inconsistent.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.agent import AgentReminder, AgentReminderPreference, WeeklyReviewSnapshot
from app.services.learning_rhythm_history import build_persisted_rhythm_summary
from app.time import as_local, as_utc, utc_now


WEEKLY_REVIEW_RETENTION_LIMIT = 12
WEEKLY_REVIEW_RULESET_VERSION = "m8.6"
MAX_SNAPSHOT_SOURCE_REFS = 120
MAX_SNAPSHOT_STRING_CHARS = 500
MAX_SNAPSHOT_CAPACITY_TASKS = 50
MAX_SNAPSHOT_BYTES = 128 * 1024
REMINDER_CATEGORIES = ("deadlines", "plans", "materials", "estimation", "capacity")
REMINDER_RISKS = ("high", "medium", "low")
REMINDER_DIGEST_FREQUENCIES = ("immediate", "daily", "weekly")
_RISK_RANK = {risk: index for index, risk in enumerate(REMINDER_RISKS)}

_REASON_CATEGORIES = {
    "weekly_overdue_tasks": "deadlines",
    "weekly_plan_delays": "plans",
    "materials_failed": "materials",
    "materials_need_review": "materials",
    "estimate_variance_trend": "estimation",
    "capacity_overload": "capacity",
    "capacity_tight": "capacity",
}


def review_window_key(review: dict[str, Any]) -> str:
    """Identify one actual seven-day China-local calendar window."""

    return f"{as_local(review['window_start']).date().isoformat()}..{as_local(review['window_end']).date().isoformat()}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return as_utc(value).isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _snapshot_payload(review: dict[str, Any]) -> dict[str, Any]:
    """Persist a bounded projection, never raw parsed file text or credentials."""

    stats = {"source_refs_retained": 0, "source_refs_omitted": 0, "strings_truncated": 0, "fields_omitted": 0}
    forbidden_key_parts = ("content", "text", "path", "secret", "token", "password", "api_key", "raw")

    def sanitize(value: Any, *, key: str = "") -> Any:
        lowered = key.lower()
        if any(part in lowered for part in forbidden_key_parts):
            stats["fields_omitted"] += 1
            return None
        if isinstance(value, str):
            if len(value) > MAX_SNAPSHOT_STRING_CHARS:
                stats["strings_truncated"] += 1
                return value[:MAX_SNAPSHOT_STRING_CHARS] + "…"
            return value
        if isinstance(value, dict):
            result = {}
            for child_key, child_value in value.items():
                if str(child_key) == "source_refs":
                    rows = child_value if isinstance(child_value, list) else []
                    remaining = max(0, MAX_SNAPSHOT_SOURCE_REFS - stats["source_refs_retained"])
                    selected = rows[:remaining]
                    stats["source_refs_retained"] += len(selected)
                    stats["source_refs_omitted"] += max(0, len(rows) - len(selected))
                    result[child_key] = [sanitize(row, key="source_ref") for row in selected]
                    continue
                if str(child_key) == "tasks" and key == "capacity_snapshot" and isinstance(child_value, list):
                    result[child_key] = [sanitize(item, key="capacity_task") for item in child_value[:MAX_SNAPSHOT_CAPACITY_TASKS]]
                    if len(child_value) > MAX_SNAPSHOT_CAPACITY_TASKS:
                        stats["fields_omitted"] += len(child_value) - MAX_SNAPSHOT_CAPACITY_TASKS
                    continue
                sanitized = sanitize(child_value, key=str(child_key))
                if sanitized is not None:
                    result[child_key] = sanitized
            return result
        if isinstance(value, list):
            return [sanitize(item, key=key) for item in value]
        return value

    payload = sanitize(_json_safe(review))
    payload.setdefault("calculation_basis", {})["snapshot_storage"] = {
        "source_ref_limit": MAX_SNAPSHOT_SOURCE_REFS,
        **stats,
        "sensitive_field_policy": "parsed text, paths, credentials and raw payload fields are not persisted in history",
    }
    if len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        # This fallback preserves metrics and their calculation basis while
        # dropping only expandable evidence lists; it never invents summaries.
        for metric_name in (
            "completed_tasks", "overdue_tasks", "estimate_variance", "plan_item_status",
            "review_materials", "failed_materials", "execution_receipts",
        ):
            payload.get(metric_name, {}).update({"source_refs": []})
        payload["next_week_actions"] = []
        capacity = payload.get("calculation_basis", {}).get("capacity_snapshot", {})
        if isinstance(capacity, dict):
            capacity["tasks"] = []
        payload["calculation_basis"]["snapshot_storage"]["payload_truncated"] = True
    else:
        payload["calculation_basis"]["snapshot_storage"]["payload_truncated"] = False
    return payload


def _without_evaluation_timestamps(value: Any) -> Any:
    """Remove refresh-clock fields, while retaining every factual metric/ref."""

    if isinstance(value, dict):
        return {
            key: _without_evaluation_timestamps(item)
            for key, item in value.items()
            if key != "evaluated_at"
        }
    if isinstance(value, list):
        return [_without_evaluation_timestamps(item) for item in value]
    return value


def _evidence_digest(review_payload: dict[str, Any]) -> str:
    evidence = _without_evaluation_timestamps(review_payload)
    raw = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def _snapshot_read(snapshot: WeeklyReviewSnapshot) -> dict[str, Any]:
    return {
        "id": snapshot.id,
        "window_key": snapshot.window_key,
        "window_start": as_utc(snapshot.window_start),
        "window_end": as_utc(snapshot.window_end),
        "evaluated_at": as_utc(snapshot.evaluated_at),
        "snapshot_status": snapshot.snapshot_status,
        "ruleset_version": snapshot.ruleset_version,
        "evidence_digest": snapshot.evidence_digest,
        "review": snapshot.review_payload,
        "rhythm_summary_version": snapshot.rhythm_summary.get("summary_version") or None,
        "created_at": as_utc(snapshot.created_at),
        "updated_at": as_utc(snapshot.updated_at),
    }


def materialize_weekly_review(
    db: Session, review: dict[str, Any], *, evaluated_at: datetime | None = None
) -> WeeklyReviewSnapshot:
    """Upsert the current review window and retain only the newest 12 windows.

    The call does not create intermediate rows.  Retrying a refresh in the same
    window updates the existing snapshot's as-of time/payload instead of
    creating a duplicate, and an unchanged evidence digest remains visible for
    audit rather than being replaced with a synthetic version.
    """

    now = as_utc(evaluated_at or review["evaluated_at"])
    _close_elapsed_snapshots(db, now)
    window_key = review_window_key(review)
    snapshot = db.scalar(select(WeeklyReviewSnapshot).where(WeeklyReviewSnapshot.window_key == window_key))
    if snapshot is not None and snapshot.snapshot_status == "closed":
        # Closed history is evidence, not a cache.  This early return is before
        # both review projection and M8.8 evaluation, so a refresh cannot even
        # reconstruct a candidate replacement for frozen rhythm evidence.
        db.commit()
        return snapshot

    payload = _snapshot_payload(review)
    rhythm_summary = build_persisted_rhythm_summary(db, evaluated_at=now)
    digest = _evidence_digest({"review": payload, "rhythm_summary": rhythm_summary})
    if snapshot is None:
        snapshot = WeeklyReviewSnapshot(
            window_key=window_key,
            window_start=as_utc(review["window_start"]),
            window_end=as_utc(review["window_end"]),
            evaluated_at=now,
            snapshot_status="closed" if now >= as_utc(review["window_end"]) else "current",
            ruleset_version=WEEKLY_REVIEW_RULESET_VERSION,
            evidence_digest=digest,
            review_payload=payload,
            rhythm_summary=rhythm_summary,
            created_at=now,
            updated_at=now,
        )
        db.add(snapshot)
    else:
        # Same window is one durable record.  We retain the latest truthful
        # calculation as-of time even if its factual evidence has not changed.
        snapshot.evaluated_at = now
        snapshot.evidence_digest = digest
        snapshot.review_payload = payload
        snapshot.rhythm_summary = rhythm_summary
        snapshot.ruleset_version = WEEKLY_REVIEW_RULESET_VERSION
        snapshot.updated_at = now

    try:
        db.flush()
    except IntegrityError:
        # A concurrent browser refresh may create this unique window first.
        # Resolve it deterministically and overwrite only with this exact
        # current review, never manufacture a second snapshot.
        db.rollback()
        snapshot = db.scalar(select(WeeklyReviewSnapshot).where(WeeklyReviewSnapshot.window_key == window_key))
        if snapshot is None:
            raise
        if snapshot.snapshot_status != "closed":
            snapshot.evaluated_at = now
            snapshot.evidence_digest = digest
            snapshot.review_payload = payload
            snapshot.rhythm_summary = rhythm_summary
            snapshot.ruleset_version = WEEKLY_REVIEW_RULESET_VERSION
            snapshot.updated_at = now
        db.flush()

    snapshot_id = snapshot.id
    retained_ids = list(db.scalars(
        select(WeeklyReviewSnapshot.id)
        .order_by(WeeklyReviewSnapshot.window_end.desc(), WeeklyReviewSnapshot.id.desc())
        .offset(WEEKLY_REVIEW_RETENTION_LIMIT)
    ).all())
    if retained_ids:
        for stale in db.scalars(select(WeeklyReviewSnapshot).where(WeeklyReviewSnapshot.id.in_(retained_ids))).all():
            db.delete(stale)
    db.commit()
    persisted = db.get(WeeklyReviewSnapshot, snapshot_id)
    # Normal API refreshes evaluate "now", so this is always present.  Keeping
    # the detached object as a return value also makes a deliberately
    # back-dated maintenance calculation well-defined when retention correctly
    # prunes it as older than the newest twelve real windows.
    return persisted or snapshot


def _close_elapsed_snapshots(db: Session, now: datetime) -> bool:
    """Freeze all elapsed current windows before any new materialization."""

    elapsed = list(db.scalars(
        select(WeeklyReviewSnapshot).where(
            WeeklyReviewSnapshot.snapshot_status == "current",
            WeeklyReviewSnapshot.window_end <= now,
        )
    ).all())
    for snapshot in elapsed:
        snapshot.snapshot_status = "closed"
        snapshot.updated_at = now
    return bool(elapsed)


def snapshot_read(snapshot: WeeklyReviewSnapshot) -> dict[str, Any]:
    """Serialize a snapshot without exposing mutable ORM JSON internals."""

    return _snapshot_read(snapshot)


def list_weekly_review_history(db: Session, *, limit: int = WEEKLY_REVIEW_RETENTION_LIMIT) -> list[WeeklyReviewSnapshot]:
    # Merely reading the history may happen after a week boundary.  Close the
    # old window first, but do not recalculate any of its factual payload.
    if _close_elapsed_snapshots(db, utc_now()):
        db.commit()
    safe_limit = min(max(limit, 1), WEEKLY_REVIEW_RETENTION_LIMIT)
    return list(db.scalars(
        select(WeeklyReviewSnapshot)
        .order_by(WeeklyReviewSnapshot.window_end.desc(), WeeklyReviewSnapshot.id.desc())
        .limit(safe_limit)
    ).all())


def get_or_create_reminder_preferences(db: Session) -> AgentReminderPreference:
    preference = db.get(AgentReminderPreference, 1)
    if preference is not None:
        return preference
    now = utc_now()
    preference = AgentReminderPreference(
        id=1,
        enabled_categories=list(REMINDER_CATEGORIES),
        minimum_risk_level="low",
        digest_frequency="immediate",
        created_at=now,
        updated_at=now,
    )
    db.add(preference)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        preference = db.get(AgentReminderPreference, 1)
        if preference is None:
            raise
    return preference


def reminder_category(reminder: AgentReminder) -> str:
    """Map rule reasons to the immutable category vocabulary used by settings."""

    return _REASON_CATEGORIES.get(reminder.reason_code, "capacity")


def presentation_allows_reminder(reminder: AgentReminder, preference: AgentReminderPreference) -> bool:
    """Apply display choices without altering evidence or hiding high-risk facts."""

    if reminder.risk_level == "high":
        return True
    category = reminder_category(reminder)
    if category not in set(preference.enabled_categories):
        return False
    minimum_rank = _RISK_RANK.get(preference.minimum_risk_level, _RISK_RANK["low"])
    return _RISK_RANK.get(reminder.risk_level, _RISK_RANK["low"]) <= minimum_rank


def _digest_bucket(frequency: str, now: datetime) -> str | None:
    local_date = as_local(now).date()
    if frequency == "daily":
        return f"daily:{local_date.isoformat()}"
    if frequency == "weekly":
        monday = local_date - timedelta(days=local_date.weekday())
        return f"weekly:{monday.isoformat()}"
    return None


def reminder_presentation(
    db: Session,
    preference: AgentReminderPreference | None = None,
    *,
    evaluated_at: datetime | None = None,
    consume_digest: bool = False,
) -> tuple[list[AgentReminder], dict[str, Any]]:
    """Apply actual in-app digest cadence without changing reminder evidence.

    A user-dismissed item stays dismissed; preferences never reactivate it.
    ``daily``/``weekly`` release eligible non-critical signals once per local
    calendar bucket when an Agent Center briefing/refresh consumes the digest.
    High-risk factual signals are always shown immediately and never consume or
    depend on a digest bucket.  No external delivery channel exists.
    """

    preference = preference or get_or_create_reminder_preferences(db)
    now = as_utc(evaluated_at or utc_now())
    active = list(db.scalars(
        select(AgentReminder)
        .where(AgentReminder.status == "active")
        .order_by(AgentReminder.updated_at.desc(), AgentReminder.id.desc())
    ).all())
    high_risk = [item for item in active if item.risk_level == "high"]
    noncritical = [
        item for item in active
        if item.risk_level != "high" and presentation_allows_reminder(item, preference)
    ]
    bucket = _digest_bucket(preference.digest_frequency, now)
    last_bucket_before = preference.last_digest_bucket
    eligible = preference.digest_frequency == "immediate" or (
        bool(noncritical) and last_bucket_before != bucket
    )
    presented = high_risk + (noncritical if eligible else [])
    consumed = False
    if consume_digest and bucket is not None and eligible and noncritical:
        preference.last_digest_bucket = bucket
        preference.updated_at = now
        db.commit()
        consumed = True
    return presented, {
        "presentation_scope": "in-app Agent Center only; no external push or notification is sent",
        "digest_frequency": preference.digest_frequency,
        "digest_bucket": bucket,
        "last_digest_bucket_before": last_bucket_before,
        "noncritical_candidate_count": len(noncritical),
        "noncritical_digest_eligible": eligible,
        "digest_consumed": consumed,
        "high_risk_policy": "always_presented",
        "high_risk_presented_count": len(high_risk),
    }


def presented_active_reminders(
    db: Session, preference: AgentReminderPreference | None = None, *, evaluated_at: datetime | None = None
) -> list[AgentReminder]:
    """Read-only presentation preview used by the existing list endpoint."""

    reminders, _basis = reminder_presentation(db, preference, evaluated_at=evaluated_at, consume_digest=False)
    return reminders


def reminder_preference_read(preference: AgentReminderPreference) -> dict[str, Any]:
    return {
        "enabled_categories": list(preference.enabled_categories),
        "minimum_risk_level": preference.minimum_risk_level,
        "digest_frequency": preference.digest_frequency,
        "high_risk_policy": "always_presented",
        "created_at": as_utc(preference.created_at),
        "updated_at": as_utc(preference.updated_at),
    }
