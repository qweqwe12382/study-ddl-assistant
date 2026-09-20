from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.time import deadline_to_utc

from app.schemas.timestamps import UtcDateTime


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
    estimated_minutes: int | None = Field(default=None, ge=15, le=10080)
    remaining_minutes: int | None = Field(default=None, ge=0, le=10080)
    source_quote: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    need_review: bool = False
    warnings: list[str] = Field(default_factory=list)
    selected: bool = True

    @field_validator("due_at")
    @classmethod
    def normalize_due_at(cls, value: datetime | None) -> datetime | None:
        return deadline_to_utc(value) if value is not None else None

    @model_validator(mode="after")
    def validate_remaining_minutes(self):
        if self.remaining_minutes is not None and self.estimated_minutes is None:
            raise ValueError("remaining_minutes requires estimated_minutes")
        if (
            self.estimated_minutes is not None
            and self.remaining_minutes is not None
            and self.remaining_minutes > self.estimated_minutes
        ):
            raise ValueError("remaining_minutes cannot exceed estimated_minutes")
        return self


ExtractionProviderName = Literal["local-rules", "openai-compatible"]
ExtractionEvidenceSource = Literal["filename", "text", "both", "rule_inference", "unconfirmed"]


class ExtractionRequest(BaseModel):
    provider: ExtractionProviderName = "local-rules"


class ExtractionProviderOption(BaseModel):
    id: ExtractionProviderName
    label: str
    description: str
    available: bool
    sends_data_externally: bool
    model: str | None = None


class ExtractionPolicyRead(BaseModel):
    default_provider: ExtractionProviderName = "local-rules"
    providers: list[ExtractionProviderOption]


class ExtractionFieldEvidence(BaseModel):
    """Server-derived provenance for one structured extraction value.

    The provider never supplies this object.  ``snippets`` are deliberately
    short material excerpts, rather than provider explanations or paths.
    """

    model_config = ConfigDict(extra="ignore")

    value: str = Field(min_length=1, max_length=120)
    source: ExtractionEvidenceSource
    snippets: list[str] = Field(default_factory=list, max_length=2)

    @field_validator("snippets")
    @classmethod
    def validate_snippets(cls, value: list[str]) -> list[str]:
        if any(not item or len(item) > 180 for item in value):
            raise ValueError("evidence snippets must be non-empty and at most 180 characters")
        return value


class ExtractionFieldEvidenceSet(BaseModel):
    """Evidence for the top-level fields that users can review or confirm."""

    model_config = ConfigDict(extra="ignore")

    course_name: ExtractionFieldEvidence | None = None
    material_type: ExtractionFieldEvidence | None = None
    tags: list[ExtractionFieldEvidence] = Field(default_factory=list, max_length=30)


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    course_name: str | None = Field(default=None, max_length=120)
    material_type: str | None = Field(default=None, max_length=50)
    tags: list[str] = Field(default_factory=list)
    tasks: list[ExtractionTaskCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    needs_review: bool = False
    batch_id: str | None = None
    content_kind: Literal["study_material", "review_outline", "task_notice", "mixed"] = "study_material"
    learning_points: list[str] = Field(default_factory=list, max_length=6)
    field_evidence: ExtractionFieldEvidenceSet = Field(default_factory=ExtractionFieldEvidenceSet)


class ConfirmedExtractionTaskRef(BaseModel):
    """Identity captured when the student confirms creation, never reconstructed."""

    id: int = Field(gt=0)
    navigation_key: str = Field(pattern=r"^[0-9a-f]{32}$")
    name: str = Field(min_length=1, max_length=200)


class ExtractionRead(ExtractionResult):
    material_id: int
    material_navigation_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    material_revision: int = Field(default=1, ge=1)
    status: str
    provider: str | None = None
    error: str | None = None
    extracted_at: UtcDateTime | None = None
    confirmed_task_ids: list[int] = Field(default_factory=list)
    confirmed_task_refs: list[ConfirmedExtractionTaskRef] = Field(default_factory=list)


class ExtractionConfirm(BaseModel):
    material_only: bool = False
    tasks: list[ExtractionTaskCandidate] | None = None
    course_id: int | None = None
    material_type: str | None = Field(default=None, max_length=50)
    tags: list[str] | None = None
