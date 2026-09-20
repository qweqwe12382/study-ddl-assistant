"""Bounded HTTP contracts for the learning-agent suggestion loop."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.task import TaskRead
from app.schemas.timestamps import UtcDateTime


SuggestionStatus = Literal["pending", "accepted", "executed", "failed", "dismissed", "expired"]


class AgentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: int = Field(ge=1, le=5)


class ActionReceiptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    navigation_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    action_type: str
    source_type: str
    source_id: int
    source_navigation_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    outcome: str
    applied_payload: dict[str, Any]
    before_payload: dict[str, Any]
    after_payload: dict[str, Any]
    message: str
    executed_at: UtcDateTime


class AgentSuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action_type: str
    status: SuggestionStatus
    source_type: str
    source_id: int
    source_navigation_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    source_name: str
    title: str
    explanation: str
    reason_code: str
    current_payload: dict[str, Any]
    proposed_payload: dict[str, Any]
    risk_level: str
    confidence: float
    expires_at: UtcDateTime
    fingerprint: str
    run_id: int | None
    created_at: UtcDateTime
    updated_at: UtcDateTime
    accepted_at: UtcDateTime | None
    executed_at: UtcDateTime | None
    dismissed_at: UtcDateTime | None
    dismissal_reason: str | None
    receipt: ActionReceiptRead | None = None


class AgentBriefingRead(BaseModel):
    generated_at: UtcDateTime
    pending_count: int
    suggestions: list[AgentSuggestionRead]
    inbox: "AgentInboxRead"
    decision_queue: list["AgentDecisionQueueItemRead"] = Field(default_factory=list, max_length=5)
    capacity: "CapacityRead"
    today_actions: list["TodayActionRead"] = Field(max_length=3)
    capacity_action_candidates: list["CapacityActionCandidateRead"]
    recent_results: list[AgentSuggestionRead] = Field(max_length=5)
    plan_deltas: list[AgentSuggestionRead] = Field(default_factory=list, max_length=3)
    weekly_review: "WeeklyReviewRead"
    reminders: list["AgentReminderRead"] = Field(default_factory=list, max_length=20)
    reminder_preferences: "AgentReminderPreferenceRead"
    reminder_presentation: "ReminderPresentationRead"


class AgentInboxBucketRead(BaseModel):
    count: int = Field(ge=0)
    material_ids: list[int]


class AgentInboxRead(BaseModel):
    ready: AgentInboxBucketRead
    needs_review: AgentInboxBucketRead
    failed: AgentInboxBucketRead


DecisionPriority = Literal["critical", "high", "medium", "normal"]
DecisionKind = Literal[
    "material_failed",
    "material_needs_review",
    "material_ready",
    "plan_delta_review",
    "suggestion_priority_review",
    "capacity_estimate_review",
    "capacity_start_review",
    "capacity_overload_review",
    "capacity_same_day_review",
]
DecisionReasonCode = Literal[
    "material_processing_failed",
    "material_extraction_failed",
    "material_needs_review",
    "material_ready",
    "pending_plan_delta",
    "pending_priority_suggestion",
    "capacity_missing_estimate",
    "capacity_start_task",
    "capacity_daily_overload",
    "capacity_same_day_deadlines",
]


class AgentDecisionSourceRefRead(BaseModel):
    """Only the resolver identity needed to open a decision's evidence."""

    source_type: Literal["task", "material", "study_plan", "capacity"]
    source_id: int | Literal["next_7_days"]
    navigation_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


class AgentDecisionCalculationBasisRead(BaseModel):
    """Fixed explanation metadata; no stored suggestion payload is exposed."""

    evaluated_at: UtcDateTime
    ordering_rule: Literal["risk_then_kind_then_source"]
    source_state: Literal["failed", "needs_review", "ready", "pending", "current_capacity"]


class AgentDecisionQueueItemRead(BaseModel):
    """A bounded navigation/review item, never an executable instruction."""

    decision_id: str = Field(min_length=1, max_length=120)
    kind: DecisionKind
    priority: DecisionPriority
    title: str = Field(max_length=80)
    description: str = Field(max_length=240)
    action_label: str = Field(max_length=80)
    reason_code: DecisionReasonCode
    source_refs: list[AgentDecisionSourceRefRead] = Field(min_length=1, max_length=1)
    calculation_basis: AgentDecisionCalculationBasisRead


class TodayActionRead(BaseModel):
    task_id: int
    task_navigation_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    task_name: str
    course_id: int | None
    course_name: str | None
    due_at: UtcDateTime | None
    estimated_minutes: int | None
    remaining_minutes: int | None
    counted_minutes: int | None
    minute_source: Literal["remaining_minutes", "estimated_minutes"] | None
    risk_level: Literal["high", "medium", "unknown", "low"]
    preferred_time_slot: Literal["morning", "afternoon", "evening"]
    reason_codes: list[str]
    display_reasons: list[str]
    score: float
    score_components: dict[str, float]
    score_basis: dict[str, object]
    controlled_action: Literal["start_task"] | None = None
    suggestion_id: int | None = None


class CapacityActionCandidateRead(BaseModel):
    action_type: Literal[
        "set_task_estimate",
        "start_task",
        "review_daily_overload",
        "navigate_same_day_deadlines",
    ]
    target_type: Literal["task", "local_date"]
    target_id: int | str
    title: str
    explanation: str
    risk_level: Literal["high", "medium", "unknown", "low"]
    execution_mode: Literal["accept", "review", "navigate"]
    suggestion_id: int | None = None
    allowed_input: dict[str, object] = Field(default_factory=dict)
    source_refs: list["AgentSourceRefRead"] = Field(default_factory=list, max_length=50)


class AgentSuggestionAccept(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    priority: int | None = Field(default=None, ge=4, le=5)
    estimated_minutes: int | None = Field(default=None, ge=15, le=10080)
    idempotency_key: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class TaskCompletionFeedback(BaseModel):
    """Optional feedback; an omitted body preserves the old one-click completion."""

    model_config = ConfigDict(extra="forbid")

    actual_minutes: int | None = Field(default=None, ge=15, le=10080)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    idempotency_key: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
    )


class TaskCompletionRead(BaseModel):
    """The task result and the durable receipt proving the completion action."""

    status: Literal["executed"] = "executed"
    task: TaskRead
    receipt: ActionReceiptRead
    message: str


class AgentPlanDeltaAccept(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    idempotency_key: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class CalibrationRead(BaseModel):
    course_id: int
    minimum_sample_count: int
    sample_count: int
    eligible: bool
    factor: float | None
    ratio_bounds: dict[str, float]
    median_ratio: float | None
    difficulty_average: float | None
    reset_at: UtcDateTime | None
    explanation: str


TrendStatus = Literal["known", "partial", "unknown"]


class LearningTrendSignalRead(BaseModel):
    """A bounded, explanatory signal derived from completed-task feedback."""

    code: Literal[
        "learning_day_distribution",
        "longest_idle_gap",
        "load_concentration",
        "completion_pace",
    ]
    status: TrendStatus
    window_start: UtcDateTime
    window_end: UtcDateTime
    timezone: Literal["Asia/Shanghai"]
    minimum_sample_count: int = Field(ge=1)
    sample_count: int = Field(ge=0)
    known_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    value: int | float | str | None = None
    direction: Literal["accelerating", "slowing", "stable"] | None = None
    explanation: str = Field(max_length=500)
    limitations: list[str] = Field(default_factory=list, max_length=10)
    source_refs: list["AgentSourceRefRead"] = Field(default_factory=list, max_length=50)
    calculation_basis: dict[str, Any] = Field(default_factory=dict)


class LearningTrendCalibrationRead(BaseModel):
    """Read-only calibration context; it never applies an estimate change."""

    course_id: int
    status: TrendStatus
    window_start: UtcDateTime
    window_end: UtcDateTime
    timezone: Literal["Asia/Shanghai"]
    minimum_sample_count: int = Field(ge=1)
    sample_count: int = Field(ge=0)
    known_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    factor: float | None = None
    limitations: list[str] = Field(default_factory=list, max_length=10)
    source_refs: list["AgentSourceRefRead"] = Field(default_factory=list, max_length=50)


class LearningTrendAdjustmentCandidateRead(BaseModel):
    """A navigation/review card, deliberately not an executable action."""

    action_type: Literal["review_learning_rhythm"]
    target_type: Literal["learning_trend"]
    target_id: Literal["longest_idle_gap", "load_concentration", "completion_pace"]
    status: TrendStatus
    window_start: UtcDateTime
    window_end: UtcDateTime
    timezone: Literal["Asia/Shanghai"]
    title: str = Field(max_length=120)
    explanation: str = Field(max_length=300)
    execution_mode: Literal["review"] = "review"
    allowed_input: dict[str, object] = Field(default_factory=dict)
    source_refs: list["AgentSourceRefRead"] = Field(default_factory=list, max_length=50)


class LearningTrendsRead(BaseModel):
    """Read-only, single-user learning rhythm evidence, never a plan mutation."""

    status: TrendStatus
    window_start: UtcDateTime
    window_end: UtcDateTime
    evaluated_at: UtcDateTime
    timezone: Literal["Asia/Shanghai"]
    minimum_sample_count: int = Field(ge=1)
    sample_count: int = Field(ge=0)
    known_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    signals: list[LearningTrendSignalRead] = Field(default_factory=list, max_length=4)
    calibration_context: list[LearningTrendCalibrationRead] = Field(default_factory=list, max_length=50)
    adjustment_candidates: list[LearningTrendAdjustmentCandidateRead] = Field(default_factory=list, max_length=3)
    limitations: list[str] = Field(default_factory=list, max_length=15)
    source_refs: list["AgentSourceRefRead"] = Field(default_factory=list, max_length=50)
    calculation_basis: dict[str, Any] = Field(default_factory=dict)


LearningRhythmHistoryStatus = Literal["known", "partial", "unknown", "service_not_available"]


class AgentSourceRefRead(BaseModel):
    """Small, navigation-safe source reference used by weekly evidence."""

    source_type: str
    source_id: int | str
    navigation_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    source_name: str | None = None
    snapshot: dict[str, Any] = Field(default_factory=dict)


ActivityKind = Literal["event", "suggestion", "receipt", "run"]
ActivityEvent = Literal[
    "suggestion_generated", "suggestion_confirmed", "suggestion_executed", "suggestion_failed",
    "suggestion_expired", "suggestion_ignored", "task_recorded", "evaluation_recorded",
    "calibration_recorded", "reminder_ignored", "material_extraction_confirmed", "execution_receipt",
    "run_completed", "run_recorded",
    "unavailable",
]
ActivityStatus = Literal["generated", "confirmed", "executed", "failed", "expired", "ignored", "recorded", "completed", "unavailable"]
ActivitySourceType = Literal[
    "task", "material", "study_plan", "study_plan_item", "action_receipt",
    "task_collection", "material_collection", "study_plan_collection", "capacity",
]


class AgentActivitySourceRefRead(BaseModel):
    """Minimal resolver identity; activity never exposes source snapshots."""

    source_type: ActivitySourceType
    source_id: int | str
    navigation_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


class AgentActivitySourceRead(BaseModel):
    """Only a resolver-compatible evidence identity, never a path or payload."""

    status: Literal["available", "unavailable"]
    source_ref: AgentActivitySourceRefRead | None = None
    message: str = Field(max_length=240)


class AgentActivityItemRead(BaseModel):
    """One stable, bounded, user-facing projection of agent audit history."""

    activity_id: str = Field(max_length=80)
    kind: ActivityKind
    event: ActivityEvent
    status: ActivityStatus
    occurred_at: UtcDateTime
    title: str = Field(max_length=200)
    description: str = Field(max_length=500)
    source: AgentActivitySourceRead
    suggestion_id: int | None = Field(default=None, ge=1)
    receipt_id: int | None = Field(default=None, ge=1)
    run_id: int | None = Field(default=None, ge=1)


class AgentActivityRead(BaseModel):
    items: list[AgentActivityItemRead] = Field(default_factory=list, max_length=50)
    limit: int = Field(ge=1, le=50)
    generated_at: UtcDateTime
    calculation_basis: dict[str, Any] = Field(default_factory=dict)


class LearningRhythmHistoryWindowRead(BaseModel):
    """Metadata for an actual frozen weekly snapshot, never a synthetic week."""

    snapshot_id: int
    window_key: str
    window_start: UtcDateTime
    window_end: UtcDateTime
    snapshot_status: Literal["closed"]
    ruleset_version: str
    evidence_digest: str
    rhythm_summary_version: str | None = None
    rhythm_summary_status: LearningRhythmHistoryStatus | None = None


class LearningRhythmHistoryComparisonRead(BaseModel):
    """A deliberately non-executable frozen-rhythm comparison result."""

    status: LearningRhythmHistoryStatus
    comparable: bool
    reason_codes: list[str] = Field(default_factory=list, max_length=10)
    sample_count: int = Field(ge=0)
    known_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    compared_snapshot_ids: list[int] = Field(default_factory=list, max_length=2)
    source_refs: list[AgentSourceRefRead] = Field(default_factory=list, max_length=50)
    limitations: list[str] = Field(default_factory=list, max_length=10)
    calculation_basis: dict[str, Any] = Field(default_factory=dict)


class LearningRhythmHistoryRead(BaseModel):
    """Read-only availability and comparison contract for frozen rhythm data."""

    status: LearningRhythmHistoryStatus
    timezone: Literal["Asia/Shanghai"]
    evaluated_at: UtcDateTime
    minimum_comparable_window_count: int = Field(ge=2)
    closed_snapshot_count: int = Field(ge=0)
    available_windows: list[LearningRhythmHistoryWindowRead] = Field(default_factory=list, max_length=12)
    comparison: LearningRhythmHistoryComparisonRead
    limitations: list[str] = Field(default_factory=list, max_length=10)
    source_refs: list[AgentSourceRefRead] = Field(default_factory=list, max_length=50)
    calculation_basis: dict[str, Any] = Field(default_factory=dict)


# Evidence is deliberately resolved by the server before the UI navigates.
# These are the only source families emitted by the weekly-review, reminder,
# and action evidence.  A client cannot supply a route, query string, file
# path, or arbitrary source family to turn an evidence card into navigation.
EvidenceSourceType = Literal[
    "task",
    "material",
    "study_plan",
    "study_plan_item",
    "action_receipt",
    "task_collection",
    "material_collection",
    "study_plan_collection",
    "capacity",
]


class AgentSourceRefResolveInput(BaseModel):
    """Identity only: historic display/snapshot data is never client input."""

    model_config = ConfigDict(extra="forbid")

    source_type: EvidenceSourceType
    source_id: str = Field(min_length=1, max_length=160)
    navigation_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")

    @field_validator("source_id", mode="before")
    @classmethod
    def _source_identifier_is_bounded_text(cls, value: Any) -> str:
        # IDs in old evidence may be JSON numbers while collection/item IDs
        # are strings. Normalize both to a safe textual identity before any
        # resolver sees them; booleans and structured payloads are not IDs.
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValueError("source_id 必须是整数或文本标识")
        normalized = str(value)
        # Source IDs are identities, never a transport for terminal controls
        # or a client route.  Plan-item identifiers may contain ordinary
        # Unicode text, so only control characters are rejected here.
        if any(ord(char) < 32 or ord(char) == 127 for char in normalized):
            raise ValueError("source_id 不能包含控制字符")
        return normalized


class AgentSourceNavigationResolve(BaseModel):
    """Bounded batch lookup for existing in-app destinations; it never writes."""

    model_config = ConfigDict(extra="forbid")

    source_refs: list[AgentSourceRefResolveInput] = Field(min_length=1, max_length=50)


class AgentNavigationTargetRead(BaseModel):
    """A server-issued local route, never an external URL or raw storage path."""

    path: Literal["/tasks", "/materials", "/study-plans"]
    query: dict[str, str] = Field(default_factory=dict, max_length=3)


class AgentSourceNavigationItemRead(BaseModel):
    source_ref: AgentSourceRefResolveInput
    available: bool
    target: AgentNavigationTargetRead | None = None
    label: str | None = Field(default=None, max_length=200)
    message: str = Field(max_length=240)


class AgentSourceNavigationRead(BaseModel):
    items: list[AgentSourceNavigationItemRead] = Field(default_factory=list, max_length=50)


class WeeklyMetricRead(BaseModel):
    count: int = Field(ge=0)
    known_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    value: int | float | None = None
    status: Literal["known", "partial", "unknown"]
    sample_count: int | None = Field(default=None, ge=0)
    missing_count: int | None = Field(default=None, ge=0)
    direction: Literal["overrun", "underrun", "balanced"] | None = None
    source_refs: list[AgentSourceRefRead] = Field(default_factory=list, max_length=50)
    calculation_basis: dict[str, Any] = Field(default_factory=dict)


class WeeklyActionRead(BaseModel):
    action_type: str
    target_type: str
    target_id: int | str
    title: str
    explanation: str
    reason_code: str
    risk_level: Literal["high", "medium", "low"]
    execution_mode: Literal["accept", "review", "navigate"]
    suggestion_id: int | None = None
    source_refs: list[AgentSourceRefRead] = Field(default_factory=list, max_length=50)


class WeeklyReviewRead(BaseModel):
    window_start: UtcDateTime
    window_end: UtcDateTime
    evaluated_at: UtcDateTime
    timezone: Literal["Asia/Shanghai"]
    calculation_basis: dict[str, Any]
    completed_tasks: WeeklyMetricRead
    overdue_tasks: WeeklyMetricRead
    estimate_variance: WeeklyMetricRead
    plan_item_status: WeeklyMetricRead
    review_materials: WeeklyMetricRead
    failed_materials: WeeklyMetricRead
    execution_receipts: WeeklyMetricRead
    next_week_actions: list[WeeklyActionRead] = Field(default_factory=list, max_length=3)


ReminderCategory = Literal["deadlines", "plans", "materials", "estimation", "capacity"]
ReminderRisk = Literal["high", "medium", "low"]
ReminderDigestFrequency = Literal["immediate", "daily", "weekly"]


class AgentReminderPreferenceRead(BaseModel):
    """Server-authoritative display policy; it cannot hide high-risk facts."""

    model_config = ConfigDict(from_attributes=True)

    enabled_categories: list[ReminderCategory] = Field(default_factory=list, max_length=5)
    minimum_risk_level: ReminderRisk
    digest_frequency: ReminderDigestFrequency
    high_risk_policy: Literal["always_presented"] = "always_presented"
    created_at: UtcDateTime
    updated_at: UtcDateTime


class AgentReminderPreferenceUpdate(BaseModel):
    """Only explicitly whitelisted presentation fields are writable."""

    model_config = ConfigDict(extra="forbid")

    enabled_categories: list[ReminderCategory] | None = Field(default=None, max_length=5)
    minimum_risk_level: ReminderRisk | None = None
    digest_frequency: ReminderDigestFrequency | None = None

    @field_validator("enabled_categories")
    @classmethod
    def _categories_are_unique(cls, value: list[ReminderCategory] | None) -> list[ReminderCategory] | None:
        if value is not None and len(set(value)) != len(value):
            raise ValueError("enabled_categories 不能包含重复类别")
        return value


class WeeklyReviewSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    window_key: str
    window_start: UtcDateTime
    window_end: UtcDateTime
    evaluated_at: UtcDateTime
    snapshot_status: Literal["current", "closed"]
    ruleset_version: str
    evidence_digest: str
    review: WeeklyReviewRead
    rhythm_summary_version: str | None = None
    created_at: UtcDateTime
    updated_at: UtcDateTime


class WeeklyReviewHistoryRead(BaseModel):
    items: list[WeeklyReviewSnapshotRead] = Field(default_factory=list, max_length=12)
    retention_limit: int = Field(ge=1, le=52)
    calculation_basis: dict[str, Any] = Field(default_factory=dict)


class ReminderPresentationRead(BaseModel):
    """The server's current in-app digest decision for the Agent Center."""

    digest_frequency: ReminderDigestFrequency
    digest_bucket: str | None = None
    noncritical_digest_eligible: bool
    high_risk_policy: Literal["always_presented"] = "always_presented"
    presentation_scope: Literal["in-app Agent Center only; no external push or notification is sent"]
    last_digest_bucket_before: str | None = None
    noncritical_candidate_count: int = Field(ge=0)
    digest_consumed: bool
    high_risk_presented_count: int = Field(ge=0)


class AgentReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: Literal["active", "dismissed", "resolved"]
    risk_level: Literal["high", "medium", "low"]
    reason_code: str
    source_type: str
    source_id: str
    title: str
    explanation: str
    source_refs: list[AgentSourceRefRead]
    calculation_basis: dict[str, Any]
    fingerprint: str
    created_at: UtcDateTime
    updated_at: UtcDateTime
    dismissed_at: UtcDateTime | None
    dismissal_reason: str | None


class AgentReminderDismiss(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str | None = Field(default=None, max_length=500)


from app.schemas.capacity import CapacityRead


class AgentSuggestionDismiss(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str | None = Field(default=None, max_length=500)
