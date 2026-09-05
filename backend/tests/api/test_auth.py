from collections.abc import Generator
from contextlib import asynccontextmanager

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth_database import AuthBase, get_auth_db
from app.config import settings
from app.database import Base, get_db, get_system_db
from app.main import app
from app.services.auth import get_current_user


@pytest.fixture
def auth_client(tmp_path) -> Generator[TestClient, None, None]:
    previous_upload_dir = settings.upload_dir
    object.__setattr__(settings, "upload_dir", tmp_path / "uploads")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    auth_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    AuthBase.metadata.create_all(bind=auth_engine)
    auth_sessions = sessionmaker(bind=auth_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    system_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    system_sessions = sessionmaker(
        bind=system_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    workspace_sessions: dict[str, sessionmaker] = {}
    workspace_engines = []

    def override_auth_db() -> Generator[Session, None, None]:
        db = auth_sessions()
        try:
            yield db
        finally:
            db.close()

    def override_user_db(current_user=Depends(get_current_user)) -> Generator[Session, None, None]:
        factory = workspace_sessions.get(current_user.workspace_key)
        if factory is None:
            workspace_engine = create_engine(
                "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
            )

            @event.listens_for(workspace_engine, "connect")
            def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
                dbapi_connection.execute("PRAGMA foreign_keys=ON")

            Base.metadata.create_all(bind=workspace_engine)
            workspace_engines.append(workspace_engine)
            factory = sessionmaker(
                bind=workspace_engine, autoflush=False, autocommit=False, expire_on_commit=False
            )
            workspace_sessions[current_user.workspace_key] = factory
        db = factory()
        try:
            yield db
        finally:
            db.close()

    def override_system_db() -> Generator[Session, None, None]:
        db = system_sessions()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_auth_db] = override_auth_db
    app.dependency_overrides[get_db] = override_user_db
    app.dependency_overrides[get_system_db] = override_system_db
    original_lifespan_context = app.router.lifespan_context

    @asynccontextmanager
    async def isolated_lifespan(_app):
        yield

    app.router.lifespan_context = isolated_lifespan
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.router.lifespan_context = original_lifespan_context
        app.dependency_overrides.clear()
        auth_engine.dispose()
        system_engine.dispose()
        for workspace_engine in workspace_engines:
            workspace_engine.dispose()
        object.__setattr__(settings, "upload_dir", previous_upload_dir)


def _csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("study_csrf")
    assert token
    return {"X-CSRF-Token": token}


def test_email_authentication_csrf_and_workspace_isolation(auth_client: TestClient, tmp_path):
    client = auth_client

    assert client.get("/api/health").status_code == 200
    assert client.get("/api/courses").status_code == 401

    weak_password = client.post(
        "/api/auth/register",
        json={"display_name": "林同学", "email": "lin@example.com", "password": "onlyletters"},
    )
    assert weak_password.status_code == 422

    registered = client.post(
        "/api/auth/register",
        json={"display_name": "林同学", "email": "LIN@example.com", "password": "study2026"},
    )
    assert registered.status_code == 201
    assert registered.json()["email"] == "lin@example.com"
    assert registered.json()["is_admin"] is True
    cookies = registered.headers.get("set-cookie", "").lower()
    assert "study_session=" in cookies
    assert "httponly" in cookies
    assert "samesite=lax" in cookies

    assert client.get("/api/auth/me").json()["display_name"] == "林同学"
    assert client.get("/api/courses").json() == []
    assert client.post("/api/courses", json={"name": "数据结构"}).status_code == 403
    created = client.post(
        "/api/courses", json={"name": "数据结构"}, headers=_csrf_headers(client)
    )
    assert created.status_code == 201
    first_upload = client.post(
        "/api/materials/upload",
        files={"files": ("first-user.txt", b"Assignment due 2026-10-12", "text/plain")},
        headers=_csrf_headers(client),
    )
    assert first_upload.status_code == 201
    upload_dir = tmp_path / "uploads"
    assert len(list(upload_dir.glob("*.txt"))) == 1

    assert client.post("/api/auth/logout").status_code == 403
    assert client.post("/api/auth/logout", headers=_csrf_headers(client)).status_code == 204
    assert client.get("/api/courses").status_code == 401

    wrong_login = client.post(
        "/api/auth/login", json={"email": "lin@example.com", "password": "wrong-password"}
    )
    assert wrong_login.status_code == 401
    login = client.post(
        "/api/auth/login", json={"email": "lin@example.com", "password": "study2026"}
    )
    assert login.status_code == 200
    assert [course["name"] for course in client.get("/api/courses").json()] == ["数据结构"]
    assert client.post("/api/auth/logout", headers=_csrf_headers(client)).status_code == 204

    second_user = client.post(
        "/api/auth/register",
        json={"display_name": "周同学", "email": "zhou@example.com", "password": "campus2026"},
    )
    assert second_user.status_code == 201
    assert second_user.json()["is_admin"] is False
    assert client.get("/api/courses").json() == []
    assert client.get("/api/settings/llm").status_code == 403
    client.post("/api/courses", json={"name": "线性代数"}, headers=_csrf_headers(client))
    assert [course["name"] for course in client.get("/api/courses").json()] == ["线性代数"]
    second_upload = client.post(
        "/api/materials/upload",
        files={"files": ("second-user.txt", b"Quiz due 2026-10-13", "text/plain")},
        headers=_csrf_headers(client),
    )
    assert second_upload.status_code == 201
    user_directories = [path for path in upload_dir.iterdir() if path.is_dir()]
    assert len(user_directories) == 1
    assert len(list(user_directories[0].glob("*.txt"))) == 1
    reset_second = client.post("/api/dev/reset", headers=_csrf_headers(client))
    assert reset_second.status_code == 200
    assert len(list(upload_dir.glob("*.txt"))) == 1
    assert list(user_directories[0].glob("*.txt")) == []
    assert client.get("/api/courses").json() == []
    assert client.post("/api/auth/logout", headers=_csrf_headers(client)).status_code == 204

    client.post("/api/auth/login", json={"email": "lin@example.com", "password": "study2026"})
    assert [course["name"] for course in client.get("/api/courses").json()] == ["数据结构"]
    assert client.get("/api/settings/llm").status_code == 200


def test_duplicate_email_is_rejected(auth_client: TestClient):
    payload = {"display_name": "林同学", "email": "lin@example.com", "password": "study2026"}
    assert auth_client.post("/api/auth/register", json=payload).status_code == 201
    duplicate = auth_client.post("/api/auth/register", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "EMAIL_EXISTS"
