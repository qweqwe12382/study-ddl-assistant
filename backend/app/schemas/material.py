from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ProcessingStatus = Literal["pending", "processing", "processed", "failed"]


class MaterialManualCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    course_id: int | None = None
    original_filename: str = Field(min_length=1, max_length=255)
    file_type: str | None = Field(default=None, max_length=30)
    material_type: str | None = Field(default=None, max_length=50)
    extracted_text: str | None = None
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    source_time: datetime | None = None
class MaterialUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    course_id: int | None = None
    original_filename: str | None = Field(default=None, min_length=1, max_length=255)
    file_type: str | None = Field(default=None, max_length=30)
    extracted_text: str | None = None
    material_type: str | None = Field(default=None, max_length=50)
    summary: str | None = None
    tags: list[str] | None = None


class MaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int | None
    original_filename: str
    stored_path: str | None
    file_type: str | None
    file_size: int | None
    content_hash: str | None
    material_type: str | None
    extracted_text: str | None
    summary: str | None
    tags: list[str]
    source_time: datetime | None
    processing_status: ProcessingStatus
    processing_error: str | None
    extraction_status: str
    extraction_result: dict | None
    extraction_provider: str | None
    extraction_error: str | None
    extracted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MaterialSearchRead(MaterialRead):
    """Material row with optional evidence for a keyword match."""

    matched_fields: list[str] = Field(default_factory=list)
    match_snippets: list[str] = Field(default_factory=list)
