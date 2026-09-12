from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.utils import commit_or_rollback, require_entity
from app.database import get_db
from app.models.course import Course
from app.models.material import Material
from app.models.study_plan import StudyPlan
from app.models.task import Task
from app.schemas.study_plan import StudyPlanGenerate, StudyPlanItem, StudyPlanRead, StudyPlanUpdate
from app.services.study_plan import (
    decode_plan_agent_metadata,
    decode_plan_content,
    decode_plan_unscheduled_items,
    encode_plan_content,
    encode_plan_content_with_metadata,
    generate_review_schedule,
)
from app.services.agent_feedback import calibration_payload
from app.services.edit_concurrency import check_edit_precondition
from app.services.source_identity import new_navigation_key
from app.time import as_local, utc_now

router = APIRouter(prefix="/api/study-plans", tags=["study-plans"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "STUDY_PLAN_NOT_FOUND", "message": "复习计划不存在"})


def _invalid_plan(message: str, *, code: str = "INVALID_STUDY_PLAN") -> HTTPException:
    return HTTPException(status_code=422, detail={"code": code, "message": message})


def _read_payload(plan: StudyPlan) -> StudyPlanRead:
    items, warnings, material_count, task_count = decode_plan_content(plan.plan_content)
    unscheduled_items = decode_plan_unscheduled_items(plan.plan_content)
    completed_items = [item for item in items if item.status == "completed"]
    return StudyPlanRead(
        id=plan.id,
        navigation_key=plan.navigation_key,
        revision=plan.revision,
        course_id=plan.course_id,
        title=plan.title,
        exam_date=plan.exam_date,
        daily_minutes=plan.daily_minutes,
        plan_content=plan.plan_content,
        status=plan.status,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        items=items,
        warnings=warnings,
        unscheduled_items=unscheduled_items,
        material_count=material_count,
        task_count=task_count,
        completed_item_count=len(completed_items),
        total_minutes=sum(item.minutes for item in items),
        completed_minutes=sum(item.minutes for item in completed_items),
    )


def _validate_item_dates(items: list[StudyPlanItem], exam_date: date | None) -> None:
    if exam_date is None:
        raise _invalid_plan("计划必须设置考试日期")
    invalid = next((item for item in items if item.date > exam_date), None)
    if invalid is not None:
        raise _invalid_plan(
            f"计划项“{invalid.title}”的日期不能超过考试日期 {exam_date.isoformat()}",
            code="PLAN_DATE_AFTER_EXAM",
        )


@router.get("", response_model=list[StudyPlanRead])
def list_study_plans(
    course_id: int | None = Query(default=None),
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[StudyPlanRead]:
    statement = select(StudyPlan).order_by(StudyPlan.updated_at.desc())
    if course_id is not None:
        statement = statement.where(StudyPlan.course_id == course_id)
    if not include_archived:
        statement = statement.where(StudyPlan.status != "archived")
    return [_read_payload(plan) for plan in db.scalars(statement).all()]


@router.post("/generate", response_model=StudyPlanRead, status_code=status.HTTP_201_CREATED)
def generate_study_plan(payload: StudyPlanGenerate, db: Session = Depends(get_db)) -> StudyPlanRead:
    course = require_entity(
        db,
        Course,
        payload.course_id,
        code="COURSE_NOT_FOUND",
        message="关联课程不存在",
    )
    evaluated_at = utc_now()
    start_date = as_local(evaluated_at).date()
    if payload.exam_date < start_date:
        raise _invalid_plan("考试日期不能早于今天", code="EXAM_DATE_IN_PAST")

    materials = list(
        db.scalars(
            select(Material)
            .where(Material.course_id == payload.course_id)
            .order_by(Material.created_at.asc())
        ).all()
    )
    tasks = list(
        db.scalars(
            select(Task)
            .where(Task.course_id == payload.course_id)
            .order_by(Task.due_at.asc(), Task.created_at.asc())
        ).all()
    )
    try:
        calibration_factor = calibration_payload(db, payload.course_id)["factor"]
        items, warnings, unscheduled_items = generate_review_schedule(
            # This is the explicit per-plan review ceiling supplied by the
            # student. Shared preference capacity and timetable occupancy are
            # separate inputs and are not deducted a second time here.
            start_date=start_date,
            exam_date=payload.exam_date,
            daily_minutes=payload.daily_minutes,
            materials=materials,
            tasks=tasks,
            calibration_factor=calibration_factor,
            evaluated_at=evaluated_at,
        )
    except ValueError as error:
        raise _invalid_plan(str(error), code="PLAN_RANGE_TOO_LARGE") from error

    plan = StudyPlan(
        course_id=course.id if course else payload.course_id,
        title=payload.title or f"{course.name if course else '课程'}复习计划",
        exam_date=payload.exam_date,
        daily_minutes=payload.daily_minutes,
        plan_content=encode_plan_content(
            items,
            warnings,
            material_count=len(materials),
            task_count=len([task for task in tasks if task.status not in {"completed", "canceled"}]),
            unscheduled_items=unscheduled_items,
        ),
        status="active",
    )
    db.add(plan)
    commit_or_rollback(db)
    db.refresh(plan)
    return _read_payload(plan)


@router.get("/{plan_id}", response_model=StudyPlanRead)
def get_study_plan(plan_id: int, db: Session = Depends(get_db)) -> StudyPlanRead:
    plan = db.get(StudyPlan, plan_id)
    if plan is None:
        raise _not_found()
    return _read_payload(plan)


@router.post("/{plan_id}/archive", response_model=StudyPlanRead)
def archive_study_plan(
    plan_id: int,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> StudyPlanRead:
    plan = db.get(StudyPlan, plan_id)
    if plan is None:
        raise _not_found()
    check_edit_precondition(db, plan, if_match)
    plan.status = "archived"
    commit_or_rollback(db)
    db.refresh(plan)
    return _read_payload(plan)


@router.patch("/{plan_id}", response_model=StudyPlanRead)
def update_study_plan(
    plan_id: int,
    payload: StudyPlanUpdate,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> StudyPlanRead:
    plan = db.get(StudyPlan, plan_id)
    if plan is None:
        raise _not_found()

    check_edit_precondition(db, plan, if_match)
    current_items, warnings, material_count, task_count = decode_plan_content(plan.plan_content)
    unscheduled_items = decode_plan_unscheduled_items(plan.plan_content)
    metadata = decode_plan_agent_metadata(plan.plan_content)
    changed_fields = payload.model_fields_set
    target_exam_date = payload.exam_date if "exam_date" in changed_fields else plan.exam_date
    items = payload.items if "items" in changed_fields and payload.items is not None else current_items
    if len({item.id for item in items}) != len(items):
        raise _invalid_plan("计划项编号不能重复", code="DUPLICATE_PLAN_ITEM_ID")
    if "items" in changed_fields and payload.items is not None:
        saved_by_id = {item.id: item for item in current_items}
        for item in items:
            saved = saved_by_id.get(item.id)
            # Identity and evidence come from saved server state, not editable
            # request JSON. Re-added IDs receive a new generation.
            item.navigation_key = saved.navigation_key if saved and saved.navigation_key else new_navigation_key()
            item.source_material_refs = [ref for ref in saved.source_material_refs if ref.source_id in item.source_material_ids] if saved else []
            item.source_task_refs = [ref for ref in saved.source_task_refs if ref.source_id in item.source_task_ids] if saved else []
    _validate_item_dates(items, target_exam_date)

    if "title" in changed_fields and payload.title is not None:
        plan.title = payload.title
    if "exam_date" in changed_fields and payload.exam_date is not None:
        plan.exam_date = payload.exam_date
    if "daily_minutes" in changed_fields and payload.daily_minutes is not None:
        plan.daily_minutes = payload.daily_minutes
    if "status" in changed_fields and payload.status is not None:
        plan.status = payload.status
    if "items" in changed_fields and payload.items is not None:
        # Mark an item as manual only from an explicit baseline comparison. Old
        # v1 plans have no baseline, therefore every item is conservatively
        # protected from agent plan deltas rather than guessed as generated.
        baseline = metadata["baseline_items"]
        protected = set(metadata["manual_item_ids"])
        for item in payload.items:
            baseline_item = baseline.get(item.id)
            if baseline_item is None or baseline_item != item.model_dump(mode="json"):
                protected.add(item.id)
        metadata["manual_item_ids"] = sorted(protected)
        plan.plan_content = encode_plan_content_with_metadata(
            items,
            warnings,
            material_count=material_count,
            task_count=task_count,
            metadata=metadata,
            unscheduled_items=unscheduled_items,
        )

    commit_or_rollback(db)
    db.refresh(plan)
    return _read_payload(plan)
