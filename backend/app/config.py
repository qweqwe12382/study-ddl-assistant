"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv, set_key


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


def llm_settings_payload() -> dict[str, object]:
    api_key = settings.llm_api_key.strip()
    return {
        "base_url": settings.llm_base_url or None,
        "model": settings.llm_model or None,
        "api_key_configured": bool(api_key),
        "api_key_hint": f"{api_key[:4]}…{api_key[-4:]}" if len(api_key) >= 8 else ("已配置" if api_key else None),
        "timeout_seconds": settings.llm_timeout_seconds,
        "max_retries": settings.llm_max_retries,
    }


def update_llm_settings(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
    clear_api_key: bool = False,
) -> dict[str, object]:
    env_path = PROJECT_ROOT / ".env"
    values: dict[str, str] = {}
    if base_url is not None:
        values["LLM_BASE_URL"] = base_url
        object.__setattr__(settings, "llm_base_url", base_url)
    if api_key is not None or clear_api_key:
        values["LLM_API_KEY"] = "" if clear_api_key else (api_key or "")
        object.__setattr__(settings, "llm_api_key", values["LLM_API_KEY"])
    if model is not None:
        values["LLM_MODEL"] = model
        object.__setattr__(settings, "llm_model", model)
    if timeout_seconds is not None:
        values["LLM_TIMEOUT_SECONDS"] = str(timeout_seconds)
        object.__setattr__(settings, "llm_timeout_seconds", timeout_seconds)
    if max_retries is not None:
        values["LLM_MAX_RETRIES"] = str(max_retries)
        object.__setattr__(settings, "llm_max_retries", max_retries)

    env_path.touch(exist_ok=True)
    for key, value in values.items():
        set_key(str(env_path), key, value, quote_mode="auto")
    return llm_settings_payload()


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
