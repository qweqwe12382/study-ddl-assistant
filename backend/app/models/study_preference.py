"""Single-user learning-capacity preferences."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.time import utc_now


class StudyPreference(Base):
    __tablename__ = "study_preferences"

    # The local product is intentionally single-user. API helpers always use
    # row 1 and create it lazily rather than accepting a user-controlled id.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    weekly_available_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1200)
    daily_limit_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=240)
    buffer_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.15)
    preferred_time_slots: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=lambda: ["evening"])
    course_weights: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
