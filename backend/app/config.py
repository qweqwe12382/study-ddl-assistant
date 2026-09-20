"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _parse_origins(value: str) -> tuple[str, ...]:
    return tuple(origin.strip() for origin in value.split(",") if origin.strip())


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
    auth_database_url: str = os.getenv("AUTH_DATABASE_URL", "sqlite:///./data/auth.db")
    user_database_dir: Path = _resolve_path(os.getenv("USER_DATABASE_DIR", "data/users"))
    auth_session_days: int = int(os.getenv("AUTH_SESSION_DAYS", "30"))
    auth_cookie_secure: bool = os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"
    upload_dir: Path = _resolve_path(os.getenv("UPLOAD_DIR", "data/uploads"))
    max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20"))
    max_upload_files: int = int(os.getenv("MAX_UPLOAD_FILES", "10"))
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "")
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "2"))
    ocr_mode: str = os.getenv("OCR_MODE", "local")
    demo_mode: bool = os.getenv("DEMO_MODE", "false").lower() == "true"
    cors_origins: tuple[str, ...] = _parse_origins(
        os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    )


settings = Settings()


def ensure_runtime_directories() -> None:
    """Create directories needed by the local SQLite/upload runtime."""

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.user_database_dir.mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "data" / "demo").mkdir(parents=True, exist_ok=True)


def database_path() -> Path | None:
    """Return the local SQLite path when the configured URL points to SQLite."""

    prefix = "sqlite:///"
    if not settings.database_url.startswith(prefix):
        return None
    raw_path = settings.database_url[len(prefix) :]
    path = Path(raw_path)
    return path if path.is_absolute() else PROJECT_ROOT / path
