from collections.abc import Generator
from contextlib import asynccontextmanager
from dataclasses import replace
from types import SimpleNamespace

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


@pytest.fixture
def registration_verification(monkeypatch):
    from app.api import auth
    from app.services import signup_verification

    send_log = []
    configured = replace(
        settings,
        auth_turnstile_enabled=True,
        auth_turnstile_site_key="public-test-key",
        auth_turnstile_secret_key="secret-test-key",
        auth_turnstile_hostname="study.example.com",
        auth_email_verification_enabled=True,
        auth_email_code_secret="test-key-only-not-a-production-secret",
        auth_smtp_host="smtp.example.com",
        auth_smtp_username="test-user",
        auth_smtp_password="test-password",
        auth_smtp_from="signup@study.example.com",
    )
    monkeypatch.setattr(auth, "settings", configured)
    monkeypatch.setattr(signup_verification, "settings", configured)
    monkeypatch.setattr(signup_verification, "_send_email_code", lambda email, code: send_log.append((email, code)))

    def siteverify(url, *, data, timeout):
        assert url == signup_verification.SITEVERIFY_URL
        assert data["secret"] == configured.auth_turnstile_secret_key
        action, _, hostname = data["response"].partition("@")
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"success": True, "action": action, "hostname": hostname},
        )

    monkeypatch.setattr(signup_verification.requests, "post", siteverify)
    return configured, signup_verification, send_log


def test_register_requires_verified_email_and_login_checks_turnstile(auth_client, registration_verification):
    _settings, _verification, sent = registration_verification
    email = "lin@example.com"
    registration = {"email": email, "password": "StrongPass123", "display_name": "林同学"}
    code_request = {"email": email, "turnstile_token": "register_code@study.example.com"}

    config = auth_client.get("/api/auth/config").json()
    assert config == {"turnstile_site_key": "public-test-key", "email_verification_required": True}
    assert auth_client.post("/api/auth/register", json=registration).status_code == 400
    rejected = auth_client.post(
        "/api/auth/register/code", json={**code_request, "turnstile_token": "login@study.example.com"}
    )
    assert rejected.status_code == 400
    assert sent == []
    response = auth_client.post("/api/auth/register/code", json=code_request)
    assert response.json() == {"retry_after_seconds": 60}
    assert sent[0][0] == email
    throttled = auth_client.post("/api/auth/register/code", json=code_request)
    assert throttled.status_code == 429
    assert int(throttled.headers["Retry-After"]) > 0
    assert len(sent) == 1
    code = sent[0][1]
    wrong_code = "000001" if code == "000000" else "000000"
    assert auth_client.post("/api/auth/register", json={**registration, "email_code": wrong_code}).status_code == 400
    assert auth_client.post(
        "/api/auth/register", json={**registration, "email": "other@example.com", "email_code": code}
    ).status_code == 400
    assert auth_client.post("/api/auth/register", json={**registration, "email_code": code}).status_code == 201
    assert auth_client.get("/api/auth/me").json()["email"] == email

    credentials = {"email": email, "password": registration["password"]}
    assert auth_client.post("/api/auth/login", json=credentials).status_code == 400
    assert auth_client.post(
        "/api/auth/login", json={**credentials, "turnstile_token": "login@wrong.example.com"}
    ).status_code == 400
    assert auth_client.post(
        "/api/auth/login", json={**credentials, "turnstile_token": "login@study.example.com"}
    ).status_code == 200


def test_registration_codes_expire_and_limit_guesses(auth_client, registration_verification, monkeypatch):
    _settings, verification, sent = registration_verification
    now = 2_000_000_000
    monkeypatch.setattr(verification, "time", SimpleNamespace(time=lambda: now))
    email = "lin@example.com"
    registration = {"email": email, "password": "StrongPass123", "display_name": "林同学"}
    code_request = {"email": email, "turnstile_token": "register_code@study.example.com"}
    assert auth_client.post("/api/auth/register/code", json=code_request).status_code == 200
    expired_code = sent[-1][1]
    now += verification.CODE_LIFETIME
    assert auth_client.post("/api/auth/register", json={**registration, "email_code": expired_code}).status_code == 400
    assert auth_client.post("/api/auth/register/code", json=code_request).status_code == 200
    code = sent[-1][1]
    wrong_code = "000001" if code == "000000" else "000000"
    for _ in range(verification.MAX_ATTEMPTS):
        assert auth_client.post(
            "/api/auth/register", json={**registration, "email_code": wrong_code}
        ).status_code == 400
    assert auth_client.post("/api/auth/register", json={**registration, "email_code": code}).status_code == 400


def test_turnstile_still_protects_registration_when_email_is_disabled(auth_client, registration_verification, monkeypatch):
    from app.api import auth

    configured, verification, sent = registration_verification
    turnstile_only = replace(configured, auth_email_verification_enabled=False)
    monkeypatch.setattr(auth, "settings", turnstile_only)
    monkeypatch.setattr(verification, "settings", turnstile_only)
    registration = {"email": "lin@example.com", "password": "StrongPass123", "display_name": "林同学"}
    assert auth_client.post("/api/auth/register", json=registration).status_code == 400
    assert auth_client.post(
        "/api/auth/register", json={**registration, "turnstile_token": "register@study.example.com"}
    ).status_code == 201
    assert sent == []


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
    assert client.get("/api/settings/llm").status_code == 404
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
    assert client.get("/api/settings/llm").status_code == 404


def test_first_public_registration_starts_with_an_isolated_non_admin_workspace(auth_client, monkeypatch):
    from app.api import auth, reset

    production = replace(settings, app_env="production")
    monkeypatch.setattr(auth, "settings", production)
    monkeypatch.setattr(reset, "settings", production)
    response = auth_client.post("/api/auth/register", json={
        "display_name": "新同学", "email": "student@example.com", "password": "study2026",
    })
    assert response.status_code == 201, response.text
    assert response.json()["is_admin"] is False
    assert auth_client.get("/api/courses").json() == []
    local_demo = auth_client.post("/api/auth/demo-login")
    assert local_demo.status_code == 404
    assert auth_client.post("/api/dev/reset", headers=_csrf_headers(auth_client)).status_code == 404


def test_duplicate_email_is_rejected(auth_client: TestClient):
    payload = {"display_name": "林同学", "email": "lin@example.com", "password": "study2026"}
    assert auth_client.post("/api/auth/register", json=payload).status_code == 201
    duplicate = auth_client.post("/api/auth/register", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "EMAIL_EXISTS"
