from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.services.source_identity import new_navigation_key, prevent_navigation_key_change
from app.time import utc_now


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    navigation_key: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True, default=new_navigation_key)
    revision: Mapped[int] = mapped_column(nullable=False, default=1)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True)
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id", ondelete="SET NULL"), nullable=True, index=True)
    source_material_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    task_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remaining_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Feedback is deliberately stored on the completed task rather than inferred
    # from wall-clock timestamps: a student may pause, switch devices, or finish
    # later.  Only explicit bounded input becomes a calibration sample.
    actual_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    difficulty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
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

    __mapper_args__ = {"version_id_col": revision}

    @property
    def material_navigation_key(self) -> str | None:
        return self.material.navigation_key if self.material is not None else None


event.listen(Task.navigation_key, "set", prevent_navigation_key_change, retval=True, active_history=True)
