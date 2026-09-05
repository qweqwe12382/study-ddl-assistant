"""Password hashing and cookie-session authentication."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth_database import get_auth_db
from app.config import settings
from app.models.user import User, UserSession
from app.time import as_utc, utc_now


SESSION_COOKIE = "study_session"
CSRF_COOKIE = "study_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=_b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32
        )
        return hmac.compare_digest(actual, _b64decode(expected))
    except (ValueError, TypeError):
        return False


# Unknown emails still run the same deliberately expensive password check, so
# the login endpoint does not provide a cheap account-existence timing signal.
_DUMMY_PASSWORD_HASH = hash_password("study-account-timing-placeholder-2026")


def verify_login_password(user: User | None, password: str) -> bool:
    encoded = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_matches = verify_password(password, encoded)
    return user is not None and password_matches


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, user: User) -> tuple[str, str, UserSession]:
    now = utc_now()
    db.execute(delete(UserSession).where(UserSession.expires_at <= now))
    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(24)
    session = UserSession(
        id=secrets.token_hex(16),
        user_id=user.id,
        token_hash=hash_token(session_token),
        csrf_hash=hash_token(csrf_token),
        expires_at=now + timedelta(days=settings.auth_session_days),
    )
    db.add(session)
    db.commit()
    return session_token, csrf_token, session


def authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "AUTH_REQUIRED", "message": "登录已失效，请重新登录"},
    )


def get_current_user(request: Request, db: Session = Depends(get_auth_db)) -> User:
    raw_token = request.cookies.get(SESSION_COOKIE)
    if not raw_token:
        raise authentication_error()
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(raw_token)))
    now = utc_now()
    if session is None or as_utc(session.expires_at) <= now:
        if session is not None:
            db.delete(session)
            db.commit()
        raise authentication_error()
    if request.method.upper() not in SAFE_METHODS:
        supplied = request.headers.get(CSRF_HEADER, "")
        cookie_value = request.cookies.get(CSRF_COOKIE, "")
        valid = bool(supplied and cookie_value and hmac.compare_digest(supplied, cookie_value))
        valid = valid and hmac.compare_digest(hash_token(supplied), session.csrf_hash)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "CSRF_INVALID", "message": "页面安全校验已失效，请刷新后重试"},
            )
    user = db.get(User, session.user_id)
    if user is None:
        raise authentication_error()
    if (now - as_utc(session.last_seen_at)).total_seconds() >= 3600:
        session.last_seen_at = now
        db.commit()
    return user


def require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ADMIN_REQUIRED", "message": "外部 AI 配置仅由实例管理员维护"},
        )
    return current_user
