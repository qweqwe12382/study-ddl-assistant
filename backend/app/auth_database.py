"""Independent account/session store for the local multi-user web app."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import PROJECT_ROOT, settings


class AuthBase(DeclarativeBase):
    pass


def _sqlite_path_from_url(url: str) -> Path | None:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return None
    path = Path(url[len(prefix) :])
    return path if path.is_absolute() else PROJECT_ROOT / path


if (auth_path := _sqlite_path_from_url(settings.auth_database_url)) is not None:
    auth_path.parent.mkdir(parents=True, exist_ok=True)

auth_connect_args = {"check_same_thread": False} if settings.auth_database_url.startswith("sqlite") else {}
auth_engine = create_engine(settings.auth_database_url, connect_args=auth_connect_args, pool_pre_ping=True)

if settings.auth_database_url.startswith("sqlite"):

    @event.listens_for(auth_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")


AuthSessionLocal = sessionmaker(bind=auth_engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_auth_db() -> Generator[Session, None, None]:
    db = AuthSessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_auth_db() -> None:
    from app.models import user  # noqa: F401

    AuthBase.metadata.create_all(bind=auth_engine)
    if settings.auth_database_url.startswith("sqlite"):
        columns = {column["name"] for column in inspect(auth_engine).get_columns("users")}
        if "is_admin" not in columns:
            with auth_engine.begin() as connection:
                connection.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"))
                connection.execute(
                    text(
                        "UPDATE users SET is_admin = 1 WHERE id = ("
                        "SELECT id FROM users ORDER BY created_at ASC, id ASC LIMIT 1)"
                    )
                )
