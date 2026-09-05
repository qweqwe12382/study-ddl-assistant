from __future__ import annotations

from datetime import datetime, time

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, Time, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.services.source_identity import new_navigation_key, prevent_navigation_key_change
from app.time import utc_now


class ClassSession(Base):
    __tablename__ = "class_sessions"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 1 AND 7", name="ck_class_sessions_weekday"),
        CheckConstraint("start_week BETWEEN 1 AND 30", name="ck_class_sessions_start_week"),
        CheckConstraint("end_week BETWEEN start_week AND 30", name="ck_class_sessions_end_week"),
        CheckConstraint("start_time < end_time", name="ck_class_sessions_time_order"),
        CheckConstraint("week_pattern IN ('all', 'odd', 'even')", name="ck_class_sessions_week_pattern"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    navigation_key: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True, default=new_navigation_key
    )
    revision: Mapped[int] = mapped_column(nullable=False, default=1)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    start_week: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    end_week: Mapped[int] = mapped_column(Integer, nullable=False, default=18)
    week_pattern: Mapped[str] = mapped_column(String(10), nullable=False, default="all")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    course = relationship("Course", back_populates="class_sessions")
    __mapper_args__ = {"version_id_col": revision}

    @property
    def course_name(self) -> str:
        return self.course.name

    @property
    def course_color(self) -> str | None:
        return self.course.color

    @property
    def teacher(self) -> str | None:
        return self.course.teacher


class Exam(Base):
    __tablename__ = "exams"
    __table_args__ = (
        CheckConstraint("exam_type IN ('quiz', 'midterm', 'final', 'other')", name="ck_exams_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    navigation_key: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True, default=new_navigation_key
    )
    revision: Mapped[int] = mapped_column(nullable=False, default=1)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    exam_type: Mapped[str] = mapped_column(String(20), nullable=False, default="final")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    seat_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    course = relationship("Course", back_populates="exams")
    __mapper_args__ = {"version_id_col": revision}

    @property
    def course_name(self) -> str:
        return self.course.name

    @property
    def course_color(self) -> str | None:
        return self.course.color


class AcademicCalendarSyncLink(Base):
    """Bind one external calendar item to the local row last written from it.

    Credentials and raw calendar payloads are deliberately not stored.  The
    applied hash lets a later import avoid overwriting a row that the student
    edited locally after the previous sync.
    """

    __tablename__ = "academic_calendar_sync_links"
    __table_args__ = (
        CheckConstraint("source_type IN ('ical')", name="ck_academic_sync_source_type"),
        CheckConstraint(
            "entity_type IN ('class_session', 'exam')", name="ck_academic_sync_entity_type"
        ),
        UniqueConstraint(
            "source_key", "external_uid", "entity_type", name="uq_academic_sync_external_item"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="ical")
    external_uid: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_navigation_key: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    applied_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


event.listen(ClassSession.navigation_key, "set", prevent_navigation_key_change, retval=True, active_history=True)
event.listen(Exam.navigation_key, "set", prevent_navigation_key_change, retval=True, active_history=True)
