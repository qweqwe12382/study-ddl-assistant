"""Human-confirmed DDL notice change preview and execution endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.api.utils import commit_or_rollback
from app.database import get_db
from app.models.agent import ActionReceipt
from app.models.task import Task
from app.schemas.deadline_radar import (
    DeadlineRadarApplyRead,
    DeadlineRadarApplyRequest,
    DeadlineRadarPreviewRead,
    DeadlineRadarPreviewRequest,
)
from app.services.deadline_radar import (
    CANCEL_TASK_FROM_NOTICE,
    DeadlineRadarError,
    build_deadline_radar_preview,
    execute_deadline_change,
    find_idempotent_result,
    notice_digest,
)
from app.services.edit_concurrency import check_edit_precondition, edit_conflict


router = APIRouter(prefix="/api/deadline-radar", tags=["deadline-radar"])


def _task(payload: DeadlineRadarPreviewRequest, db: Session) -> Task:
    task = db.get(Task, payload.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "关联任务不存在"})
    if task.navigation_key != payload.task_navigation_key or task.revision != payload.task_revision:
        raise edit_conflict()
    return task


def _radar_http_error(error: DeadlineRadarError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.message},
    )


@router.post("/preview", response_model=DeadlineRadarPreviewRead)
def preview_deadline_change(
    payload: DeadlineRadarPreviewRequest,
    db: Session = Depends(get_db),
) -> DeadlineRadarPreviewRead:
    task = _task(payload, db)
    try:
        return build_deadline_radar_preview(
            db,
            task,
            payload.notice_text,
            reference_time=payload.reference_time,
        )
    except DeadlineRadarError as exc:
        raise _radar_http_error(exc) from exc


@router.post("/apply", response_model=DeadlineRadarApplyRead)
def apply_deadline_change(
    payload: DeadlineRadarApplyRequest,
    db: Session = Depends(get_db),
) -> DeadlineRadarApplyRead:
    digest = notice_digest(payload.notice_text)
    try:
        existing = find_idempotent_result(
            db,
            idempotency_key=payload.idempotency_key,
            task_id=payload.task_id,
            digest=digest,
        )
        if existing is not None:
            receipt = db.scalar(select(ActionReceipt).where(ActionReceipt.suggestion_id == existing.id))
            task = db.get(Task, existing.source_id)
            if receipt is None or task is None:
                raise DeadlineRadarError(
                    "DEADLINE_CHANGE_RESULT_UNAVAILABLE",
                    "这次操作已有记录，但执行结果当前无法完整读取。",
                    status_code=409,
                )
            intent = "cancel" if existing.action_type == CANCEL_TASK_FROM_NOTICE else "reschedule"
            return DeadlineRadarApplyRead(
                intent=intent,
                task=task,
                receipt=receipt,
                plan_delta_count=int(receipt.applied_payload.get("plan_delta_count", 0)),
                message=receipt.message,
            )

        task = _task(payload, db)
        preview = build_deadline_radar_preview(
            db,
            task,
            payload.notice_text,
            reference_time=payload.reference_time,
        )
        check_edit_precondition(
            db,
            task,
            f'"{payload.task_navigation_key}:{payload.task_revision}"',
        )
        task, receipt, plan_delta_count = execute_deadline_change(
            db,
            task,
            preview,
            notice_text=payload.notice_text,
            idempotency_key=payload.idempotency_key,
        )
        commit_or_rollback(db)
        db.refresh(task)
        db.refresh(receipt)
        return DeadlineRadarApplyRead(
            intent=preview.intent,
            task=task,
            receipt=receipt,
            plan_delta_count=plan_delta_count,
            message=receipt.message,
        )
    except DeadlineRadarError as exc:
        db.rollback()
        raise _radar_http_error(exc) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": "IDEMPOTENCY_KEY_CONFLICT", "message": "该幂等键已用于另一项操作。"},
        ) from exc
    except StaleDataError as exc:
        db.rollback()
        raise edit_conflict() from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={"code": "DEADLINE_CHANGE_FAILED", "message": "通知变更未保存，请重试。"},
        ) from exc
