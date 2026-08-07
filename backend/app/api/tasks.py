from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.utils import commit_or_rollback, require_entity
from app.models.course import Course
from app.models.material import Material
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.services.task_service import sync_overdue_tasks

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "任务不存在"})


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
    task = Task(**payload.model_dump(), source_material_name=material.original_filename if material else None)
    db.add(task)
    commit_or_rollback(db)
    db.refresh(task)
    return task


@router.post("/{task_id}/complete", response_model=TaskRead)
def complete_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise _not_found()
    task.status = "completed"
    commit_or_rollback(db)
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
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)) -> Task:
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
    if "material_id" in changes and changes["material_id"] is not None:
        task.source_material_name = material.original_filename if material else None
    for field, value in changes.items():
        setattr(task, field, value)
    commit_or_rollback(db)
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db)) -> None:
    task = db.get(Task, task_id)
    if task is None:
        raise _not_found()
    db.delete(task)
    commit_or_rollback(db)
