"""Safe, deterministic demo data for local presentations."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.material import Material
from app.models.task import Task


DEMO_COURSE_NAME = "数据结构（演示）"


def ensure_demo_data(db: Session) -> bool:
    """Create generic demo records once and report whether anything was added."""

    if db.scalar(select(Course.id).where(Course.name == DEMO_COURSE_NAME)) is not None:
        return False

    course = Course(
        name=DEMO_COURSE_NAME,
        teacher="演示教师",
        semester="2026 秋",
        color="#5964ed",
    )
    db.add(course)
    db.flush()

    notice = Material(
        course_id=course.id,
        original_filename="演示课程通知.md",
        file_type="md",
        material_type="作业要求",
        extracted_text="作业一：完成二叉树遍历练习。\n复习重点：递归、队列和复杂度分析。",
        summary="二叉树遍历练习及复杂度分析",
        tags=["作业", "二叉树", "重点"],
        processing_status="processed",
    )
    review = Material(
        course_id=course.id,
        original_filename="演示复习重点.txt",
        file_type="txt",
        material_type="复习资料",
        extracted_text="线性表、栈、队列、树和图的基本概念。",
        summary="课程核心数据结构概念整理",
        tags=["复习", "数据结构"],
        processing_status="processed",
    )
    db.add_all([notice, review])
    db.flush()

    now = datetime.combine(date.today(), time(12, 0))
    db.add_all(
        [
            Task(
                course_id=course.id,
                material_id=notice.id,
                source_material_name=notice.original_filename,
                name="完成二叉树遍历练习",
                task_type="作业",
                description="提交先序、中序和后序遍历结果。",
                due_at=now + timedelta(days=3),
                priority=4,
                status="in_progress",
            ),
            Task(
                course_id=course.id,
                material_id=review.id,
                source_material_name=review.original_filename,
                name="整理课程复习提纲",
                task_type="复习",
                description="将核心概念整理为一页提纲。",
                due_at=now + timedelta(days=7),
                priority=3,
                status="not_started",
            ),
        ]
    )
    db.commit()
    return True
