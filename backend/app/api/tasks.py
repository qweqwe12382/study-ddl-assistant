from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.utils import commit_or_rollback, flush_or_rollback, require_entity
from app.models.course import Course
from app.models.material import Material
from app.models.agent import AgentEvent
from app.models.task import Task
from app.schemas.agent import TaskCompletionFeedback
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.services.agent_feedback import (
    complete_task_with_feedback,
    create_plan_delta_candidates,
    task_feedback_snapshot,
)
from app.services.edit_concurrency import check_edit_precondition, edit_conflict
from app.services.task_service import sync_overdue_tasks

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "任务不存在"})


def _validate_duration_pair(estimated_minutes: int | None, remaining_minutes: int | None, *, status: str) -> None:
    if remaining_minutes is not None and estimated_minutes is None and status != "completed":
        raise HTTPException(
            status_code=422,
            detail={"code": "TASK_DURATION_INVALID", "message": "填写剩余时长前必须先填写预计时长"},
        )
    if estimated_minutes is not None and remaining_minutes is not None and remaining_minutes > estimated_minutes:
        raise HTTPException(
            status_code=422,
            detail={"code": "TASK_DURATION_INVALID", "message": "剩余时长不能超过预计时长"},
        )


@router.get("", response_model=list[TaskRead])
def list_tasks(db: Session = Depends(get_db)) -> list[Task]:
    sync_overdue_tasks(db)
    return list(db.scalars(select(Task).order_by(Task.due_at.asc(), Task.created_at.desc())).all())


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)) -> Task:
    require_entity(
        db,
        Course,
        payload.course_id,
        code="COURSE_NOT_FOUND",
        message="关联课程不存在",
    )
    material = require_entity(
        db,
        Material,
        payload.material_id,
        code="MATERIAL_NOT_FOUND",
        message="关联资料不存在",
    )
    task_data = payload.model_dump()
    if task_data["status"] == "completed":
        task_data["remaining_minutes"] = 0
    task = Task(**task_data, source_material_name=material.original_filename if material else None)
    db.add(task)
    db.flush()
    create_plan_delta_candidates(db, task, "task_created")
    commit_or_rollback(db)
    db.refresh(task)
    return task


@router.post("/{task_id}/complete", response_model=TaskRead)
def complete_task(
    task_id: int,
    payload: TaskCompletionFeedback | None = Body(default=None),
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise _not_found()
    check_edit_precondition(db, task, if_match)
    try:
        complete_task_with_feedback(
            db, task,
            actual_minutes=payload.actual_minutes if payload else None,
            difficulty=payload.difficulty if payload else None,
            idempotency_key=payload.idempotency_key if payload else None,
        )
        commit_or_rollback(db)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": str(exc), "message": "幂等键已用于其他操作"}) from exc
    except StaleDataError as exc:
        db.rollback()
        raise edit_conflict() from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail={"code": "TASK_COMPLETION_FAILED", "message": "任务完成未保存，请重试"}) from exc
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    sync_overdue_tasks(db)
    task = db.get(Task, task_id)
    if task is None:
        raise _not_found()
    return task


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise _not_found()
    changes = payload.model_dump(exclude_unset=True)
    require_entity(
        db,
        Course,
        changes.get("course_id"),
        code="COURSE_NOT_FOUND",
        message="关联课程不存在",
    )
    material = require_entity(
        db,
        Material,
        changes.get("material_id"),
        code="MATERIAL_NOT_FOUND",
        message="关联资料不存在",
    )
    target_status = changes.get("status", task.status)
    target_estimated = changes.get("estimated_minutes", task.estimated_minutes)
    target_remaining = 0 if target_status == "completed" else changes.get("remaining_minutes", task.remaining_minutes)
    _validate_duration_pair(target_estimated, target_remaining, status=target_status)
    check_edit_precondition(db, task, if_match)
    if "material_id" in changes and changes["material_id"] is not None:
        task.source_material_name = material.original_filename if material else None
    before_actual = task.actual_minutes
    before_status = task.status
    for field, value in changes.items():
        setattr(task, field, value)
    if target_status == "completed":
        task.remaining_minutes = 0
        if before_status != "completed":
            from app.time import utc_now
            task.completed_at = utc_now()
    flush_or_rollback(db)
    if before_status != "completed" and task.status == "completed":
        db.add(AgentEvent(
            event_type="task_completed",
            entity_type="task",
            entity_id=task.id,
            entity_navigation_key=task.navigation_key,
            payload={"completion_path": "task_update", "after": task_feedback_snapshot(task)},
        ))
        create_plan_delta_candidates(db, task, "task_completed")
    if "actual_minutes" in changes and before_actual != task.actual_minutes:
        create_plan_delta_candidates(db, task, "actual_minutes_changed")
    if task.status == "overdue" and before_status != "overdue":
        create_plan_delta_candidates(db, task, "task_overdue")
    commit_or_rollback(db)
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> None:
    task = db.get(Task, task_id)
    if task is None:
        raise _not_found()
    check_edit_precondition(db, task, if_match)
    db.delete(task)
    commit_or_rollback(db)
