from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.time import utc_now


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    teacher: Mapped[str | None] = mapped_column(String(120), nullable=True)
    semester: Mapped[str | None] = mapped_column(String(40), nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    materials = relationship("Material", back_populates="course", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="course", cascade="all, delete-orphan")
    study_plans = relationship("StudyPlan", back_populates="course", cascade="all, delete-orphan")
    class_sessions = relationship("ClassSession", back_populates="course", cascade="all, delete-orphan")
    exams = relationship("Exam", back_populates="course", cascade="all, delete-orphan")
