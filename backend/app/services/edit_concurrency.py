"""HTTP preconditions for the web client's optimistic editing contract."""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session


_STRONG_EDIT_TAG = re.compile(r'^"([0-9a-f]{32}):([1-9][0-9]{0,18})"$')


def edit_conflict() -> HTTPException:
    """Return the shared stale-edit response without exposing row details."""

    return HTTPException(
        status_code=409,
        detail={"code": "EDIT_CONFLICT", "message": "内容已在其他页面更新，请刷新后再试"},
    )


def check_edit_precondition(db: Session, entity: Any, if_match: str | None) -> None:
    """Validate the optional, single strong ``If-Match`` value.

    Omitting the header preserves legacy API compatibility.  Once supplied,
    its syntax is deliberately strict: weak/wildcard/list values cannot turn a
    stale numeric row ID into permission to edit a replacement row.
    """

    if if_match is None:
        return
    match = _STRONG_EDIT_TAG.fullmatch(if_match)
    if match is None:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_EDIT_PRECONDITION", "message": "If-Match 必须是单个强校验值"},
        )
    navigation_key, revision_text = match.groups()
    revision = int(revision_text)
    if entity.navigation_key != navigation_key or entity.revision != revision:
        raise edit_conflict()
    # `version_id_col` protects normal ORM writes, but an ABA delete/recreate
    # could otherwise make a new row look like revision 1. This conditional
    # no-op UPDATE includes the immutable key and acquires SQLite's write lock
    # for the rest of this transaction without changing revision or timestamps.
    model = type(entity)
    with db.no_autoflush:
        result = db.execute(
            update(model)
            .where(
                model.id == entity.id,
                model.navigation_key == navigation_key,
                model.revision == revision,
            )
            # Explicitly preserve the timestamp too: SQLAlchemy Core would
            # otherwise apply its column ``onupdate`` default to this lock.
            .values({model.revision: model.revision, model.updated_at: model.updated_at})
            .execution_options(synchronize_session=False)
        )
    if result.rowcount != 1:
        db.rollback()
        raise edit_conflict()
