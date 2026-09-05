"""Persisted, server-authoritative records for the learning agent."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, event, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.services.source_identity import new_navigation_key, prevent_navigation_key_change
from app.time import utc_now


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    trigger: Mapped[str] = mapped_column(String(50), nullable=False, default="manual_refresh")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="completed")
    generated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expired_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ruleset_version: Mapped[str] = mapped_column(String(50), nullable=False, default="m8.1")
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    suggestions: Mapped[list["AgentSuggestion"]] = relationship(back_populates="run")


class AgentSuggestion(Base):
    __tablename__ = "agent_suggestions"
    __table_args__ = (
        Index(
            "uq_agent_suggestions_pending_fingerprint",
            "fingerprint",
            unique=True,
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="task")
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_navigation_key: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    current_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    proposed_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(30), nullable=False, default="low")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.9)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[AgentRun | None] = relationship(back_populates="suggestions")
    receipt: Mapped["ActionReceipt | None"] = relationship(back_populates="suggestion", uselist=False)
    events: Mapped[list["AgentEvent"]] = relationship(back_populates="suggestion")


class ActionReceipt(Base):
    __tablename__ = "action_receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    navigation_key: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True, default=new_navigation_key)
    suggestion_id: Mapped[int] = mapped_column(
        ForeignKey("agent_suggestions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_navigation_key: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False, default="executed")
    applied_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    before_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    after_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    suggestion: Mapped[AgentSuggestion] = relationship(back_populates="receipt")


class AgentEvent(Base):
    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    entity_type: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    entity_navigation_key: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    suggestion_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_suggestions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    suggestion: Mapped[AgentSuggestion | None] = relationship(back_populates="events")


event.listen(ActionReceipt.navigation_key, "set", prevent_navigation_key_change, retval=True, active_history=True)


class AgentReminder(Base):
    """Durable, local-only risk signal shown in the Agent Center.

    Reminders are not suggestions: they can never mutate tasks or plans.  A
    stable fingerprint lets the server retain a user's dismissal across refresh
    calls instead of recreating the same notification every time a briefing is
    read.
    """

    __tablename__ = "agent_reminders"
    __table_args__ = (
        Index(
            "uq_agent_reminders_active_fingerprint",
            "fingerprint",
            unique=True,
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", index=True)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="low", index=True)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    calculation_basis: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class WeeklyReviewSnapshot(Base):
    """One durable, evidence-backed weekly review per China-local window.

    The payload is a projection of :func:`build_weekly_review`, not an
    independently calculated score.  Storing one row per window gives the
    user an auditable history without manufacturing empty historical weeks.
    """

    __tablename__ = "weekly_review_snapshots"
    __table_args__ = (
        UniqueConstraint("window_key", name="uq_weekly_review_snapshots_window_key"),
        Index("ix_weekly_review_snapshots_window_end", "window_end"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # A normalized local-date key avoids SQLite timezone-comparison ambiguity.
    window_key: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # A current window can be refreshed as new local evidence arrives.  Once
    # its end boundary passes, the payload becomes an immutable historical
    # record and is never recomputed by later reads.
    snapshot_status: Mapped[str] = mapped_column(String(20), nullable=False, default="current", index=True)
    ruleset_version: Mapped[str] = mapped_column(String(50), nullable=False, default="m8.6")
    evidence_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    review_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # M8.9 stores only a bounded, aggregate projection of the M8.8 rhythm
    # calculation.  It deliberately has its own version so later metric
    # changes cannot silently be compared with this historical evidence.
    rhythm_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class AgentReminderPreference(Base):
    """A local user's presentation and digest choices for non-critical reminders.

    These values never delete, resolve, or alter reminder evidence.  High-risk
    factual reminders are always eligible for presentation regardless of the
    preference values; an explicit per-reminder dismissal remains separate.
    """

    __tablename__ = "agent_reminder_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    enabled_categories: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    minimum_risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
    digest_frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="immediate")
    # The consumed calendar bucket makes daily/weekly frequency an actual
    # server-side in-app digest policy, rather than a cosmetic client option.
    last_digest_bucket: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
