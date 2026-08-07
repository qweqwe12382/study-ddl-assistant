from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExtractionTaskCandidate(BaseModel):
    """A task proposal shown to the user before it becomes a real Task."""

    candidate_id: str | None = None
    course_id: int | None = None
    course_name: str | None = Field(default=None, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    task_type: str | None = Field(default=None, max_length=50)
    description: str | None = None
    due_at: datetime | None = None
    priority: int = Field(default=3, ge=1, le=5)
    source_quote: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    need_review: bool = False
    warnings: list[str] = Field(default_factory=list)
    selected: bool = True


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    course_name: str | None = Field(default=None, max_length=120)
    material_type: str | None = Field(default=None, max_length=50)
    tags: list[str] = Field(default_factory=list)
    tasks: list[ExtractionTaskCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    needs_review: bool = False
    batch_id: str | None = None


class ExtractionRead(ExtractionResult):
    material_id: int
    status: str
    provider: str | None = None
    error: str | None = None
    extracted_at: datetime | None = None
    confirmed_task_ids: list[int] = Field(default_factory=list)


class ExtractionConfirm(BaseModel):
    tasks: list[ExtractionTaskCandidate] | None = None
    course_id: int | None = None
    material_type: str | None = Field(default=None, max_length=50)
    tags: list[str] | None = None
