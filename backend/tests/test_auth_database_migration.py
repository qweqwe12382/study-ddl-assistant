"""Schema upgrades must not turn preexisting users into public demo identities."""

import pytest
from sqlalchemy import create_engine, inspect, text
from types import SimpleNamespace

import app.auth_database as auth_database


@pytest.mark.parametrize("has_admin_column", [True, False])
def test_auth_upgrade_preserves_old_accounts_without_adopting_demo_email(tmp_path, monkeypatch, has_admin_column):
    engine = create_engine(f"sqlite:///{(tmp_path / 'old-auth.db').as_posix()}")
    monkeypatch.setattr(auth_database, "auth_engine", engine)
    monkeypatch.setattr(auth_database, "settings", SimpleNamespace(auth_database_url=str(engine.url)))
    admin_column = ", is_admin BOOLEAN NOT NULL DEFAULT 0" if has_admin_column else ""
    try:
        with engine.begin() as connection:
            connection.execute(text(
                "CREATE TABLE users (id VARCHAR(32) PRIMARY KEY, email VARCHAR(254) UNIQUE NOT NULL, "
                "display_name VARCHAR(40) NOT NULL, password_hash VARCHAR(255) NOT NULL, "
                "workspace_key VARCHAR(40) UNIQUE NOT NULL, created_at DATETIME NOT NULL, "
                f"updated_at DATETIME NOT NULL{admin_column})"
            ))
            connection.execute(text(
                "INSERT INTO users (id, email, display_name, password_hash, workspace_key, created_at, updated_at) "
                "VALUES (:id, :email, :name, :password, :workspace, '2026-09-01', '2026-09-01')"
            ), {"id": "a" * 32, "email": "demo@study.local", "name": "旧账号", "password": "unchanged",
                "workspace": "legacy"})

        auth_database.init_auth_db()
        auth_database.init_auth_db()

        assert {"is_admin", "is_demo"} <= {column["name"] for column in inspect(engine).get_columns("users")}
        with engine.connect() as connection:
            row = connection.execute(text("SELECT * FROM users")).mappings().one()
        assert row["is_demo"] == 0
        assert row["is_admin"] == (0 if has_admin_column else 1)
        assert row["password_hash"] == "unchanged"
        assert row["workspace_key"] == "legacy"
        assert row["display_name"] == "旧账号"
    finally:
        engine.dispose()
