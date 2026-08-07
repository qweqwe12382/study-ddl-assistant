import csv
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.material import Material
from app.models.study_plan import StudyPlan
from app.models.task import Task
from app.services.study_plan import decode_plan_content

router = APIRouter(prefix="/api/exports", tags=["exports"])


def _download(content: str, *, filename: str, media_type: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
