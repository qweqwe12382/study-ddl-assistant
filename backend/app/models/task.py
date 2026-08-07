from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.time import utc_now


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True)
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id", ondelete="SET NULL"), nullable=True, index=True)
    source_material_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    task_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="not_started", nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    need_review: Mapped[bool] = mapped_column(default=False, nullable=False)
    source_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extraction_candidate_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    course = relationship("Course", back_populates="tasks")
    material = relationship("Material", back_populates="tasks")
