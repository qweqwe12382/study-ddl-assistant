"""One continuous, file-backed reviewer workflow with no production data access."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.auth_database import AuthBase, get_auth_db
from app.config import PROJECT_ROOT, settings
from app.database import Base, get_db, get_system_db
from app.main import app
from app.services.auth import get_current_user


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _file_session_factory(path: Path, metadata):
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(_sqlite_url(path), connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture
def isolated_reviewer_client(tmp_path: Path) -> Generator[tuple[TestClient, Path], None, None]:
    """Use distinct temporary files for system, auth, user data, and uploads."""

    runtime_root = tmp_path / "isolated-runtime"
    upload_dir = runtime_root / "uploads"
    user_data_dir = runtime_root / "user-data"
    upload_dir.mkdir(parents=True)

    auth_engine, auth_sessions = _file_session_factory(runtime_root / "auth.db", AuthBase.metadata)
    system_engine, system_sessions = _file_session_factory(runtime_root / "system.db", Base.metadata)
    workspace_engines = {}
    workspace_sessions = {}

    def override_auth_db() -> Generator[Session, None, None]:
        with auth_sessions() as db:
            yield db

    def override_system_db() -> Generator[Session, None, None]:
        with system_sessions() as db:
            yield db

    def override_user_db(current_user=Depends(get_current_user)) -> Generator[Session, None, None]:
        factory = workspace_sessions.get(current_user.workspace_key)
        if factory is None:
            engine, factory = _file_session_factory(
                user_data_dir / f"{current_user.workspace_key}.db", Base.metadata
            )
            workspace_engines[current_user.workspace_key] = engine
            workspace_sessions[current_user.workspace_key] = factory
        with factory() as db:
            yield db

    previous_settings = {
        "upload_dir": settings.upload_dir,
        "demo_mode": settings.demo_mode,
        "llm_base_url": settings.llm_base_url,
        "llm_api_key": settings.llm_api_key,
        "llm_model": settings.llm_model,
    }
    object.__setattr__(settings, "upload_dir", upload_dir)
    object.__setattr__(settings, "demo_mode", False)
    object.__setattr__(settings, "llm_base_url", "")
    object.__setattr__(settings, "llm_api_key", "")
    object.__setattr__(settings, "llm_model", "")

    app.dependency_overrides[get_auth_db] = override_auth_db
    app.dependency_overrides[get_system_db] = override_system_db
    app.dependency_overrides[get_db] = override_user_db
    original_lifespan_context = app.router.lifespan_context

    @asynccontextmanager
    async def isolated_lifespan(_app):
        # Every schema above is initialized explicitly inside runtime_root.
        yield

    app.router.lifespan_context = isolated_lifespan
    try:
        with TestClient(app) as client:
            yield client, runtime_root
    finally:
        app.router.lifespan_context = original_lifespan_context
        app.dependency_overrides.clear()
        auth_engine.dispose()
        system_engine.dispose()
        for engine in workspace_engines.values():
            engine.dispose()
        for name, value in previous_settings.items():
            object.__setattr__(settings, name, value)


def _csrf_headers(client: TestClient, **extra: str) -> dict[str, str]:
    token = client.cookies.get("study_csrf")
    assert token, "authenticated mutation must have a CSRF cookie"
    return {"X-CSRF-Token": token, **extra}


def _edit_tag(item: dict, *, revision_field: str = "revision") -> str:
    return f'"{item["navigation_key"]}:{item[revision_field]}"'


def test_reviewer_can_reproduce_the_complete_learning_loop_without_real_data(
    isolated_reviewer_client: tuple[TestClient, Path],
) -> None:
    client, runtime_root = isolated_reviewer_client
    real_user_data_dir = PROJECT_ROOT / "data" / "users"
    real_user_data_before = {
        path.name: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in real_user_data_dir.glob("*.db")
    } if real_user_data_dir.exists() else {}

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["service"] == "learning-assistant-api"

    registration = client.post(
        "/api/auth/register",
        json={
            "display_name": "评审测试同学",
            "email": "reviewer-smoke@example.test",
            "password": "review2026",
        },
    )
    assert registration.status_code == 201
    assert registration.json()["email"] == "reviewer-smoke@example.test"

    logout = client.post("/api/auth/logout", headers=_csrf_headers(client))
    assert logout.status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    login = client.post(
        "/api/auth/login",
        json={"email": "reviewer-smoke@example.test", "password": "review2026"},
    )
    assert login.status_code == 200

    course = client.post(
        "/api/courses",
        json={"name": "数据结构"},
        headers=_csrf_headers(client),
    )
    assert course.status_code == 201
    course_id = course.json()["id"]

    notice_text = (
        "课程：数据结构\n"
        "实验报告：完成图遍历实验，截止时间：2099年10月15日 20:00\n"
        "请保留来源片段以供人工复核。"
    )
    uploaded = client.post(
        "/api/materials/upload",
        data={"course_id": str(course_id), "material_type": "课程通知"},
        files={"files": ("数据结构-实验通知.txt", notice_text.encode("utf-8"), "text/plain")},
        headers=_csrf_headers(client),
    )
    assert uploaded.status_code == 201
    material = uploaded.json()[0]
    assert material["processing_status"] == "processed"
    assert material["extraction_status"] in {"ready", "needs_review"}

    saved_preview = client.get(f"/api/materials/{material['id']}/extraction")
    assert saved_preview.status_code == 200
    preview = saved_preview.json()
    assert preview["provider"] == "local-rules"
    assert preview["batch_id"]
    assert len(preview["tasks"]) == 1
    assert "图遍历实验" in preview["tasks"][0]["name"]
    assert preview["tasks"][0]["source_quote"] in notice_text

    confirmed = client.post(
        f"/api/materials/{material['id']}/extraction/confirm",
        json={
            "course_id": course_id,
            "material_type": "实验通知",
            "tags": ["实验", "DDL", "图遍历"],
            "tasks": preview["tasks"],
        },
        headers=_csrf_headers(
            client,
            **{"If-Match": _edit_tag({
                "navigation_key": preview["material_navigation_key"],
                "revision": preview["material_revision"],
            })},
        ),
    )
    assert confirmed.status_code == 200
    confirmation = confirmed.json()
    assert confirmation["status"] == "confirmed"
    assert len(confirmation["confirmed_task_ids"]) == 1

    searched = client.get("/api/materials", params={"q": "图遍历"})
    assert searched.status_code == 200
    assert len(searched.json()) == 1
    search_hit = searched.json()[0]
    assert search_hit["id"] == material["id"]
    assert "content" in search_hit["matched_fields"]
    assert search_hit["match_snippets"]

    task = client.get(f"/api/tasks/{confirmation['confirmed_task_ids'][0]}")
    assert task.status_code == 200
    completed = client.post(
        f"/api/tasks/{task.json()['id']}/complete",
        json={"actual_minutes": 45, "difficulty": 3},
        headers=_csrf_headers(client, **{"If-Match": _edit_tag(task.json())}),
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["actual_minutes"] == 45

    weekly_review = client.post(
        "/api/agent/weekly-review/refresh", headers=_csrf_headers(client)
    )
    assert weekly_review.status_code == 200
    assert weekly_review.json()["window_start"]
    assert weekly_review.json()["window_end"]

    exam_date = date.today() + timedelta(days=30)
    generated_plan = client.post(
        "/api/study-plans/generate",
        json={"course_id": course_id, "exam_date": exam_date.isoformat(), "daily_minutes": 30},
        headers=_csrf_headers(client),
    )
    assert generated_plan.status_code == 201
    plan = generated_plan.json()
    assert plan["items"]
    assert plan["material_count"] == 1

    tasks_csv = client.get("/api/exports/tasks.csv")
    materials_md = client.get("/api/exports/materials.md")
    plan_md = client.get(f"/api/exports/study-plans/{plan['id']}.md")
    tasks_ical = client.get("/api/exports/tasks.ics", params={"include_completed": True})
    assert tasks_csv.status_code == materials_md.status_code == plan_md.status_code == tasks_ical.status_code == 200
    assert tasks_csv.content.startswith(b"\xef\xbb\xbf")
    assert "图遍历实验" in tasks_csv.content.decode("utf-8-sig")
    assert "数据结构-实验通知.txt" in materials_md.text
    assert "复习清单" in plan_md.text
    calendar_text = tasks_ical.content.decode("utf-8")
    assert "BEGIN:VEVENT" in calendar_text
    assert "TZID=Asia/Shanghai" in calendar_text
    assert "TRIGGER:-P1D" in calendar_text

    assert (runtime_root / "auth.db").is_file()
    assert (runtime_root / "system.db").is_file()
    assert len(list((runtime_root / "user-data").glob("*.db"))) == 1
    assert len(list((runtime_root / "uploads").rglob("*.txt"))) == 1
    real_user_data_after = {
        path.name: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in real_user_data_dir.glob("*.db")
    } if real_user_data_dir.exists() else {}
    assert real_user_data_after == real_user_data_before

    print(f"isolated runtime evidence: {runtime_root}")
    print("workflow: register/login -> upload -> saved preview -> versioned confirm -> search -> complete -> review/plan -> CSV/Markdown/iCal")
