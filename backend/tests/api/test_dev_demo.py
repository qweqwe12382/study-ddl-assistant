"""One-click demo login for the competition demo mode."""

import contextlib
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.auth as auth_module
import app.database as database_module
from app.auth_database import AuthBase, get_auth_db
from app.database import Base
from app.main import app
from app.models.course import Course
from app.services.auth import get_current_user
from test_auth import auth_client  # noqa: F401


@pytest.fixture
def seed_spy(monkeypatch) -> dict:
    """Replace workspace seeding with a recorded no-op so tests stay hermetic."""

    calls: list[str] = []
    monkeypatch.setattr(auth_module, "_seed_demo_workspace", lambda key: calls.append(key))
    return {"calls": calls}


@pytest.fixture
def seeded_workspace_factory(monkeypatch) -> dict:
    """Route demo seeding to a shared in-memory workspace engine."""

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    monkeypatch.setattr(database_module, "_workspace_session_factory", lambda workspace_key: factory)
    return {"engine": engine, "factory": factory}


@pytest.fixture
def isolated_auth_client():
    """TestClient whose auth database is an isolated in-memory SQLite."""

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    AuthBase.metadata.create_all(bind=engine)
    auth_sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def override_auth_db() -> Generator:
        db = auth_sessions()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_auth_db] = override_auth_db
    original_lifespan = app.router.lifespan_context

    @contextlib.asynccontextmanager
    async def isolated_lifespan(_app):
        yield

    app.router.lifespan_context = isolated_lifespan
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.router.lifespan_context = original_lifespan
        app.dependency_overrides.clear()
        engine.dispose()


def test_demo_login_reuses_one_account_and_starts_session(auth_client: TestClient, seed_spy: dict):
    first = auth_client.post("/api/auth/demo-login")
    assert first.status_code == 200
    body = first.json()
    assert body["email"] == "demo@study.local"
    assert body["display_name"] == "演示同学"
    assert body["is_admin"] is False
    assert len(seed_spy["calls"]) == 1
    assert len(seed_spy["calls"][0]) == 32

    me = auth_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "demo@study.local"

    second = auth_client.post("/api/auth/demo-login")
    assert second.status_code == 200
    assert second.json()["id"] == body["id"]
    assert len(seed_spy["calls"]) == 2


def test_demo_login_seeds_workspace_once(isolated_auth_client: TestClient, seeded_workspace_factory: dict):
    first = isolated_auth_client.post("/api/auth/demo-login")
    assert first.status_code == 200
    workspace_db = seeded_workspace_factory["factory"]()
    try:
        courses = workspace_db.scalars(select(Course)).all()
        assert len(courses) == 1
        assert courses[0].name == "数据结构（演示）"
    finally:
        workspace_db.close()

    second = isolated_auth_client.post("/api/auth/demo-login")
    assert second.status_code == 200
    workspace_db = seeded_workspace_factory["factory"]()
    try:
        assert len(workspace_db.scalars(select(Course)).all()) == 1
    finally:
        workspace_db.close()


def test_demo_login_disabled_in_production(auth_client: TestClient, monkeypatch, seed_spy: dict):
    previous = auth_module.settings.app_env
    object.__setattr__(auth_module.settings, "app_env", "production")
    try:
        response = auth_client.post("/api/auth/demo-login")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "DEMO_DISABLED"
        assert seed_spy["calls"] == []
    finally:
        object.__setattr__(auth_module.settings, "app_env", previous)
