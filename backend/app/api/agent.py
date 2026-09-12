"""Server-authoritative API for the M8.1 learning-agent loop."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.exc import StaleDataError

from app.database import get_db
from app.models.agent import ActionReceipt, AgentEvent, AgentReminder, AgentRun, AgentSuggestion
from app.models.task import Task
from app.models.study_plan import StudyPlan
from app.models.material import Material
from app.models.course import Course
from app.schemas.agent import (
    AgentBriefingRead,
    AgentActivityRead,
    AgentReminderDismiss,
    AgentReminderPreferenceRead,
    AgentReminderPreferenceUpdate,
    AgentReminderRead,
    AgentSourceNavigationRead,
    AgentSourceNavigationResolve,
    AgentSuggestionAccept,
    AgentSuggestionDismiss,
    AgentSuggestionRead,
    AgentPlanDeltaAccept,
    CalibrationRead,
    LearningRhythmHistoryRead,
    LearningTrendsRead,
    TaskCompletionFeedback,
    TaskCompletionRead,
    WeeklyReviewHistoryRead,
    WeeklyReviewRead,
    WeeklyReviewSnapshotRead,
    SuggestionStatus,
)
from app.schemas.study_plan import StudyPlanItem
from app.schemas.task import TaskRead
from app.schemas.capacity import CapacityRead
from app.services.agent import (
    ADJUST_PRIORITY,
    SET_TASK_ESTIMATE,
    START_TASK,
    is_action_candidate,
    refresh_suggestions,
    task_fingerprint,
    task_snapshot_payload,
)
from app.services.agent_feedback import (
    APPLY_PLAN_DELTA,
    COMPLETE_TASK,
    calibration_payload,
    complete_task_with_feedback,
    create_plan_delta_candidates,
    recompute_delta_is_current,
    reset_calibration,
)
from app.services.study_plan import (
    decode_plan_agent_metadata,
    decode_plan_content,
    decode_plan_unscheduled_items,
    encode_plan_content_with_metadata,
    plan_content_fingerprint,
)
from app.time import as_local, as_utc, utc_now
from app.services.study_preferences import build_capacity
from app.services.study_preferences import get_or_create_preference
from app.services.weekly_review import build_weekly_review, sync_weekly_reminders
from app.services.weekly_review_history import (
    WEEKLY_REVIEW_RETENTION_LIMIT,
    get_or_create_reminder_preferences,
    list_weekly_review_history,
    materialize_weekly_review,
    reminder_presentation,
    reminder_preference_read,
    snapshot_read,
)
from app.services.evidence_navigation import resolve_source_navigation_batch
from app.services.learning_trends import build_learning_trends
from app.services.learning_rhythm_history import build_learning_rhythm_history
from app.services.activity import ACTIVITY_LIMIT, build_activity
from app.services.decision_queue import build_decision_queue
from app.services.edit_concurrency import check_edit_precondition, edit_conflict

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "AGENT_SUGGESTION_NOT_FOUND", "message": "智能体建议不存在"})


def _conflict(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=409, detail={"code": code, "message": message})


def _suggestion_statement():
    # Sessions deliberately use expire_on_commit=False. Refresh the identity-map
    # value here so a just-created receipt is included in the response.
    return select(AgentSuggestion).options(joinedload(AgentSuggestion.receipt)).execution_options(populate_existing=True)


def _is_visible_pending(db: Session, suggestion: AgentSuggestion, now: datetime) -> bool:
    """Never advertise a candidate that the matching accept endpoint would reject."""

    if as_utc(suggestion.expires_at) <= now:
        return False
    if suggestion.action_type == APPLY_PLAN_DELTA:
        plan, task, changes = recompute_delta_is_current(db, suggestion)
        return plan is not None and task is not None and bool(changes)
    task = db.get(Task, suggestion.source_id) if suggestion.source_type == "task" else None
    return bool(task is not None and task.navigation_key == suggestion.source_navigation_key
                and is_action_candidate(task, suggestion.action_type, now)
                and task_fingerprint(task, suggestion.action_type) == suggestion.fingerprint)


def _briefing(db: Session) -> AgentBriefingRead:
    now = utc_now()
    pending = list(
        db.scalars(
            _suggestion_statement()
            .where(AgentSuggestion.status == "pending")
            .order_by(AgentSuggestion.expires_at.asc(), AgentSuggestion.created_at.desc())
        ).unique().all()
    )
    # Briefing is read-only, but it must never surface a stale recommendation.
    # Refresh/accept/dismiss persist the terminal expired state when they act.
    valid_pending = [item for item in pending if _is_visible_pending(db, item, now)]
    # The original suggestion inbox remains the deadline-priority queue. New
    # capacity controls are intentionally surfaced only through their typed
    # capacity candidates, so a user is never shown two competing inbox items
    # for the same task.
    suggestions = [item for item in valid_pending if item.action_type == ADJUST_PRIORITY]
    recent_results = list(
        db.scalars(
            _suggestion_statement()
            .where(AgentSuggestion.status.in_(("executed", "failed", "dismissed", "expired")))
            .order_by(AgentSuggestion.updated_at.desc(), AgentSuggestion.id.desc())
            .limit(5)
        ).unique().all()
    )
    plan_deltas = [item for item in valid_pending if item.action_type == APPLY_PLAN_DELTA][:3]
    # Every derived part of one briefing shares one evaluation instant, so a
    # deadline exactly on a boundary cannot disagree across the response.
    generated_at = now
    capacity = build_capacity(db, evaluated_at=now)
    capacity_action_candidates = _capacity_action_candidates(capacity, valid_pending)
    decision_queue = build_decision_queue(
        db,
        pending=valid_pending,
        capacity_candidates=capacity_action_candidates,
        evaluated_at=now,
    )
    preference = get_or_create_preference(db)
    weekly_review = build_weekly_review(db, evaluated_at=now)
    materialize_weekly_review(db, weekly_review, evaluated_at=now)
    # Materializing reminders is deliberately the only briefing write. It is
    # idempotent for the same evidence and retains a dismissal instead of
    # recreating the signal on each refresh.
    sync_weekly_reminders(db, weekly_review, evaluated_at=now)
    reminder_preferences = get_or_create_reminder_preferences(db)
    reminders, reminder_presentation_basis = reminder_presentation(
        db, reminder_preferences, evaluated_at=now, consume_digest=True
    )
    return AgentBriefingRead(
        generated_at=generated_at,
        # Count cards actually presented as confirmation items. Capacity/start
        # controls have their own sections and must not double-count one task.
        pending_count=len(suggestions) + len(plan_deltas),
        suggestions=suggestions[:3],
        inbox=_inbox_summary(db),
        decision_queue=decision_queue,
        capacity=capacity,
        today_actions=_today_actions(db, capacity, preference, valid_pending, evaluated_at=now),
        capacity_action_candidates=capacity_action_candidates,
        recent_results=recent_results,
        plan_deltas=plan_deltas,
        weekly_review=weekly_review,
        reminders=reminders,
        reminder_preferences=reminder_preference_read(reminder_preferences),
        reminder_presentation=reminder_presentation_basis,
    )


def _inbox_summary(db: Session) -> dict[str, dict[str, object]]:
    """A read-only extraction inbox; it never performs extraction or creates tasks."""

    result: dict[str, dict[str, object]] = {}
    for status in ("ready", "needs_review", "failed"):
        condition = (
            or_(Material.extraction_status == "failed", Material.processing_status == "failed")
            if status == "failed"
            else Material.extraction_status == status
        )
        # DISTINCT makes rows failed in both processing and extraction appear
        # once in the evidence list.
        ids = list(db.scalars(select(Material.id).where(condition).distinct().order_by(Material.id)).all())
        result[status] = {"count": len(ids), "material_ids": ids}
    return result


def _today_actions(
    db: Session, capacity, preference, pending: list[AgentSuggestion], *, evaluated_at: datetime
) -> list[dict[str, object]]:
    """Project up to three deterministic next actions without changing Task state."""

    now = evaluated_at
    daily_risks = {group.local_date: group.risk_level for group in capacity.daily_risk_groups}
    same_day_dates = {group.local_date for group in capacity.same_day_deadline_groups}
    courses = {course.id: course.name for course in db.scalars(select(Course)).all()}
    starts = {item.source_id: item for item in pending if item.action_type == START_TASK}
    rows: list[tuple[tuple[object, ...], dict[str, object]]] = []
    for task in db.scalars(select(Task).where(~Task.status.in_(["completed", "canceled"]))).all():
        due_at = as_utc(task.due_at) if task.due_at is not None else None
        hours = (due_at - now).total_seconds() / 3600 if due_at is not None else None
        if hours is not None and hours < 0:
            deadline_score, deadline_code, deadline_reason = 1000.0, "overdue", "已逾期，应优先处理"
        elif hours is not None and hours <= 24:
            deadline_score, deadline_code, deadline_reason = 800.0, "due_within_24h", "24 小时内到期"
        elif hours is not None and hours <= 48:
            deadline_score, deadline_code, deadline_reason = 600.0, "due_within_48h", "48 小时内到期"
        elif hours is not None and hours <= 7 * 24:
            deadline_score, deadline_code, deadline_reason = 300.0, "due_within_7d", "未来 7 天内到期"
        else:
            deadline_score, deadline_code, deadline_reason = 0.0, "no_near_deadline", "暂无临近截止时间"
        weight = float(preference.course_weights.get(str(task.course_id), 1.0)) if task.course_id else 1.0
        counted = task.remaining_minutes if task.remaining_minutes is not None else task.estimated_minutes
        # The capacity service is authoritative for China-local grouping. Match its group by UTC->local date.
        local_date = None
        if due_at is not None:
            local_date = as_local(due_at).date().isoformat()
        capacity_risk = daily_risks.get(local_date, capacity.risk_level) if local_date else capacity.risk_level
        deadline_risk = "high" if hours is not None and hours <= 24 else ("medium" if hours is not None and hours <= 48 else "low")
        risk_rank = {"low": 0, "unknown": 1, "medium": 2, "high": 3}
        risk_level = max((deadline_risk, capacity_risk), key=lambda level: risk_rank[level])
        reason_codes = [deadline_code, "priority", "course_weight"]
        reasons = [deadline_reason, f"当前优先级为 {task.priority}", f"课程权重为 {weight:g}"]
        if counted is None:
            reason_codes.append("missing_estimate")
            reasons.append("尚未填写预计时长，未伪造分钟数")
        else:
            reason_codes.append("workload_known")
            reasons.append(f"待处理时长约 {counted} 分钟")
        if capacity_risk in ("high", "medium", "unknown"):
            reason_codes.append(f"capacity_{capacity_risk}")
            reasons.append({"high": "当日容量已超载", "medium": "当日容量接近上限", "unknown": "当日容量仍缺少估时"}[capacity_risk])
        same_day_conflict = local_date in same_day_dates
        if same_day_conflict:
            reason_codes.append("same_day_deadline_conflict")
            reasons.append("同日有多项截止任务，需要统筹安排")
        # Shorter known work gets a small, explicit quick-win boost. It never
        # dominates deadline/priority, but resolves equal urgent work in a
        # capacity-aware way without inventing a value for missing estimates.
        quick_win = round(max(0, 120 - counted) / 10, 2) if counted is not None else 0.0
        components = {
            "deadline": deadline_score,
            "priority": float(task.priority * 50),
            "course_weight": round(weight * 20, 2),
            "in_progress": 30.0 if task.status == "in_progress" else 0.0,
            "capacity_risk": {"high": 100.0, "medium": 50.0, "unknown": 25.0, "low": 0.0}[capacity_risk],
            "quick_win": quick_win,
            # Deliberately small: deadline tier remains the primary sort key.
            "same_day_deadline_conflict": 20.0 if same_day_conflict else 0.0,
        }
        score = round(sum(components.values()), 2)
        deadline_tier = 4 if deadline_code == "overdue" else (3 if deadline_code == "due_within_24h" else (2 if deadline_code == "due_within_48h" else (1 if deadline_code == "due_within_7d" else 0)))
        rows.append((
            (-deadline_tier, -score, due_at or datetime.max.replace(tzinfo=timezone.utc), -task.priority, task.id),
            {
                "task_id": task.id, "task_navigation_key": task.navigation_key, "task_name": task.name, "course_id": task.course_id,
                "course_name": courses.get(task.course_id), "due_at": due_at,
                "estimated_minutes": task.estimated_minutes, "remaining_minutes": task.remaining_minutes,
                "counted_minutes": counted,
                "minute_source": "remaining_minutes" if task.remaining_minutes is not None else ("estimated_minutes" if task.estimated_minutes is not None else None),
                "risk_level": risk_level, "preferred_time_slot": "evening", "reason_codes": reason_codes,
                "display_reasons": reasons, "score": score, "score_components": components,
                "score_basis": {"deadline_hours": round(hours, 2) if hours is not None else None,
                                "course_weight": weight, "minute_source": "remaining_minutes" if task.remaining_minutes is not None else ("estimated_minutes" if task.estimated_minutes is not None else None),
                                "effective_daily_capacity_minutes": capacity.calculation_basis.effective_daily_capacity_minutes,
                                "deadline_risk": deadline_risk, "capacity_risk": capacity_risk,
                                "same_day_deadline_conflict": same_day_conflict,
                                "deadline_tier": deadline_tier},
                "controlled_action": "start_task" if task.id in starts else None,
                "suggestion_id": starts[task.id].id if task.id in starts else None,
            },
        ))
    rows.sort(key=lambda item: item[0])
    slots = preference.preferred_time_slots
    actions = []
    for index, (_key, action) in enumerate(rows[:3]):
        action["preferred_time_slot"] = slots[index % len(slots)]
        actions.append(action)
    return actions


def _capacity_action_candidates(capacity, pending: list[AgentSuggestion]) -> list[dict[str, object]]:
    """Expose only fixed server action types/targets; no client-composed operation exists."""

    pending_by_action_task = {(item.action_type, item.source_id): item for item in pending}
    task_by_id = {item.id: item for item in capacity.tasks}

    def task_ref(task_id: int) -> dict[str, object] | None:
        task = task_by_id.get(task_id)
        if task is None:
            return None
        return {
            "source_type": "task", "source_id": task.id, "navigation_key": task.navigation_key, "source_name": task.name,
            "snapshot": {
                "due_at": as_utc(task.due_at).isoformat(), "counted_minutes": task.counted_minutes,
                "estimated_minutes": task.estimated_minutes, "remaining_minutes": task.remaining_minutes,
            },
        }

    def capacity_refs(*, local_date: str, task_ids: list[int], risk_level: str | None = None,
                      known_workload_minutes: int | None = None, overload_minutes: int | None = None) -> list[dict[str, object]]:
        # `capacity/next_7_days` is an explicit resolver whitelist key.  It
        # gives every capacity review card a stable safe destination even if a
        # referenced task disappears after this briefing was generated.
        refs: list[dict[str, object]] = [{
            "source_type": "capacity", "source_id": "next_7_days", "source_name": "未来 7 天学习容量",
            "snapshot": {
                "local_date": local_date, "risk_level": risk_level,
                "known_workload_minutes": known_workload_minutes, "overload_minutes": overload_minutes,
                "task_ids": task_ids[:49],
            },
        }]
        refs.extend(ref for task_id in task_ids[:49] if (ref := task_ref(task_id)) is not None)
        return refs

    candidates: list[dict[str, object]] = []
    for task_id in capacity.missing_estimate_task_ids:
        suggestion = pending_by_action_task.get((SET_TASK_ESTIMATE, task_id))
        candidates.append({"action_type": SET_TASK_ESTIMATE, "target_type": "task", "target_id": task_id,
                           "title": "补充任务预计时长",
                           "explanation": "填写后将参与容量计算。" if suggestion else "请先刷新智能体建议后再确认预计时长。",
                           "risk_level": "unknown", "execution_mode": "accept" if suggestion else "review",
                           "suggestion_id": suggestion.id if suggestion else None,
                           "allowed_input": {"estimated_minutes": {"minimum": 15, "maximum": 10080}},
                           "source_refs": [ref] if (ref := task_ref(task_id)) is not None else []})
    # Start suggestions may rank below today's top three; retain a typed
    # discoverability path instead of leaving those persisted actions orphaned.
    for suggestion in sorted(
        (item for item in pending if item.action_type == START_TASK),
        key=lambda item: (as_utc(item.expires_at), item.source_id, item.id),
    ):
        candidates.append({"action_type": START_TASK, "target_type": "task", "target_id": suggestion.source_id,
                           "title": suggestion.title, "explanation": suggestion.explanation,
                           "risk_level": suggestion.risk_level, "execution_mode": "accept",
                           "suggestion_id": suggestion.id, "allowed_input": {},
                           "source_refs": [ref] if (ref := task_ref(suggestion.source_id)) is not None else []})
    for group in capacity.daily_risk_groups:
        if group.risk_level == "high":
            candidates.append({"action_type": "review_daily_overload", "target_type": "local_date", "target_id": group.local_date,
                               "title": "复核当日超载", "explanation": f"已知工作量超出有效日容量 {group.overload_minutes} 分钟，需要人工调整安排。",
                               "risk_level": "high", "execution_mode": "review", "suggestion_id": None, "allowed_input": {},
                               "source_refs": capacity_refs(
                                   local_date=group.local_date, task_ids=group.task_ids, risk_level=group.risk_level,
                                   known_workload_minutes=group.known_workload_minutes,
                                   overload_minutes=group.overload_minutes,
                               )})
    for group in capacity.same_day_deadline_groups:
        candidates.append({"action_type": "navigate_same_day_deadlines", "target_type": "local_date", "target_id": group.local_date,
                           "title": "查看同日截止任务", "explanation": f"当天有 {group.task_count} 项截止任务，建议集中查看安排。",
                           "risk_level": "medium", "execution_mode": "navigate", "suggestion_id": None, "allowed_input": {},
                           "source_refs": capacity_refs(
                               local_date=group.local_date, task_ids=group.task_ids,
                               known_workload_minutes=group.known_workload_minutes,
                           )})
    return candidates


@router.get("/briefing", response_model=AgentBriefingRead)
def get_briefing(db: Session = Depends(get_db)) -> AgentBriefingRead:
    return _briefing(db)


@router.post("/refresh", response_model=AgentBriefingRead)
def refresh_agent(db: Session = Depends(get_db)) -> AgentBriefingRead:
    refresh_suggestions(db)
    return _briefing(db)


@router.get("/capacity", response_model=CapacityRead)
def get_capacity(db: Session = Depends(get_db)) -> CapacityRead:
    return build_capacity(db)


@router.get("/learning-trends", response_model=LearningTrendsRead)
def get_learning_trends(db: Session = Depends(get_db)) -> dict:
    """Return bounded local rhythm evidence; this GET never persists changes."""

    return build_learning_trends(db)


@router.get("/learning-rhythm-history", response_model=LearningRhythmHistoryRead)
def get_learning_rhythm_history(db: Session = Depends(get_db)) -> dict:
    """Return only frozen, same-caliber rhythm history; this GET never writes."""

    return build_learning_rhythm_history(db)


@router.get("/activity", response_model=AgentActivityRead)
def get_agent_activity(
    limit: int = Query(default=ACTIVITY_LIMIT, ge=1, le=ACTIVITY_LIMIT),
    db: Session = Depends(get_db),
) -> dict:
    """Read a bounded public audit timeline without refreshing or writing state."""

    return build_activity(db, limit=limit)


@router.post("/source-navigation/resolve", response_model=AgentSourceNavigationRead)
def resolve_agent_source_navigation(
    payload: AgentSourceNavigationResolve, db: Session = Depends(get_db)
) -> dict:
    """Resolve existing local evidence to fixed in-app routes without writes.

    The request only identifies persisted evidence.  It cannot carry a route,
    URL, raw upload path, or a mutation instruction, and missing historic rows
    return an explicit unavailable result instead of a guessed destination.
    """

    return {"items": resolve_source_navigation_batch(db, payload.source_refs)}


@router.get("/weekly-review", response_model=WeeklyReviewRead)
def get_weekly_review(db: Session = Depends(get_db)) -> dict:
    """Expose the current local-only review without creating a free-form plan."""

    review = build_weekly_review(db)
    materialize_weekly_review(db, review, evaluated_at=review["evaluated_at"])
    sync_weekly_reminders(db, review, evaluated_at=review["evaluated_at"])
    return review


@router.post("/weekly-review/refresh", response_model=WeeklyReviewSnapshotRead)
def refresh_weekly_review(db: Session = Depends(get_db)) -> dict:
    """Persist the current actual review window without creating fake history."""

    review = build_weekly_review(db)
    snapshot = materialize_weekly_review(db, review, evaluated_at=review["evaluated_at"])
    sync_weekly_reminders(db, review, evaluated_at=review["evaluated_at"])
    return snapshot_read(snapshot)


@router.get("/weekly-reviews", response_model=WeeklyReviewHistoryRead)
def get_weekly_review_history(
    limit: int = Query(default=WEEKLY_REVIEW_RETENTION_LIMIT, ge=1, le=WEEKLY_REVIEW_RETENTION_LIMIT),
    db: Session = Depends(get_db),
) -> dict:
    """Read only materialized windows; gaps intentionally remain gaps."""

    items = list_weekly_review_history(db, limit=limit)
    return {
        "items": [snapshot_read(item) for item in items],
        "retention_limit": WEEKLY_REVIEW_RETENTION_LIMIT,
        "calculation_basis": {
            "storage_semantics": "one snapshot per actually refreshed China-local seven-day window; no missing windows are fabricated",
            "retention": f"newest {WEEKLY_REVIEW_RETENTION_LIMIT} windows by window_end",
            "evidence": "each snapshot stores the existing weekly-review payload and a digest excluding refresh-clock timestamps",
        },
    }


@router.get("/reminder-preferences", response_model=AgentReminderPreferenceRead)
def get_reminder_preferences(db: Session = Depends(get_db)) -> dict:
    return reminder_preference_read(get_or_create_reminder_preferences(db))


@router.patch("/reminder-preferences", response_model=AgentReminderPreferenceRead)
def update_reminder_preferences(
    payload: AgentReminderPreferenceUpdate, db: Session = Depends(get_db)
) -> dict:
    """Update only display/digest choices; reminders and evidence never mutate."""

    preference = get_or_create_reminder_preferences(db)
    changes = payload.model_dump(exclude_unset=True)
    changed = False
    for field, value in changes.items():
        normalized = list(value) if field == "enabled_categories" else value
        if getattr(preference, field) != normalized:
            setattr(preference, field, normalized)
            changed = True
    if changed:
        now = utc_now()
        # A changed display policy deserves a fresh in-app digest decision;
        # this never alters any reminder's evidence or dismissal state.
        preference.last_digest_bucket = None
        preference.updated_at = now
        db.add(AgentEvent(
            event_type="reminder_preferences_updated",
            entity_type="agent_reminder_preference",
            entity_id=preference.id,
            payload={
                "fields": sorted(changes),
                "high_risk_policy": "always_presented",
                "presentation_only": True,
            },
        ))
        db.commit()
        db.refresh(preference)
    return reminder_preference_read(preference)


@router.get("/reminders", response_model=list[AgentReminderRead])
def list_reminders(
    status: str = Query(default="active", pattern="^(active|dismissed|resolved)$"),
    presentation: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[AgentReminder]:
    # Default remains the complete audit list used by M8.5.  The opt-in view
    # applies only user-facing presentation choices, with high-risk evidence
    # always retained; it never changes durable reminder status.
    if status == "active" and presentation:
        reminders, _basis = reminder_presentation(db)
        return reminders
    return list(db.scalars(select(AgentReminder).where(AgentReminder.status == status).order_by(
        AgentReminder.updated_at.desc(), AgentReminder.id.desc()
    )).all())


@router.post("/reminders/{reminder_id}/dismiss", response_model=AgentReminderRead)
def dismiss_reminder(
    reminder_id: int, payload: AgentReminderDismiss, db: Session = Depends(get_db)
) -> AgentReminder:
    reminder = db.get(AgentReminder, reminder_id)
    if reminder is None:
        raise HTTPException(status_code=404, detail={"code": "AGENT_REMINDER_NOT_FOUND", "message": "站内提醒不存在"})
    # The same user tap/retry is intentionally idempotent. Return the durable
    # dismissed record rather than turning a harmless network retry into a
    # conflict.
    if reminder.status == "dismissed":
        return reminder
    if reminder.status != "active":
        raise _conflict("REMINDER_NOT_ACTIVE", "该站内提醒当前不能忽略")
    now = utc_now()
    reminder.status = "dismissed"
    reminder.dismissed_at = now
    reminder.dismissal_reason = payload.reason
    reminder.updated_at = now
    db.add(AgentEvent(event_type="reminder_dismissed", entity_type="agent_reminder", entity_id=reminder.id,
                      payload={"reason_code": reminder.reason_code, "reason": payload.reason}))
    db.commit()
    db.refresh(reminder)
    return reminder


@router.get("/suggestions", response_model=list[AgentSuggestionRead])
def list_suggestions(
    status: SuggestionStatus | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[AgentSuggestion]:
    statement = _suggestion_statement().order_by(AgentSuggestion.created_at.desc(), AgentSuggestion.id.desc())
    if status is not None:
        statement = statement.where(AgentSuggestion.status == status)
    else:
        # The default preserves the original small deadline-priority inbox;
        # explicit status filters are the audit view for every action type.
        statement = statement.where(AgentSuggestion.action_type == ADJUST_PRIORITY)
    suggestions = list(db.scalars(statement).unique().all())
    if status == "pending":
        now = utc_now()
        return [item for item in suggestions if as_utc(item.expires_at) > now]
    return suggestions


@router.get("/plan-deltas", response_model=list[AgentSuggestionRead])
def list_plan_deltas(
    status: SuggestionStatus | None = Query(default="pending"),
    db: Session = Depends(get_db),
) -> list[AgentSuggestion]:
    statement = _suggestion_statement().where(AgentSuggestion.action_type == APPLY_PLAN_DELTA)
    if status is not None:
        statement = statement.where(AgentSuggestion.status == status)
    rows = list(db.scalars(statement.order_by(AgentSuggestion.updated_at.desc(), AgentSuggestion.id.desc())).unique().all())
    if status == "pending":
        now = utc_now()
        return [item for item in rows if _is_visible_pending(db, item, now)]
    return rows


@router.get("/calibration", response_model=CalibrationRead)
def get_calibration(course_id: int = Query(ge=1), db: Session = Depends(get_db)) -> dict:
    if db.get(Course, course_id) is None:
        raise HTTPException(status_code=404, detail={"code": "COURSE_NOT_FOUND", "message": "课程不存在"})
    return calibration_payload(db, course_id)


@router.post("/calibration/{course_id}/reset", response_model=CalibrationRead)
def reset_course_calibration(
    course_id: int,
    payload: AgentPlanDeltaAccept,
    db: Session = Depends(get_db),
) -> dict:
    if db.get(Course, course_id) is None:
        raise HTTPException(status_code=404, detail={"code": "COURSE_NOT_FOUND", "message": "课程不存在"})
    try:
        result = reset_calibration(db, course_id, idempotency_key=payload.idempotency_key)
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise _conflict(str(exc), "幂等键已用于其他操作") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail={"code": "CALIBRATION_RESET_FAILED", "message": "校准重置失败"}) from exc


@router.post("/tasks/{task_id}/complete", response_model=TaskCompletionRead)
def complete_agent_task(
    task_id: int, payload: TaskCompletionFeedback | None = None, db: Session = Depends(get_db),
    if_match: str | None = Header(default=None),
) -> dict:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "任务不存在"})
    check_edit_precondition(db, task, if_match)
    try:
        complete_task_with_feedback(
            db, task, actual_minutes=payload.actual_minutes if payload else None,
            difficulty=payload.difficulty if payload else None,
            idempotency_key=payload.idempotency_key if payload else None,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise _conflict(str(exc), "幂等键已用于其他操作") from exc
    except IntegrityError as exc:
        db.rollback()
        # A simultaneous retry may already have saved this exact request.
        existing = payload.idempotency_key if payload else None
        if existing:
            winner = db.scalar(select(AgentSuggestion).where(AgentSuggestion.idempotency_key == existing))
            if winner is not None and winner.action_type == COMPLETE_TASK and winner.source_id == task_id and winner.source_navigation_key == task.navigation_key:
                saved = db.get(Task, task_id)
                if saved is not None and winner.receipt is not None:
                    return {"status": "executed", "task": saved, "receipt": winner.receipt,
                            "message": winner.receipt.message}
        raise _conflict("AGENT_EXECUTION_CONFLICT", "任务完成请求正在被处理，请重试") from exc
    except StaleDataError as exc:
        db.rollback()
        raise edit_conflict() from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail={"code": "TASK_COMPLETION_FAILED", "message": "任务完成未保存，请重试"}) from exc
    db.refresh(task)
    statement = _suggestion_statement().where(
        AgentSuggestion.action_type == COMPLETE_TASK,
        AgentSuggestion.source_type == "task",
        AgentSuggestion.source_id == task_id,
        AgentSuggestion.source_navigation_key == task.navigation_key,
    )
    if payload is not None and payload.idempotency_key:
        statement = statement.where(AgentSuggestion.idempotency_key == payload.idempotency_key)
    completion = db.scalar(statement.order_by(AgentSuggestion.id.desc()))
    if completion is None or completion.receipt is None or completion.status != "executed":
        raise HTTPException(
            status_code=500,
            detail={"code": "TASK_COMPLETION_RECEIPT_MISSING", "message": "任务已处理，但未找到完成回执"},
        )
    return {"status": "executed", "task": task, "receipt": completion.receipt,
            "message": completion.receipt.message}


@router.post("/plan-deltas/{suggestion_id}/accept", response_model=AgentSuggestionRead)
def accept_plan_delta(
    suggestion_id: int, payload: AgentPlanDeltaAccept, db: Session = Depends(get_db)
) -> AgentSuggestion:
    winner = db.scalar(select(AgentSuggestion).where(AgentSuggestion.idempotency_key == payload.idempotency_key))
    if winner is not None and winner.id != suggestion_id:
        raise _conflict("IDEMPOTENCY_KEY_CONFLICT", "幂等键已用于另一条智能体建议")
    suggestion = db.scalar(_suggestion_statement().where(AgentSuggestion.id == suggestion_id))
    if suggestion is None or suggestion.action_type != APPLY_PLAN_DELTA:
        raise _not_found()
    if suggestion.status == "executed":
        return suggestion
    if suggestion.status != "pending":
        raise _conflict("SUGGESTION_NOT_PENDING", "该计划差异当前不能执行")
    now = utc_now()
    plan, task, changes = recompute_delta_is_current(db, suggestion)
    if plan is None or task is None or not changes or as_utc(suggestion.expires_at) <= now:
        suggestion.status = "expired"
        suggestion.updated_at = now
        db.add(AgentEvent(event_type="plan_delta_expired", suggestion_id=suggestion.id, entity_type="study_plan",
                          entity_id=suggestion.source_id, entity_navigation_key=suggestion.source_navigation_key, payload={"reason_code": "plan_or_task_snapshot_changed"}))
        db.commit()
        raise _conflict("PLAN_DELTA_EXPIRED", "计划或任务状态已变化，请重新查看差异")
    # Keep the already-validated identities stable until the action transaction
    # commits, including deletion/recreation between the snapshot read and write.
    check_edit_precondition(db, plan, f'"{plan.navigation_key}:{plan.revision}"')
    check_edit_precondition(db, task, f'"{task.navigation_key}:{task.revision}"')
    items, warnings, material_count, task_count = decode_plan_content(plan.plan_content)
    unscheduled_items = decode_plan_unscheduled_items(plan.plan_content)
    metadata = decode_plan_agent_metadata(plan.plan_content)
    protected = set(metadata["manual_item_ids"])
    by_id = {item.id: item for item in items}
    # This is intentionally repeated at execution time: no completed item,
    # explicit manual item, or baseline-mismatched item may be overwritten.
    for change in changes:
        current = by_id.get(change["item_id"])
        if (current is None or current.status in {"completed", "canceled"} or current.id in protected
                or metadata["baseline_items"].get(current.id) != current.model_dump(mode="json")
                or current.model_dump(mode="json") != change["before"]):
            suggestion.status = "expired"
            suggestion.updated_at = now
            db.add(AgentEvent(event_type="plan_delta_expired", suggestion_id=suggestion.id, entity_type="study_plan",
                              entity_id=plan.id, entity_navigation_key=plan.navigation_key, payload={"reason_code": "manual_or_completed_item_protected"}))
            db.commit()
            raise _conflict("PLAN_DELTA_EXPIRED", "计划项已被手动修改或完成，不能覆盖")
    before_payload = {"plan_id": plan.id, "plan_snapshot": plan_content_fingerprint(plan.plan_content),
                      "changes": [{"item_id": change["item_id"], "item": change["before"]} for change in changes]}
    for change in changes:
        by_id[change["item_id"]] = StudyPlanItem.model_validate(change["after"])
    metadata["adjustment_log"] = [*metadata["adjustment_log"], {
        "suggestion_id": suggestion.id, "trigger": suggestion.reason_code, "applied_at": now.isoformat(),
        "item_ids": [change["item_id"] for change in changes],
    }]
    plan.plan_content = encode_plan_content_with_metadata(
        list(by_id.values()), warnings, material_count=material_count, task_count=task_count, metadata=metadata,
        unscheduled_items=unscheduled_items,
    )
    after_payload = {"plan_id": plan.id, "plan_snapshot": plan_content_fingerprint(plan.plan_content),
                     "changes": [{"item_id": change["item_id"], "item": change["after"]} for change in changes]}
    try:
        suggestion.idempotency_key = payload.idempotency_key
        suggestion.status = "accepted"
        suggestion.accepted_at = now
        db.add(AgentEvent(event_type="plan_delta_accepted", suggestion_id=suggestion.id, entity_type="study_plan",
                          entity_id=plan.id, entity_navigation_key=plan.navigation_key, payload={"change_count": len(changes)}))
        db.flush()
        db.add(ActionReceipt(suggestion_id=suggestion.id, action_type=APPLY_PLAN_DELTA, source_type="study_plan",
                             source_id=plan.id, source_navigation_key=plan.navigation_key, outcome="executed", applied_payload={"changes": changes},
                             before_payload=before_payload, after_payload=after_payload,
                             message="计划差异已在未完成、未手工修改的计划项中应用", executed_at=now))
        suggestion.status = "executed"
        suggestion.executed_at = now
        db.add(AgentEvent(event_type="plan_delta_executed", suggestion_id=suggestion.id, entity_type="study_plan",
                          entity_id=plan.id, entity_navigation_key=plan.navigation_key, payload={"before": before_payload, "after": after_payload}))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        resolved = db.scalar(_suggestion_statement().where(AgentSuggestion.id == suggestion_id))
        if resolved is not None and resolved.status == "executed":
            return resolved
        raise _conflict("AGENT_EXECUTION_CONFLICT", "计划差异正在被另一请求处理，请重试") from exc
    except StaleDataError as exc:
        db.rollback()
        raise edit_conflict() from exc
    except SQLAlchemyError as exc:
        # The plan write and ActionReceipt share one transaction; a database
        # failure cannot leave a partially adjusted plan behind.
        db.rollback()
        raise HTTPException(status_code=500, detail={"code": "PLAN_DELTA_EXECUTION_FAILED", "message": "计划差异未保存，请重试"}) from exc
    return db.scalar(_suggestion_statement().where(AgentSuggestion.id == suggestion_id))


@router.post("/suggestions/{suggestion_id}/accept", response_model=AgentSuggestionRead)
def accept_suggestion(
    suggestion_id: int,
    payload: AgentSuggestionAccept,
    db: Session = Depends(get_db),
) -> AgentSuggestion:
    existing_key = db.scalar(
        select(AgentSuggestion).where(AgentSuggestion.idempotency_key == payload.idempotency_key)
    )
    if existing_key is not None and existing_key.id != suggestion_id:
        raise _conflict("IDEMPOTENCY_KEY_CONFLICT", "幂等键已用于另一条智能体建议")

    suggestion = db.scalar(_suggestion_statement().where(AgentSuggestion.id == suggestion_id))
    if suggestion is None:
        raise _not_found()
    if suggestion.status == "executed":
        return suggestion
    if suggestion.status != "pending":
        raise _conflict("SUGGESTION_NOT_PENDING", "该智能体建议当前不能执行")
    if suggestion.action_type not in (ADJUST_PRIORITY, SET_TASK_ESTIMATE, START_TASK):
        raise _conflict("UNSUPPORTED_AGENT_ACTION", "不支持的智能体动作")

    now = utc_now()
    task = db.get(Task, suggestion.source_id)
    if task is not None and task.navigation_key != suggestion.source_navigation_key:
        task = None
    if (
        task is None
        or not is_action_candidate(task, suggestion.action_type, now)
        or task_fingerprint(task, suggestion.action_type) != suggestion.fingerprint
        or as_utc(suggestion.expires_at) <= now
    ):
        suggestion.status = "expired"
        suggestion.updated_at = now
        db.add(
            AgentEvent(
                event_type="suggestion_expired",
                suggestion_id=suggestion.id,
                entity_type="task" if task is not None else None,
                entity_id=task.id if task is not None else None,
                entity_navigation_key=task.navigation_key if task is not None else None,
                payload={"reason_code": "source_state_changed"},
            )
        )
        db.commit()
        raise _conflict("SUGGESTION_EXPIRED", "任务状态已变化，建议已失效")

    check_edit_precondition(db, task, f'"{task.navigation_key}:{task.revision}"')
    if suggestion.action_type == ADJUST_PRIORITY:
        if payload.estimated_minutes is not None:
            raise _conflict("INVALID_AGENT_ACTION_INPUT", "该动作不接受预计时长")
        selected_payload = {"priority": payload.priority if payload.priority is not None else suggestion.proposed_payload["priority"]}
        message = "任务优先级已按确认建议更新"
    elif suggestion.action_type == SET_TASK_ESTIMATE:
        if payload.priority is not None or payload.estimated_minutes is None:
            raise _conflict("INVALID_AGENT_ACTION_INPUT", "补充预计时长时必须提供 15 至 10080 的整数分钟")
        selected_payload = {"estimated_minutes": payload.estimated_minutes, "remaining_minutes": payload.estimated_minutes}
        message = "任务预计时长和剩余时长已同步更新"
    else:
        if payload.priority is not None or payload.estimated_minutes is not None:
            raise _conflict("INVALID_AGENT_ACTION_INPUT", "开始任务不接受额外参数")
        selected_payload = {"status": "in_progress"}
        message = "任务已标记为进行中"
    before_payload = task_snapshot_payload(task)
    after_payload = {**before_payload, **selected_payload}
    try:
        suggestion.idempotency_key = payload.idempotency_key
        suggestion.status = "accepted"
        suggestion.accepted_at = now
        db.add(
            AgentEvent(
                event_type="suggestion_accepted",
                suggestion_id=suggestion.id,
                entity_type="task",
                entity_id=task.id,
                entity_navigation_key=task.navigation_key,
                payload=selected_payload,
            )
        )
        if suggestion.action_type == ADJUST_PRIORITY:
            task.priority = selected_payload["priority"]
        elif suggestion.action_type == SET_TASK_ESTIMATE:
            task.estimated_minutes = selected_payload["estimated_minutes"]
            task.remaining_minutes = selected_payload["remaining_minutes"]
        else:
            task.status = "in_progress"
        receipt = ActionReceipt(
            suggestion_id=suggestion.id,
            action_type=suggestion.action_type,
            source_type="task",
            source_id=task.id,
            source_navigation_key=task.navigation_key,
            outcome="executed",
            applied_payload=selected_payload,
            before_payload=before_payload,
            after_payload=after_payload,
            message=message,
            executed_at=now,
        )
        db.add(receipt)
        suggestion.status = "executed"
        suggestion.executed_at = now
        db.add(
            AgentEvent(
                event_type="suggestion_executed",
                suggestion_id=suggestion.id,
                entity_type="task",
                entity_id=task.id,
                entity_navigation_key=task.navigation_key,
                payload=selected_payload,
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        resolved_suggestion = db.scalar(_suggestion_statement().where(AgentSuggestion.id == suggestion_id))
        # A competing request may have committed after this request loaded the
        # pending row. Never overwrite that completed result as "failed".
        if resolved_suggestion is not None and resolved_suggestion.status == "executed":
            return resolved_suggestion
        key_winner = db.scalar(select(AgentSuggestion).where(AgentSuggestion.idempotency_key == payload.idempotency_key))
        if key_winner is not None and key_winner.id != suggestion_id:
            raise _conflict("IDEMPOTENCY_KEY_CONFLICT", "幂等键已用于另一条智能体建议") from exc
        # Integrity errors are normally concurrent receipt/idempotency races.
        # Their outcome is unknown to this request, so leave the suggestion
        # retryable rather than writing an incorrect terminal failure state.
        raise _conflict("AGENT_EXECUTION_CONFLICT", "建议正在被另一请求处理，请重试") from exc
    except StaleDataError as exc:
        db.rollback()
        raise edit_conflict() from exc
    except SQLAlchemyError as exc:
        db.rollback()
        # The action transaction is atomic: the Task mutation and receipt were
        # rolled back together. Persist a terminal failure only when the
        # database is still available for this separate bookkeeping write.
        failed_suggestion = db.scalar(_suggestion_statement().where(AgentSuggestion.id == suggestion_id))
        if failed_suggestion is not None:
            try:
                failed_suggestion.status = "failed"
                failed_suggestion.updated_at = now
                db.add(
                    AgentEvent(
                        event_type="suggestion_failed",
                        suggestion_id=failed_suggestion.id,
                        entity_type="task",
                        entity_id=failed_suggestion.source_id,
                        entity_navigation_key=failed_suggestion.source_navigation_key,
                        payload={"reason_code": "execution_failed"},
                    )
                )
                db.commit()
            except SQLAlchemyError:
                db.rollback()
        raise HTTPException(
            status_code=500,
            detail={"code": "AGENT_EXECUTION_FAILED", "message": "智能体建议执行失败，未修改任务"},
        ) from exc

    return db.scalar(_suggestion_statement().where(AgentSuggestion.id == suggestion.id))


@router.post("/suggestions/{suggestion_id}/dismiss", response_model=AgentSuggestionRead)
def dismiss_suggestion(
    suggestion_id: int,
    payload: AgentSuggestionDismiss,
    db: Session = Depends(get_db),
) -> AgentSuggestion:
    suggestion = db.scalar(_suggestion_statement().where(AgentSuggestion.id == suggestion_id))
    if suggestion is None:
        raise _not_found()
    if suggestion.status != "pending":
        raise _conflict("SUGGESTION_NOT_PENDING", "该智能体建议当前不能忽略")
    now = utc_now()
    if as_utc(suggestion.expires_at) <= now:
        suggestion.status = "expired"
        suggestion.updated_at = now
        db.add(
            AgentEvent(
                event_type="suggestion_expired",
                suggestion_id=suggestion.id,
                entity_type="task",
                entity_id=suggestion.source_id, entity_navigation_key=suggestion.source_navigation_key,
                payload={"reason_code": "suggestion_expired"},
            )
        )
        db.commit()
        raise _conflict("SUGGESTION_EXPIRED", "建议已过期，不能忽略")
    suggestion.status = "dismissed"
    suggestion.dismissed_at = now
    suggestion.dismissal_reason = payload.reason
    db.add(
        AgentEvent(
            event_type="suggestion_dismissed",
            suggestion_id=suggestion.id,
            entity_type="task",
            entity_id=suggestion.source_id, entity_navigation_key=suggestion.source_navigation_key,
            payload={"reason": payload.reason},
        )
    )
    db.commit()
    return db.scalar(_suggestion_statement().where(AgentSuggestion.id == suggestion_id))
