"""Schema upgrades must not turn preexisting users into public demo identities."""

import pytest
from sqlalchemy import create_engine, inspect, text
from types import SimpleNamespace

import app.auth_database as auth_database
from app.models.user import RegistrationEmailCode, User


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
        assert row["email_verified"] == 0
        assert row["is_admin"] == (0 if has_admin_column else 1)
        assert row["password_hash"] == "unchanged"
        assert row["workspace_key"] == "legacy"
        assert row["display_name"] == "旧账号"
    finally:
        engine.dispose()


def test_email_backfill_only_trusts_consumed_challenge_at_registration(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'accounts.db').as_posix()}")
    monkeypatch.setattr(auth_database, "auth_engine", engine)
    monkeypatch.setattr(auth_database, "settings", SimpleNamespace(auth_database_url=str(engine.url)))
    try:
        User.__table__.create(engine)
        RegistrationEmailCode.__table__.create(engine)
        with engine.begin() as db:
            db.exec_driver_sql("ALTER TABLE users DROP COLUMN email_verified")
            for email, digest, delivered, age, demo in [
                ("valid@example.com", "", 0, 180, 0),
                ("old@example.com", "", 0, 9999, 0),
                ("guessed@example.com", "unused-digest", 1, 180, 0),
                ("demo@example.com", "", 0, 180, 1),
            ]:
                db.execute(text("""
                    INSERT INTO users (id,email,workspace_key,display_name,password_hash,is_admin,is_demo,created_at,updated_at)
                    VALUES (:e,:e,:e,'test','hash',0,:demo,'2026-09-01','2026-09-01')
                """), {"e": email, "demo": demo})
                db.execute(text("""
                    INSERT INTO registration_email_codes
                    (email,challenge_id,digest,delivered,expires_at,retry_at,window_start,sends_in_window,attempts_remaining)
                    VALUES (:e,'challenge',:digest,:delivered,strftime('%s','2026-09-01') + :age,0,0,1,0)
                """), {"e": email, "digest": digest, "delivered": delivered, "age": age})
        auth_database.init_auth_db()
        auth_database.init_auth_db()
        with engine.connect() as db:
            assert db.scalars(text("SELECT email FROM users WHERE email_verified = 1")).all() == ["valid@example.com"]
    finally:
        engine.dispose()
