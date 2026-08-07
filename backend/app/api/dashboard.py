from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.course import Course
from app.models.material import Material
from app.models.task import Task
from app.schemas.dashboard import DashboardMaterialRead, DashboardRead, DashboardTaskRead
from app.schemas.material import MaterialSearchRead
from app.schemas.task import TaskRead
from app.services.task_service import _as_utc, sync_overdue_tasks

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _task_payload(task: Task) -> DashboardTaskRead:
    payload = TaskRead.model_validate(task).model_dump()
    payload.update(
        {
            "course_name": task.course.name if task.course else None,
            "material_name": task.material.original_filename if task.material else task.source_material_name,
            "source_available": task.material is not None,
        }
    )
    return DashboardTaskRead.model_validate(payload)


def _material_payload(material: Material) -> DashboardMaterialRead:
    payload = MaterialSearchRead.model_validate(material).model_dump()
    payload["course_name"] = material.course.name if material.course else None
    return DashboardMaterialRead.model_validate(payload)


@router.get("", response_model=DashboardRead)
def get_dashboard(db: Session = Depends(get_db)) -> DashboardRead:
    sync_overdue_tasks(db)
    now = datetime.now(timezone.utc)
    next_week = now + timedelta(days=7)
    tasks = list(
        db.scalars(select(Task).options(selectinload(Task.course), selectinload(Task.material))).all()
    )
    active = [task for task in tasks if task.status != "completed"]
    overdue = [
        task for task in active
        if task.status == "overdue" or (task.due_at and _as_utc(task.due_at) < now)
    ]
    upcoming = [
        task for task in active
        if task.due_at and now <= _as_utc(task.due_at) <= next_week
    ]
    upcoming.sort(key=lambda task: (_as_utc(task.due_at), -task.priority, task.id))
    overdue.sort(key=lambda task: (_as_utc(task.due_at) if task.due_at else now, -task.priority, task.id))
    recent_materials = list(
        db.scalars(
            select(Material).options(selectinload(Material.course)).order_by(Material.created_at.desc()).limit(5)
        ).all()
    )
    if overdue:
        next_action = "先处理逾期任务，再重新安排接下来 7 天的任务。"
    elif upcoming:
        next_action = "优先完成最近 7 天内到期的任务。"
    elif not recent_materials:
        next_action = "先上传一份课程资料，建立你的学习资料库。"
    else:
        next_action = "当前没有临近 DDL，可以继续整理资料或创建复习任务。"
    return DashboardRead(
        active_task_count=len(active),
        due_soon_count=len(upcoming),
        overdue_count=len(overdue),
        completed_task_count=len(tasks) - len(active),
        materials_count=db.scalar(select(func.count(Material.id))) or 0,
        courses_count=db.scalar(select(func.count(Course.id))) or 0,
        upcoming_tasks=[_task_payload(task) for task in upcoming[:5]],
        overdue_tasks=[_task_payload(task) for task in overdue[:5]],
        recent_materials=[_material_payload(material) for material in recent_materials],
        next_action=next_action,
    )
