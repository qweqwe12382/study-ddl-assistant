"""Development-only endpoint for resetting local test data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.course import Course
from app.models.material import Material
from app.models.study_plan import StudyPlan
from app.models.task import Task


router = APIRouter(prefix="/api/dev", tags=["development"])


@router.post("/reset")
def reset_test_data(db: Session = Depends(get_db)) -> dict:
    """Clear all local business records and uploaded files in development."""

    if settings.app_env.lower() not in {"development", "test"}:
        raise HTTPException(
            status_code=404,
            detail={"code": "RESET_DISABLED", "message": "当前环境不允许重置测试数据"},
        )

    table_models = (
        ("study_plans", StudyPlan),
        ("tasks", Task),
        ("materials", Material),
        ("courses", Course),
    )
    deleted = {}
    try:
        for table_name, model in table_models:
            result = db.execute(delete(model))
            deleted[table_name] = int(result.rowcount or 0)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={"code": "RESET_DATABASE_FAILED", "message": "测试数据清理失败"},
        ) from exc

    deleted_files = 0
    file_errors: list[str] = []
    upload_root = settings.upload_dir.resolve()
    upload_root.mkdir(parents=True, exist_ok=True)
    for path in upload_root.iterdir():
        if path.name == ".gitkeep" or not (path.is_file() or path.is_symlink()):
            continue
        try:
            path.unlink()
            deleted_files += 1
        except OSError:
            file_errors.append(path.name)

    return {
        "status": "reset",
        "deleted": deleted,
        "deleted_files": deleted_files,
        "file_errors": file_errors,
    }
