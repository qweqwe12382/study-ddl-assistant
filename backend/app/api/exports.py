import csv
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from icalendar import Alarm, Calendar, Event, Timezone
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.material import Material
from app.models.study_plan import StudyPlan
from app.models.task import Task
from app.services.study_plan import decode_plan_content
from app.services.task_service import sync_overdue_tasks

router = APIRouter(prefix="/api/exports", tags=["exports"])
CALENDAR_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _download(content: str | bytes, *, filename: str, media_type: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _calendar_datetime(value: datetime) -> datetime:
    """Represent stored wall-clock deadlines in the application's local timezone."""

    if value.tzinfo is None:
        return value.replace(tzinfo=CALENDAR_TIMEZONE)
    return value.astimezone(CALENDAR_TIMEZONE)


@router.get("/tasks.ics")
def export_tasks_icalendar(
    include_completed: bool = Query(default=False),
    course_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    """Export dated DDL tasks as importable calendar events with reminders."""

    sync_overdue_tasks(db)
    statement = (
        select(Task)
        .options(selectinload(Task.course), selectinload(Task.material))
        .where(Task.due_at.is_not(None))
        .order_by(Task.due_at.asc(), Task.created_at.asc())
    )
    if not include_completed:
        statement = statement.where(Task.status != "completed")
    if course_id is not None:
        statement = statement.where(Task.course_id == course_id)
    tasks = list(db.scalars(statement).all())

    calendar = Calendar()
    calendar.add("prodid", "-//Learning Assistant//DDL Calendar//CN")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "PUBLISH")
    calendar.add("x-wr-calname", "学伴管家 DDL")
    calendar.add("x-wr-timezone", "Asia/Shanghai")
    event_datetimes = [_calendar_datetime(task.due_at) for task in tasks if task.due_at]
    years = [value.year for value in event_datetimes] or [datetime.now(CALENDAR_TIMEZONE).year]
    first_year = max(1, min(years) - 1)
    last_year = min(9999, max(years) + 2)
    calendar.add_component(
        Timezone.from_tzinfo(
            CALENDAR_TIMEZONE,
            first_date=date(first_year, 1, 1),
            last_date=date(last_year, 12, 31),
        )
    )

    generated_at = datetime.now(timezone.utc)
    status_labels = {
        "not_started": "未开始",
        "in_progress": "进行中",
        "completed": "已完成",
        "overdue": "已逾期",
    }
    for task, due_at in zip(tasks, event_datetimes, strict=True):
        course_name = task.course.name if task.course else "未归类课程"
        source_name = task.material.original_filename if task.material else task.source_material_name
        description = [
            f"课程：{course_name}",
            f"状态：{status_labels.get(task.status, task.status)}",
            f"优先级：{task.priority}/5",
        ]
        if task.task_type:
            description.append(f"类型：{task.task_type}")
        if source_name:
            description.append(f"来源资料：{source_name}")
        if task.description:
            description.extend(["", task.description])

        event = Event()
        event.add("uid", f"task-{task.id}@learning-assistant.local")
        event.add("dtstamp", generated_at)
        event.add("dtstart", due_at)
        event.add("dtend", due_at + timedelta(minutes=30))
        event.add("summary", f"[DDL] {task.name}")
        event.add("description", "\n".join(description))
        event.add("categories", [course_name, task.task_type or "DDL"])
        event.add("status", "CONFIRMED")

        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("trigger", timedelta(days=-1))
        alarm.add("description", f"明天截止：{task.name}")
        event.add_component(alarm)
        calendar.add_component(event)

    return _download(
        calendar.to_ical(),
        filename="ddl-tasks.ics",
        media_type="text/calendar; charset=utf-8",
    )


@router.get("/tasks.csv")
def export_tasks_csv(db: Session = Depends(get_db)) -> Response:
    tasks = list(
        db.scalars(
            select(Task)
            .options(selectinload(Task.course), selectinload(Task.material))
            .order_by(Task.due_at.asc(), Task.created_at.asc())
        ).all()
    )
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["任务名称", "所属课程", "任务类型", "截止时间", "状态", "优先级", "来源资料", "备注"])
    for task in tasks:
        writer.writerow(
            [
                task.name,
                task.course.name if task.course else "",
                task.task_type or "",
                task.due_at.isoformat() if task.due_at else "",
                task.status,
                task.priority,
                task.material.original_filename if task.material else task.source_material_name or "",
                task.description or "",
            ]
        )
    # UTF-8 BOM keeps Chinese headers readable when opened directly in Excel.
    return _download(f"\ufeff{output.getvalue()}", filename="ddl-tasks.csv", media_type="text/csv; charset=utf-8")


@router.get("/materials.md")
def export_materials_markdown(db: Session = Depends(get_db)) -> Response:
    materials = list(
        db.scalars(
            select(Material)
            .options(selectinload(Material.course))
            .order_by(Material.created_at.desc())
        ).all()
    )
    lines = ["# 学习资料目录", "", f"> 共 {len(materials)} 份资料。", ""]
    if not materials:
        lines.append("暂无资料记录。")
    for material in materials:
        tags = "、".join(material.tags or []) or "无"
        lines.extend(
            [
                f"## {material.original_filename}",
                f"- 课程：{material.course.name if material.course else '未归类课程'}",
                f"- 类型：{material.material_type or material.file_type or '未分类'}",
                f"- 标签：{tags}",
                f"- 处理状态：{material.processing_status}",
                f"- 摘要：{material.summary or '暂无摘要'}",
                "",
            ]
        )
    return _download("\n".join(lines), filename="materials-catalog.md", media_type="text/markdown; charset=utf-8")


@router.get("/study-plans/{plan_id}.md")
def export_study_plan_markdown(plan_id: int, db: Session = Depends(get_db)) -> Response:
    plan = db.get(StudyPlan, plan_id)
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "STUDY_PLAN_NOT_FOUND", "message": "复习计划不存在"},
        )
    items, warnings, material_count, task_count = decode_plan_content(plan.plan_content)
    material_ids = {material_id for item in items for material_id in item.source_material_ids}
    task_ids = {task_id for item in items for task_id in item.source_task_ids}
    source_materials = {
        material.id: material.original_filename
        for material in db.scalars(select(Material).where(Material.id.in_(material_ids))).all()
    } if material_ids else {}
    source_tasks = {
        task.id: task.name
        for task in db.scalars(select(Task).where(Task.id.in_(task_ids))).all()
    } if task_ids else {}
    lines = [
        f"# {plan.title}",
        "",
        f"- 考试日期：{plan.exam_date.isoformat() if plan.exam_date else '未设置'}",
        f"- 每日学习时间：{plan.daily_minutes or '未设置'} 分钟",
        f"- 计划状态：{plan.status}",
        f"- 参考资料：{material_count} 份；未完成任务：{task_count} 个",
        "",
    ]
    if warnings:
        lines.extend(["## 风险提示", "", *[f"- {warning}" for warning in warnings], ""])
    lines.extend(["## 复习清单", ""])
    if not items:
        lines.append("暂无计划明细。")
    for item in items:
        sources = []
        if item.source_material_ids:
            labels = [source_materials.get(value, f"#{value}") for value in item.source_material_ids]
            sources.append(f"资料：{'、'.join(labels)}")
        if item.source_task_ids:
            labels = [source_tasks.get(value, f"#{value}") for value in item.source_task_ids]
            sources.append(f"任务：{'、'.join(labels)}")
        source_label = f"；来源：{'、'.join(sources)}" if sources else ""
        lines.extend(
            [
                f"### {item.date.isoformat()} · {item.phase} · {item.title}",
                f"- 时长：{item.minutes} 分钟",
                f"- 状态：{item.status}",
                f"- 知识点：{'、'.join(item.knowledge_points) or '未标注'}{source_label}",
                f"- 内容：{item.content}",
                "",
            ]
        )
    filename = f"study-plan-{plan.id}.md"
    return _download("\n".join(lines), filename=filename, media_type="text/markdown; charset=utf-8")
