"""SQLAlchemy engine, session and database initialization."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from threading import Lock

from fastapi import Depends
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import database_path, ensure_runtime_directories, settings
from app.services.source_identity import add_plan_item_navigation_keys, new_navigation_key


class Base(DeclarativeBase):
    """Base class for all database models."""


ensure_runtime_directories()
if (path := database_path()) is not None:
    path.parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)


if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

_workspace_session_factories: dict[tuple[Path, str], sessionmaker] = {}
_workspace_lock = Lock()


def _workspace_session_factory(workspace_key: str) -> sessionmaker:
    """Return a dedicated SQLite session factory for one authenticated user."""

    if workspace_key == "legacy":
        return SessionLocal
    if not isinstance(workspace_key, str) or len(workspace_key) != 32 or any(
        char not in "0123456789abcdef" for char in workspace_key
    ):
        raise RuntimeError("Invalid workspace identity")
    workspace_dir = settings.user_database_dir.expanduser().resolve()
    cache_key = (workspace_dir, workspace_key)
    cached = _workspace_session_factories.get(cache_key)
    if cached is not None:
        return cached
    with _workspace_lock:
        cached = _workspace_session_factories.get(cache_key)
        if cached is not None:
            return cached
        workspace_dir.mkdir(parents=True, exist_ok=True)
        workspace_path = (workspace_dir / f"{workspace_key}.db").resolve()
        if workspace_path.parent != workspace_dir:
            raise RuntimeError("Invalid workspace identity")
        workspace_engine = create_engine(
            f"sqlite:///{workspace_path.as_posix()}",
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )

        @event.listens_for(workspace_engine, "connect")
        def _enable_workspace_foreign_keys(dbapi_connection, _connection_record) -> None:
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        from app import models  # noqa: F401

        Base.metadata.create_all(bind=workspace_engine)
        # create_all cannot add columns to an existing workspace database, so
        # later model extensions must replay the lightweight migrations here
        # just like init_db does for the shared database.
        with workspace_engine.begin() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            _apply_study_preference_migrations(connection)
        cached = sessionmaker(
            bind=workspace_engine, autoflush=False, autocommit=False, expire_on_commit=False
        )
        _workspace_session_factories[cache_key] = cached
        return cached


from app.services.auth import get_current_user  # noqa: E402


def get_system_db() -> Generator[Session, None, None]:
    """Unauthenticated system-database dependency reserved for health checks."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db(current_user=Depends(get_current_user)) -> Generator[Session, None, None]:
    db = _workspace_session_factory(current_user.workspace_key)()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Import models before create_all so SQLAlchemy knows every mapped table.
    from app import models  # noqa: F401

    # Existing M8.1 tables can predate the pending-fingerprint index. Prepare
    # them before SQLAlchemy attempts to create that unique index in create_all.
    if settings.database_url.startswith("sqlite"):
        with engine.begin() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            _apply_agent_migrations(connection)
            _apply_study_preference_migrations(connection)
    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations()


def _apply_lightweight_migrations() -> None:
    """Add columns introduced after the initial SQLite schema.

    The project intentionally keeps migrations lightweight for its local SQLite
    demo. Existing databases must continue to start after a model extension.
    """

    if not settings.database_url.startswith("sqlite"):
        return

    columns = {column["name"] for column in inspect(engine).get_columns("materials")}
    additions = {
        "file_size": "INTEGER",
        "content_hash": "VARCHAR(64)",
        "processing_error": "TEXT",
        "extraction_status": "VARCHAR(30) NOT NULL DEFAULT 'not_started'",
        "extraction_result": "JSON",
        "extraction_provider": "VARCHAR(50)",
        "extraction_error": "TEXT",
        "extracted_at": "DATETIME",
    }
    missing = {name: definition for name, definition in additions.items() if name not in columns}
    with engine.begin() as connection:
        # sqlite3 legacy transaction control does not automatically begin a
        # transaction for DDL.  Begin explicitly so every ALTER/backfill/index
        # in this migration either commits together or is rolled back.
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        for name, definition in missing.items():
            connection.execute(text(f'ALTER TABLE materials ADD COLUMN "{name}" {definition}'))
        _apply_task_migrations(connection)
        _apply_calibration_migrations(connection)
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_materials_content_hash "
                "ON materials(content_hash) WHERE content_hash IS NOT NULL"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_tasks_material_extraction_candidate "
                "ON tasks(material_id, extraction_batch_id, extraction_candidate_id) "
                "WHERE material_id IS NOT NULL AND extraction_batch_id IS NOT NULL "
                "AND extraction_candidate_id IS NOT NULL"
            )
        )
        _apply_agent_migrations(connection)
        _apply_study_preference_migrations(connection)
        _apply_navigation_key_migrations(connection)
        _apply_revision_migrations(connection)


def _apply_task_migrations(connection) -> None:
    """Backfill task fields added after the first local SQLite schema."""

    inspector = inspect(connection)
    if not inspector.has_table("tasks"):
        return
    additions = {
        "extraction_batch_id": "VARCHAR(64)",
        "extraction_candidate_id": "VARCHAR(100)",
        "source_material_name": "VARCHAR(255)",
        "estimated_minutes": "INTEGER",
        "remaining_minutes": "INTEGER",
        "actual_minutes": "INTEGER",
        "difficulty": "INTEGER",
        "completed_at": "DATETIME",
    }
    columns = {column["name"] for column in inspector.get_columns("tasks")}
    for name, definition in additions.items():
        if name not in columns:
            connection.execute(text(f'ALTER TABLE tasks ADD COLUMN "{name}" {definition}'))


def _apply_calibration_migrations(connection) -> None:
    """Backfill M8.4 task-feedback fields for existing local SQLite demos."""

    # New installations receive course_calibration_states from metadata.create_all.
    # This function intentionally contains no destructive data migration.
    inspector = inspect(connection)
    if inspector.has_table("tasks"):
        _apply_task_migrations(connection)


def _apply_agent_migrations(connection) -> None:
    """Keep locally-started M8.1 databases compatible with the hardened loop."""

    agent_additions = {
        "agent_suggestions": {
            "title": "VARCHAR(200) NOT NULL DEFAULT ''",
            "explanation": "TEXT NOT NULL DEFAULT ''",
            "source_navigation_key": "VARCHAR(32)",
        },
        "agent_runs": {
            "ruleset_version": "VARCHAR(50) NOT NULL DEFAULT 'm8.1'",
            "input_snapshot": "JSON NOT NULL DEFAULT '{}'",
        },
        "action_receipts": {
            "before_payload": "JSON NOT NULL DEFAULT '{}'",
            "after_payload": "JSON NOT NULL DEFAULT '{}'",
            "message": "TEXT NOT NULL DEFAULT ''",
            "navigation_key": "VARCHAR(32)",
            "source_navigation_key": "VARCHAR(32)",
        },
        "agent_events": {
            "entity_type": "VARCHAR(30)",
            "entity_id": "INTEGER",
            "entity_navigation_key": "VARCHAR(32)",
        },
        "weekly_review_snapshots": {
            "snapshot_status": "VARCHAR(20) NOT NULL DEFAULT 'current'",
            "ruleset_version": "VARCHAR(50) NOT NULL DEFAULT 'm8.6'",
            "rhythm_summary": "JSON NOT NULL DEFAULT '{}'",
        },
        "agent_reminder_preferences": {
            "last_digest_bucket": "VARCHAR(40)",
        },
    }
    inspector = inspect(connection)
    for table_name, additions in agent_additions.items():
        if not inspector.has_table(table_name):
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "{name}" {definition}'))

    # An older concurrent refresh may have created duplicates before the partial
    # uniqueness guard existed. Retain the earliest audit record and expire the
    # rest before installing the index.
    if inspector.has_table("agent_suggestions"):
        # Legacy pending suggestions carry only a reusable integer ID.  Do not
        # infer a new identity for that historical reference: making it
        # actionable could target a different row after SQLite ID reuse.
        connection.execute(
            text(
                "UPDATE agent_suggestions SET status = 'expired' "
                "WHERE status = 'pending' AND source_navigation_key IS NULL"
            )
        )
        connection.execute(
            text(
                "UPDATE agent_suggestions SET status = 'expired' "
                "WHERE status = 'pending' AND id NOT IN ("
                "SELECT keep_id FROM ("
                "SELECT MIN(id) AS keep_id FROM agent_suggestions "
                "WHERE status = 'pending' GROUP BY fingerprint"
                "))"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_suggestions_pending_fingerprint "
                "ON agent_suggestions(fingerprint) WHERE status = 'pending'"
            )
        )


def _apply_navigation_key_migrations(connection) -> None:
    """Backfill current navigable rows without rewriting historical evidence.

    SQLite cannot add a non-null, unique column to an existing populated table
    in one safe ``ALTER TABLE``.  The caller starts an explicit SQLite
    transaction before this nullable-add/backfill/index sequence; fresh
    installations receive the stricter metadata columns directly.
    """

    table_columns = {
        "materials": "navigation_key",
        "tasks": "navigation_key",
        "study_plans": "navigation_key",
        "action_receipts": "navigation_key",
    }
    inspector = inspect(connection)
    for table_name, column_name in table_columns.items():
        if not inspector.has_table(table_name):
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if column_name not in columns:
            connection.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" VARCHAR(32)'))
        rows = connection.execute(
            text(f'SELECT id FROM "{table_name}" WHERE "{column_name}" IS NULL OR "{column_name}" = \'\'')
        ).mappings()
        for row in rows:
            connection.execute(
                text(f'UPDATE "{table_name}" SET "{column_name}" = :navigation_key WHERE id = :id'),
                {"id": row["id"], "navigation_key": new_navigation_key()},
            )
        connection.execute(
            text(
                f'CREATE UNIQUE INDEX IF NOT EXISTS "uq_{table_name}_{column_name}" '
                f'ON "{table_name}" ("{column_name}")'
            )
        )

    if inspector.has_table("study_plans"):
        rows = connection.execute(text("SELECT id, plan_content FROM study_plans WHERE plan_content IS NOT NULL")).mappings()
        for row in rows:
            migrated = add_plan_item_navigation_keys(row["plan_content"])
            if migrated != row["plan_content"]:
                connection.execute(
                    text("UPDATE study_plans SET plan_content = :plan_content WHERE id = :id"),
                    {"id": row["id"], "plan_content": migrated},
                )


def _apply_revision_migrations(connection) -> None:
    """Give existing editable rows the initial optimistic-lock revision."""

    inspector = inspect(connection)
    for table_name in ("materials", "tasks", "study_plans"):
        if not inspector.has_table(table_name):
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "revision" not in columns:
            connection.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "revision" INTEGER NOT NULL DEFAULT 1'))


def _apply_study_preference_migrations(connection) -> None:
    """Backfill capacity-preference fields for partially initialized local DBs."""

    inspector = inspect(connection)
    if not inspector.has_table("study_preferences"):
        return
    additions = {
        "weekly_available_minutes": "INTEGER NOT NULL DEFAULT 1200",
        "daily_limit_minutes": "INTEGER NOT NULL DEFAULT 240",
        "buffer_ratio": "FLOAT NOT NULL DEFAULT 0.15",
        "preferred_time_slots": "JSON NOT NULL DEFAULT '[\"evening\"]'",
        "course_weights": "JSON NOT NULL DEFAULT '{}'",
        "semester_start_date": "DATE",
    }
    columns = {column["name"] for column in inspector.get_columns("study_preferences")}
    for name, definition in additions.items():
        if name not in columns:
            connection.execute(text(f'ALTER TABLE study_preferences ADD COLUMN "{name}" {definition}'))
