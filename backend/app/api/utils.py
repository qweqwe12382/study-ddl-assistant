"""Shared API validation and transaction helpers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def require_entity(
    db: Session,
    model: Any,
    entity_id: int | None,
    *,
    code: str,
    message: str,
) -> Any | None:
    """Return a referenced entity or raise a consistent 404 response."""

    if entity_id is None:
        return None
    entity = db.get(model, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail={"code": code, "message": message})
    return entity


def commit_or_rollback(db: Session) -> None:
    """Commit a request transaction and convert constraint errors into 409s."""

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": "DATABASE_CONSTRAINT_ERROR", "message": "数据与现有记录冲突"},
        ) from exc
