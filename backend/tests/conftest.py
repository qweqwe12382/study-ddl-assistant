from collections.abc import Generator
import sys
from pathlib import Path

# Keep the documented `python -m pytest backend/tests -q` command working
# without requiring callers to set PYTHONPATH first.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, get_db
from app.config import settings
from app.main import app


@pytest.fixture
def isolated_upload_dir(tmp_path):
    previous = settings.upload_dir
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    object.__setattr__(settings, "upload_dir", upload_dir)
    try:
        yield upload_dir
    finally:
        object.__setattr__(settings, "upload_dir", previous)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    # Use an in-memory database so tests do not depend on Windows temp-folder
    # permissions or leave test database files in the workspace.
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def _enable_test_foreign_keys(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=test_engine)
    testing_session = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    test_engine.dispose()
