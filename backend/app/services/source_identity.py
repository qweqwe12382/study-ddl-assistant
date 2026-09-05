"""Opaque, non-reusable identities for evidence navigation.

Database row IDs remain useful for joins and fixed UI query parameters, but
they are not durable evidence identities on SQLite because a deleted row ID
may be reused.  Navigation keys are deliberately small, random, and immutable.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any
from uuid import uuid4

from sqlalchemy.orm.attributes import NO_VALUE


NAVIGATION_KEY_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def new_navigation_key() -> str:
    return uuid4().hex


def prevent_navigation_key_change(_target: object, value: object, oldvalue: object, _initiator: object) -> object:
    """Reject ORM-level replacement after a durable navigation identity exists.

    Startup migrations deliberately use SQL so they can repair old rows without
    constructing incomplete historical models.  Application writes, however,
    must not replace a live identity after it has been assigned.
    """

    if oldvalue is not NO_VALUE and oldvalue is not None and value != oldvalue:
        raise ValueError("navigation_key is immutable")
    return value


def valid_navigation_key(value: object) -> bool:
    return isinstance(value, str) and NAVIGATION_KEY_PATTERN.fullmatch(value) is not None


def add_plan_item_navigation_keys(content: str | None) -> str | None:
    """Return an equivalent plan payload with missing item keys backfilled.

    Malformed legacy plan content stays untouched: the normal plan decoder is
    already responsible for representing it as unreadable rather than trying
    to repair unknown user data during startup.
    """

    if not content:
        return content
    try:
        payload: Any = json.loads(content)
    except (TypeError, ValueError, json.JSONDecodeError):
        return content
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        return content

    changed = False
    migrated_items: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for item in payload["items"]:
        if not isinstance(item, dict):
            continue
        before = deepcopy(item)
        if not valid_navigation_key(item.get("navigation_key")):
            item["navigation_key"] = new_navigation_key()
            changed = True
        # The new source-reference lists must participate in a baseline's
        # exact item comparison.  Only add absent fields; corrupted historical
        # shapes remain untouched and continue to be handled by the decoder.
        for field_name in ("source_material_refs", "source_task_refs"):
            if field_name not in item:
                item[field_name] = []
                changed = True
        item_id = item.get("id")
        if isinstance(item_id, str):
            migrated_items[item_id] = (before, deepcopy(item))

    # Existing generated plans keep an item-for-item baseline.  Synchronize
    # only an exactly matching baseline item: a user/agent-modified baseline
    # is intentionally left alone rather than guessed into equivalence.
    agent = payload.get("agent")
    baseline = agent.get("baseline_items") if isinstance(agent, dict) else None
    if isinstance(baseline, dict):
        for item_id, (before, after) in migrated_items.items():
            if baseline.get(item_id) == before:
                baseline[item_id] = after
                changed = True
    return json.dumps(payload, ensure_ascii=False) if changed else content
