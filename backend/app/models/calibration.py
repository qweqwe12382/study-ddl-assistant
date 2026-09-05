"""Persisted reset boundary for per-course estimate calibration."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.time import utc_now


class CourseCalibrationState(Base):
    __tablename__ = "course_calibration_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    # Samples at or before this instant are intentionally ignored.  Reset never
    # erases task feedback/audit history, which keeps the operation reversible.
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reset_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
