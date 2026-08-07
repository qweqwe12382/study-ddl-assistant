"""SQLAlchemy engine, session and database initialization."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import database_path, ensure_runtime_directories, settings


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


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Import models before create_all so SQLAlchemy knows every mapped table.
    from app import models  # noqa: F401

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
        for name, definition in missing.items():
            connection.execute(text(f'ALTER TABLE materials ADD COLUMN "{name}" {definition}'))
        task_columns = {column["name"] for column in inspect(engine).get_columns("tasks")}
        task_additions = {
            "extraction_batch_id": "VARCHAR(64)",
            "extraction_candidate_id": "VARCHAR(100)",
            "source_material_name": "VARCHAR(255)",
        }
        for name, definition in task_additions.items():
            if name not in task_columns:
                connection.execute(text(f'ALTER TABLE tasks ADD COLUMN "{name}" {definition}'))
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
