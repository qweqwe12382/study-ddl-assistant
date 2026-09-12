"""Isolation coverage for configured per-user SQLite workspace storage."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

import app.database as database
from app.config import settings


KEY_A = "a" * 32
KEY_B = "b" * 32


@pytest.fixture
def configured_user_database_dir(tmp_path: Path):
    """Restore settings and dispose only factories created under this temp root."""

    previous_dir = settings.user_database_dir
    roots: set[Path] = set()

    def set_directory(path: Path) -> Path:
        resolved = path.resolve()
        roots.add(resolved)
        object.__setattr__(settings, "user_database_dir", resolved)
        return resolved

    try:
        yield set_directory
    finally:
        object.__setattr__(settings, "user_database_dir", previous_dir)
        with database._workspace_lock:
            cached_factories = [
                database._workspace_session_factories.pop(cache_key)
                for cache_key in list(database._workspace_session_factories)
                if cache_key[0] in roots
            ]
        for factory in cached_factories:
            factory.kw["bind"].dispose()


def _database_file(factory) -> Path:
    return Path(factory.kw["bind"].url.database).resolve()


def test_workspace_factories_create_independent_files_for_different_users(configured_user_database_dir, tmp_path: Path):
    workspace_dir = configured_user_database_dir(tmp_path / "users")
    factory_a = database._workspace_session_factory(KEY_A)
    factory_b = database._workspace_session_factory(KEY_B)

    assert factory_a is not factory_b
    assert _database_file(factory_a) == workspace_dir / f"{KEY_A}.db"
    assert _database_file(factory_b) == workspace_dir / f"{KEY_B}.db"
    assert _database_file(factory_a).is_file()
    assert _database_file(factory_b).is_file()

    with factory_a.kw["bind"].begin() as connection:
        connection.execute(text("CREATE TABLE workspace_isolation_probe (id INTEGER PRIMARY KEY)"))
    with factory_b.kw["bind"].connect() as connection:
        assert connection.execute(
            text("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'workspace_isolation_probe'")
        ).scalar_one_or_none() is None


def test_same_workspace_key_uses_a_distinct_factory_after_directory_changes(configured_user_database_dir, tmp_path: Path):
    first_dir = configured_user_database_dir(tmp_path / "first-root")
    first_factory = database._workspace_session_factory(KEY_A)
    second_dir = configured_user_database_dir(tmp_path / "second-root")
    second_factory = database._workspace_session_factory(KEY_A)

    assert first_factory is not second_factory
    assert _database_file(first_factory) == first_dir / f"{KEY_A}.db"
    assert _database_file(second_factory) == second_dir / f"{KEY_A}.db"
    assert _database_file(first_factory).is_file()
    assert _database_file(second_factory).is_file()


@pytest.mark.parametrize("workspace_key", ["", "legacy ", "../outside", "A" * 32, "a" * 31, "a" * 33, None])
def test_invalid_workspace_keys_cannot_create_paths_outside_the_configured_directory(
    configured_user_database_dir,
    tmp_path: Path,
    workspace_key: str | None,
):
    workspace_dir = configured_user_database_dir(tmp_path / "configured-users")

    with pytest.raises(RuntimeError, match="Invalid workspace identity"):
        database._workspace_session_factory(workspace_key)

    assert not workspace_dir.exists()
    assert not (tmp_path / "outside.db").exists()


def test_legacy_workspace_continues_to_use_the_shared_session_factory():
    assert database._workspace_session_factory("legacy") is database.SessionLocal
