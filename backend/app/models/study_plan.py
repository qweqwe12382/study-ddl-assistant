from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.services.source_identity import new_navigation_key, prevent_navigation_key_change
from app.time import utc_now


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    navigation_key: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True, default=new_navigation_key)
    revision: Mapped[int] = mapped_column(nullable=False, default=1)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    daily_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plan_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    course = relationship("Course", back_populates="study_plans")

    __mapper_args__ = {"version_id_col": revision}


event.listen(StudyPlan.navigation_key, "set", prevent_navigation_key_change, retval=True, active_history=True)
