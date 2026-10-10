from datetime import datetime, time
import hashlib
import re

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.utils import commit_or_rollback, require_entity
from app.database import get_db
from app.models.academic_calendar import AcademicCalendarSyncLink, ClassSession, Exam
from app.models.course import Course
from app.models.user import User
from app.schemas.academic_calendar import (
    AcademicCalendarOverview,
    ClassSessionCreate,
    ClassSessionRead,
    ClassSessionUpdate,
    ExamCreate,
    ExamRead,
    ExamUpdate,
    has_active_class_week,
)
from app.schemas.academic_calendar_sync import (
    AcademicCalendarImportItem,
    AcademicCalendarPreviewRequest,
    AcademicCalendarPreviewResponse,
    AcademicCalendarSyncConflict,
    AcademicCalendarSyncRequest,
    AcademicCalendarSyncResponse,
    NjustAcademicPreviewRequest,
    NjustCaptchaResponse,
)
from app.services.academic_calendar_sync import (
    AcademicCalendarImportError,
    class_payload,
    exam_payload,
    parse_ical_calendar,
    payload_hash,
    source_key as expected_source_key,
)
from app.services.edit_concurrency import check_edit_precondition
from app.services.auth import get_current_user
from app.services.njust_academic import (
    NjustAcademicError,
    SESSION_TTL_SECONDS,
    fetch_njust_pages,
    njust_session_store,
    normalize_njust_calendar,
)
from app.time import as_utc, deadline_to_utc, utc_now


router = APIRouter(prefix="/api/academic-calendar", tags=["academic-calendar"])


def _class_not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "CLASS_SESSION_NOT_FOUND", "message": "课表记录不存在"},
    )


def _exam_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "EXAM_NOT_FOUND", "message": "考试记录不存在"})


def _week_matches(week: int, pattern: str) -> bool:
    return pattern == "all" or (pattern == "odd" and week % 2 == 1) or (pattern == "even" and week % 2 == 0)


def _patterns_share_week(start_week: int, end_week: int, first: str, second: str) -> bool:
    return any(_week_matches(week, first) and _week_matches(week, second) for week in range(start_week, end_week + 1))


def _ensure_class_values(start_time: time, end_time: time, start_week: int, end_week: int, week_pattern: str) -> None:
    if end_time <= start_time:
        raise HTTPException(
            status_code=422,
            detail={"code": "CLASS_TIME_INVALID", "message": "下课时间必须晚于上课时间"},
        )
    if end_week < start_week:
        raise HTTPException(
            status_code=422,
            detail={"code": "CLASS_WEEK_RANGE_INVALID", "message": "结束周不能早于开始周"},
        )
    if not has_active_class_week(start_week, end_week, week_pattern):
        raise HTTPException(
            status_code=422,
            detail={"code": "CLASS_WEEK_PATTERN_EMPTY", "message": "周次范围与单双周不匹配，至少需要一个实际上课周"},
        )


def _ensure_no_class_conflict(
    db: Session,
    *,
    weekday: int,
    start_time: time,
    end_time: time,
    start_week: int,
    end_week: int,
    week_pattern: str,
    exclude_id: int | None = None,
) -> None:
    existing = db.scalars(select(ClassSession).where(ClassSession.weekday == weekday)).all()
    for item in existing:
        if exclude_id is not None and item.id == exclude_id:
            continue
        shared_start = max(start_week, item.start_week)
        shared_end = min(end_week, item.end_week)
        if shared_start > shared_end:
            continue
        if not _patterns_share_week(shared_start, shared_end, week_pattern, item.week_pattern):
            continue
        if start_time < item.end_time and end_time > item.start_time:
            raise HTTPException(
                status_code=409,
                detail={"code": "CLASS_SESSION_CONFLICT", "message": "这段时间已有课程，请调整星期、周次或时间"},
            )


def _ensure_exam_values(starts_at: datetime, ends_at: datetime | None) -> None:
    if ends_at is not None and as_utc(ends_at) <= as_utc(starts_at):
        raise HTTPException(
            status_code=422,
            detail={"code": "EXAM_TIME_INVALID", "message": "考试结束时间必须晚于开始时间"},
        )


def _reject_cleared_required_fields(changes: dict, fields: tuple[str, ...]) -> None:
    if any(field in changes and changes[field] is None for field in fields):
        raise HTTPException(
            status_code=422,
            detail={"code": "REQUIRED_FIELD_MISSING", "message": "必填字段不能清空"},
        )


def _list_classes(db: Session, week: int) -> list[ClassSession]:
    rows = db.scalars(
        select(ClassSession).order_by(ClassSession.weekday.asc(), ClassSession.start_time.asc())
    ).all()
    return [
        item
        for item in rows
        if item.start_week <= week <= item.end_week and _week_matches(week, item.week_pattern)
    ]


def _list_exams(db: Session, include_past: bool) -> list[Exam]:
    rows = list(db.scalars(select(Exam).order_by(Exam.starts_at.asc(), Exam.created_at.asc())).all())
    if include_past:
        return rows
    now = utc_now()
    return [item for item in rows if as_utc(item.ends_at or item.starts_at) >= now]


def _course_color(name: str) -> str:
    palette = ("#3157e6", "#168b7a", "#b96b25", "#7555c7", "#b5445c", "#3d7f52")
    return palette[int(hashlib.sha256(name.casefold().encode("utf-8")).hexdigest()[:8], 16) % len(palette)]


def _find_course(db: Session, name: str) -> Course | None:
    normalized = name.strip().casefold()
    return next((course for course in db.scalars(select(Course)).all() if course.name.casefold() == normalized), None)


def _get_or_create_course(db: Session, name: str, teacher: str | None = None) -> tuple[Course, bool]:
    course = _find_course(db, name)
    if course is not None:
        if teacher and not course.teacher:
            course.teacher = teacher
        return course, False
    course = Course(name=name.strip(), teacher=teacher, color=_course_color(name))
    db.add(course)
    db.flush()
    return course, True


def _import_payload(item: AcademicCalendarImportItem) -> dict:
    return class_payload(item, item.course_name) if item.kind == "class_session" else exam_payload(item, item.course_name)


def _sync_conflict(item: AcademicCalendarImportItem, reason: str, message: str) -> AcademicCalendarSyncConflict:
    return AcademicCalendarSyncConflict(
        item_key=item.item_key,
        course_name=item.course_name,
        reason=reason,
        message=message,
    )


def _linked_entity(db: Session, link: AcademicCalendarSyncLink):
    model = ClassSession if link.entity_type == "class_session" else Exam
    return db.scalar(select(model).where(model.navigation_key == link.entity_navigation_key))


def _current_payload(entity, kind: str) -> dict:
    return class_payload(entity, entity.course_name) if kind == "class_session" else exam_payload(entity, entity.course_name)


def _apply_import_item(entity, item: AcademicCalendarImportItem, course_id: int) -> None:
    entity.course_id = course_id
    if item.kind == "class_session":
        for field in ("weekday", "start_time", "end_time", "location", "start_week", "end_week", "week_pattern", "note"):
            setattr(entity, field, getattr(item, field))
        return
    for field in ("title", "exam_type", "location", "seat_number", "note"):
        setattr(entity, field, getattr(item, field))
    entity.starts_at = deadline_to_utc(item.starts_at)
    entity.ends_at = deadline_to_utc(item.ends_at) if item.ends_at is not None else None


def _validated_preview_items(items: list[dict], warnings: list[str]) -> list[AcademicCalendarImportItem]:
    parsed = []
    for item in items:
        try:
            parsed.append(AcademicCalendarImportItem.model_validate(item))
        except ValidationError:
            # A malformed upstream row must not hide otherwise usable rows or
            # expose a model-validation exception as a server error.
            name = str(item.get("course_name") or "未命名日程")[:120]
            warnings.append(f"{name}：时间或周次信息不完整，未导入，请核对后手工录入")
    return parsed


def _recurrence_group(external_uid: str) -> str | None:
    match = re.fullmatch(r"(.+:weekday:[1-7])(?::s[0-9]+)?", external_uid)
    return match.group(1) if match else None


def _changed_recurrence_groups(db: Session, payload: AcademicCalendarSyncRequest) -> set[str]:
    """Do not leave stale split ranges behind when an exclusion list changes.

    Sync deliberately never deletes local rows. A changed partition therefore
    needs an explicit local review instead of partially updating its siblings.
    Ordinary metadata changes and repeated imports of the same partition work
    through the existing identity/concurrency checks.
    """
    incoming: dict[str, list] = {}
    for item in payload.items:
        group = _recurrence_group(item.external_uid) if item.kind == "class_session" else None
        if group:
            incoming.setdefault(group, []).append(item)
    if not incoming:
        return set()
    previous: dict[str, list] = {}
    links = db.scalars(select(AcademicCalendarSyncLink).where(
        AcademicCalendarSyncLink.source_key == payload.source_key,
        AcademicCalendarSyncLink.entity_type == "class_session",
    )).all()
    for link in links:
        group = _recurrence_group(link.external_uid)
        if group not in incoming:
            continue
        entity = _linked_entity(db, link)
        if entity is not None:
            previous.setdefault(group, []).append(entity)

    def shape(items):
        return sorted((item.start_week, item.end_week, item.week_pattern) for item in items)

    return {
        group for group, items in incoming.items()
        if previous.get(group)
        and (len(items) > 1 or len(previous[group]) > 1)
        and shape(items) != shape(previous[group])
    }


@router.get("/overview", response_model=AcademicCalendarOverview)
def overview(
    week: int = Query(default=1, ge=1, le=30),
    include_past_exams: bool = False,
    db: Session = Depends(get_db),
) -> AcademicCalendarOverview:
    return AcademicCalendarOverview(
        week=week,
        class_sessions=_list_classes(db, week),
        exams=_list_exams(db, include_past_exams),
    )


@router.post("/integrations/preview", response_model=AcademicCalendarPreviewResponse)
def preview_academic_calendar_import(payload: AcademicCalendarPreviewRequest) -> AcademicCalendarPreviewResponse:
    try:
        source_key, items, warnings = parse_ical_calendar(
            calendar_text=payload.calendar_text,
            source_name=payload.source_name,
            semester_start=payload.semester_start,
            semester_weeks=payload.semester_weeks,
        )
    except AcademicCalendarImportError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message}) from exc
    parsed = _validated_preview_items(items, warnings)
    return AcademicCalendarPreviewResponse(
        source_key=source_key,
        source_type=payload.source_type,
        source_name=payload.source_name,
        items=parsed,
        class_count=sum(item.kind == "class_session" for item in parsed),
        exam_count=sum(item.kind == "exam" for item in parsed),
        warnings=warnings,
    )


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"


def _raise_njust_error(exc: NjustAcademicError) -> None:
    raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from None


@router.post("/integrations/njust/captcha", response_model=NjustCaptchaResponse)
def create_njust_captcha(
    response: Response,
    current_user: User = Depends(get_current_user),
) -> NjustCaptchaResponse:
    _no_store(response)
    try:
        session_id, image_data_uri = njust_session_store.create(current_user.workspace_key)
    except NjustAcademicError as exc:
        _raise_njust_error(exc)
    return NjustCaptchaResponse(
        session_id=session_id,
        image_data_uri=image_data_uri,
        expires_in_seconds=SESSION_TTL_SECONDS,
        transport_warning="南理工旧教务接口使用 HTTP；仅建议在可信校园网或学校 VPN 中使用。",
    )


@router.delete("/integrations/njust/session/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def discard_njust_session(
    session_id: str,
    response: Response,
    current_user: User = Depends(get_current_user),
) -> None:
    _no_store(response)
    njust_session_store.discard(session_id, current_user.workspace_key)


@router.post("/integrations/njust/preview", response_model=AcademicCalendarPreviewResponse)
def preview_njust_academic_calendar(
    payload: NjustAcademicPreviewRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
) -> AcademicCalendarPreviewResponse:
    _no_store(response)
    try:
        session, strategy = njust_session_store.consume(payload.session_id, current_user.workspace_key)
    except NjustAcademicError as exc:
        _raise_njust_error(exc)

    password = payload.password.get_secret_value()
    try:
        schedule_html, exams_html = fetch_njust_pages(
            session,
            strategy=strategy,
            username=payload.username,
            password=password,
            captcha=payload.captcha,
            term=payload.term,
        )
        source_key, source_name, items, warnings = normalize_njust_calendar(
            schedule_html=schedule_html,
            exams_html=exams_html,
            term=payload.term,
            semester_start=payload.semester_start,
            semester_weeks=payload.semester_weeks,
        )
    except NjustAcademicError as exc:
        _raise_njust_error(exc)
    finally:
        session.close()
        del password

    parsed = _validated_preview_items(items, warnings)
    return AcademicCalendarPreviewResponse(
        source_key=source_key,
        source_type="ical",
        source_name=source_name,
        credential_policy="ephemeral_memory",
        items=parsed,
        class_count=sum(item.kind == "class_session" for item in parsed),
        exam_count=sum(item.kind == "exam" for item in parsed),
        warnings=warnings,
    )


@router.post("/integrations/sync", response_model=AcademicCalendarSyncResponse)
def sync_academic_calendar_import(
    payload: AcademicCalendarSyncRequest, db: Session = Depends(get_db)
) -> AcademicCalendarSyncResponse:
    if payload.source_key != expected_source_key(payload.source_type, payload.source_name):
        raise HTTPException(
            status_code=422,
            detail={"code": "CALENDAR_SOURCE_MISMATCH", "message": "教务来源标识与预览不一致，请重新预览"},
        )

    created = updated = unchanged = skipped = removed = courses_created = 0
    conflicts: list[AcademicCalendarSyncConflict] = []
    seen_external: set[tuple[str, str]] = set()
    if payload.replace_source:
        # WakeUp-style full replace: the import becomes the whole schedule.
        # Every previous session/exam — imported from any source or entered
        # by hand — is cleared first; real timetables do overlap (labs and
        # internships run alongside regular classes), so imports are never
        # blocked on time conflicts either.
        for link in db.scalars(select(AcademicCalendarSyncLink)).all():
            db.delete(link)
        for entity in db.scalars(select(ClassSession)).all():
            db.delete(entity)
            removed += 1
        for entity in db.scalars(select(Exam)).all():
            db.delete(entity)
            removed += 1
        db.flush()
    changed_groups = set() if payload.replace_source else _changed_recurrence_groups(db, payload)
    for item in payload.items:
        if _recurrence_group(item.external_uid) in changed_groups:
            skipped += 1
            conflicts.append(_sync_conflict(
                item, "recurrence_changed",
                "课程的分段周次与本地记录不一致，请选齐同源区间，或先核对并手工移除旧记录；本次未改写这组课程",
            ))
            continue
        external_identity = (item.kind, item.external_uid)
        if external_identity in seen_external:
            skipped += 1
            conflicts.append(_sync_conflict(item, "target_unavailable", "同一预览项重复出现，已跳过"))
            continue
        seen_external.add(external_identity)
        remote_payload = _import_payload(item)
        remote_hash = payload_hash(remote_payload)
        link = db.scalar(
            select(AcademicCalendarSyncLink).where(
                AcademicCalendarSyncLink.source_key == payload.source_key,
                AcademicCalendarSyncLink.external_uid == item.external_uid,
                AcademicCalendarSyncLink.entity_type == item.kind,
            )
        )

        if link is not None:
            entity = _linked_entity(db, link)
            if entity is None:
                if not payload.replace_source:
                    skipped += 1
                    conflicts.append(
                        _sync_conflict(item, "target_unavailable", "对应的本地日程已删除，本次不会自动恢复")
                    )
                    continue
                db.delete(link)
                db.flush()
                link = None
            else:
                if not payload.replace_source and payload_hash(_current_payload(entity, item.kind)) != link.applied_hash:
                    skipped += 1
                    conflicts.append(
                        _sync_conflict(item, "local_changed", "本地内容在上次同步后修改过，请保留本地内容或重新录入")
                    )
                    continue
                if remote_hash == link.applied_hash:
                    unchanged += 1
                    continue
                # Imported timetables are factual data and may legitimately
                # overlap (labs/internships alongside classes), so updates
                # are never blocked on time conflicts; the weekly grid shows
                # overlapping blocks side by side.
                course, was_created = _get_or_create_course(db, item.course_name, item.teacher)
                courses_created += int(was_created)
                _apply_import_item(entity, item, course.id)
                link.applied_hash = remote_hash
                link.source_name = payload.source_name
                updated += 1
                continue

        # Create path likewise accepts overlapping imports without conflict
        # checks; only hand-entered sessions are guarded against clashes.
        course, was_created = _get_or_create_course(db, item.course_name, item.teacher)
        courses_created += int(was_created)
        if item.kind == "class_session":
            entity = ClassSession(course_id=course.id)
        else:
            entity = Exam(course_id=course.id)
        _apply_import_item(entity, item, course.id)
        db.add(entity)
        db.flush()
        db.add(
            AcademicCalendarSyncLink(
                source_key=payload.source_key,
                source_name=payload.source_name,
                source_type=payload.source_type,
                external_uid=item.external_uid,
                entity_type=item.kind,
                entity_navigation_key=entity.navigation_key,
                applied_hash=remote_hash,
            )
        )
        created += 1

    commit_or_rollback(db)
    return AcademicCalendarSyncResponse(
        created=created,
        updated=updated,
        unchanged=unchanged,
        skipped=skipped,
        removed=removed,
        courses_created=courses_created,
        conflicts=conflicts,
    )


@router.get("/class-sessions", response_model=list[ClassSessionRead])
def list_class_sessions(
    week: int = Query(default=1, ge=1, le=30), db: Session = Depends(get_db)
) -> list[ClassSession]:
    return _list_classes(db, week)


@router.post("/class-sessions", response_model=ClassSessionRead, status_code=status.HTTP_201_CREATED)
def create_class_session(payload: ClassSessionCreate, db: Session = Depends(get_db)) -> ClassSession:
    require_entity(db, Course, payload.course_id, code="COURSE_NOT_FOUND", message="关联课程不存在")
    _ensure_no_class_conflict(db, **payload.model_dump(exclude={"course_id", "location", "note"}))
    item = ClassSession(**payload.model_dump())
    db.add(item)
    commit_or_rollback(db)
    db.refresh(item)
    return item


@router.patch("/class-sessions/{session_id}", response_model=ClassSessionRead)
def update_class_session(
    session_id: int,
    payload: ClassSessionUpdate,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> ClassSession:
    item = db.get(ClassSession, session_id)
    if item is None:
        raise _class_not_found()
    changes = payload.model_dump(exclude_unset=True)
    _reject_cleared_required_fields(
        changes,
        ("course_id", "weekday", "start_time", "end_time", "start_week", "end_week", "week_pattern"),
    )
    course_id = changes.get("course_id", item.course_id)
    require_entity(db, Course, course_id, code="COURSE_NOT_FOUND", message="关联课程不存在")
    values = {
        "weekday": changes.get("weekday", item.weekday),
        "start_time": changes.get("start_time", item.start_time),
        "end_time": changes.get("end_time", item.end_time),
        "start_week": changes.get("start_week", item.start_week),
        "end_week": changes.get("end_week", item.end_week),
        "week_pattern": changes.get("week_pattern", item.week_pattern),
    }
    _ensure_class_values(values["start_time"], values["end_time"], values["start_week"], values["end_week"], values["week_pattern"])
    _ensure_no_class_conflict(db, **values, exclude_id=item.id)
    check_edit_precondition(db, item, if_match)
    for field, value in changes.items():
        setattr(item, field, value)
    commit_or_rollback(db)
    db.refresh(item)
    return item


@router.delete("/class-sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class_session(
    session_id: int,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> None:
    item = db.get(ClassSession, session_id)
    if item is None:
        raise _class_not_found()
    check_edit_precondition(db, item, if_match)
    db.delete(item)
    commit_or_rollback(db)


@router.get("/exams", response_model=list[ExamRead])
def list_exams(include_past: bool = False, db: Session = Depends(get_db)) -> list[Exam]:
    return _list_exams(db, include_past)


@router.post("/exams", response_model=ExamRead, status_code=status.HTTP_201_CREATED)
def create_exam(payload: ExamCreate, db: Session = Depends(get_db)) -> Exam:
    require_entity(db, Course, payload.course_id, code="COURSE_NOT_FOUND", message="关联课程不存在")
    item = Exam(**payload.model_dump())
    db.add(item)
    commit_or_rollback(db)
    db.refresh(item)
    return item


@router.patch("/exams/{exam_id}", response_model=ExamRead)
def update_exam(
    exam_id: int,
    payload: ExamUpdate,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> Exam:
    item = db.get(Exam, exam_id)
    if item is None:
        raise _exam_not_found()
    changes = payload.model_dump(exclude_unset=True)
    _reject_cleared_required_fields(changes, ("course_id", "title", "exam_type", "starts_at"))
    course_id = changes.get("course_id", item.course_id)
    require_entity(db, Course, course_id, code="COURSE_NOT_FOUND", message="关联课程不存在")
    starts_at = changes.get("starts_at", item.starts_at)
    ends_at = changes.get("ends_at", item.ends_at)
    _ensure_exam_values(starts_at, ends_at)
    check_edit_precondition(db, item, if_match)
    for field, value in changes.items():
        setattr(item, field, value)
    commit_or_rollback(db)
    db.refresh(item)
    return item


@router.delete("/exams/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exam(
    exam_id: int,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> None:
    item = db.get(Exam, exam_id)
    if item is None:
        raise _exam_not_found()
    check_edit_precondition(db, item, if_match)
    db.delete(item)
    commit_or_rollback(db)
