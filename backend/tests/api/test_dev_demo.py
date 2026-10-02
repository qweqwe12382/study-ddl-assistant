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
from app.models.user import User, UserSession
from app.services.auth import get_current_user
from app.services.auth import hash_password
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


def test_demo_email_is_reserved_for_the_demo_entry(auth_client: TestClient, seed_spy: dict):
    response = auth_client.post(
        "/api/auth/register",
        json={"display_name": "普通同学", "email": "DEMO@study.local", "password": "private2026"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_RESERVED"
    assert auth_client.get("/api/auth/me").status_code == 401
    assert auth_client.post("/api/auth/demo-login").json()["is_admin"] is False


def test_first_real_registration_after_demo_still_claims_admin_and_legacy_workspace(
    auth_client: TestClient, seed_spy: dict,
):
    demo = auth_client.post("/api/auth/demo-login").json()
    demo_course = auth_client.post(
        "/api/courses", json={"name": "演示空间课程"},
        headers={"X-CSRF-Token": auth_client.cookies.get("study_csrf")},
    )
    assert demo_course.status_code == 201

    registered = auth_client.post(
        "/api/auth/register",
        json={"display_name": "正式同学", "email": "real@example.com", "password": "private2026"},
    )
    assert registered.status_code == 201
    assert registered.json()["is_admin"] is True
    assert registered.json()["id"] != demo["id"]
    assert auth_client.get("/api/courses").json() == []
    with contextlib.contextmanager(app.dependency_overrides[get_auth_db])() as db:
        real = db.get(User, registered.json()["id"])
        assert real.workspace_key == "legacy"
        assert db.get(User, demo["id"]).workspace_key != "legacy"

    second = auth_client.post(
        "/api/auth/register",
        json={"display_name": "第二同学", "email": "second@example.com", "password": "private2026"},
    )
    assert second.status_code == 201
    assert second.json()["is_admin"] is False
    assert auth_client.post("/api/auth/demo-login").json()["id"] == demo["id"]
    assert [row["name"] for row in auth_client.get("/api/courses").json()] == ["演示空间课程"]


@pytest.mark.parametrize("is_admin,workspace_key", [(True, "legacy"), (False, "a" * 32)])
def test_demo_entry_never_adopts_an_existing_unmarked_account(
    auth_client: TestClient, seed_spy: dict, is_admin: bool, workspace_key: str,
):
    with contextlib.contextmanager(app.dependency_overrides[get_auth_db])() as db:
        db.add(User(
            id="b" * 32, email=auth_module.DEMO_ACCOUNT_EMAIL, display_name="已有账号",
            password_hash=hash_password("private2026"), workspace_key=workspace_key, is_admin=is_admin,
        ))
        db.commit()

    response = auth_client.post("/api/auth/demo-login")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DEMO_ACCOUNT_CONFLICT"
    assert seed_spy["calls"] == []
    assert auth_client.get("/api/auth/me").status_code == 401
    with contextlib.contextmanager(app.dependency_overrides[get_auth_db])() as db:
        assert db.scalars(select(UserSession)).all() == []
        existing = db.get(User, "b" * 32)
        assert existing.display_name == "已有账号"
        assert existing.is_admin is is_admin
        assert existing.workspace_key == workspace_key

    # The original password login remains available to its owner.
    assert auth_client.post("/api/auth/login", json={
        "email": auth_module.DEMO_ACCOUNT_EMAIL, "password": "private2026",
    }).status_code == 200


@pytest.mark.parametrize("field,value", [("is_admin", True), ("workspace_key", "legacy")])
def test_demo_entry_rechecks_its_marked_account_before_seeding(
    auth_client: TestClient, seed_spy: dict, field: str, value,
):
    demo = auth_client.post("/api/auth/demo-login").json()
    auth_client.cookies.clear()
    seed_spy["calls"].clear()
    with contextlib.contextmanager(app.dependency_overrides[get_auth_db])() as db:
        setattr(db.get(User, demo["id"]), field, value)
        db.commit()

    response = auth_client.post("/api/auth/demo-login")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DEMO_ACCOUNT_CONFLICT"
    assert seed_spy["calls"] == []
    assert auth_client.get("/api/auth/me").status_code == 401
