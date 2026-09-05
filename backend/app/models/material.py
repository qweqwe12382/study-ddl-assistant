from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, JSON, DateTime, ForeignKey, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.services.source_identity import new_navigation_key, prevent_navigation_key_change
from app.time import utc_now


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    navigation_key: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True, default=new_navigation_key)
    revision: Mapped[int] = mapped_column(nullable=False, default=1)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True, unique=True)
    material_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(30), default="not_started", nullable=False)
    extraction_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extraction_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    course = relationship("Course", back_populates="materials")
    tasks = relationship("Task", back_populates="material")

    __mapper_args__ = {"version_id_col": revision}


event.listen(Material.navigation_key, "set", prevent_navigation_key_change, retval=True, active_history=True)
