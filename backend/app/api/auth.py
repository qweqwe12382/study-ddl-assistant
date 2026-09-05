"""Email registration and browser-session endpoints."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth_database import get_auth_db
from app.config import settings
from app.models.user import User, UserSession
from app.schemas.auth import LoginRequest, RegisterRequest, UserRead
from app.services.auth import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    create_session,
    get_current_user,
    hash_password,
    hash_token,
    verify_login_password,
)


router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_auth_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    max_age = settings.auth_session_days * 24 * 60 * 60
    common = {
        "max_age": max_age,
        "secure": settings.auth_cookie_secure,
        "samesite": "lax",
        "path": "/",
    }
    response.set_cookie(SESSION_COOKIE, session_token, httponly=True, **common)
    response.set_cookie(CSRF_COOKIE, csrf_token, httponly=False, **common)
    response.headers["Cache-Control"] = "no-store"


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", samesite="lax")
    response.delete_cookie(CSRF_COOKIE, path="/", samesite="lax")
    response.headers["Cache-Control"] = "no-store"


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_auth_db)) -> User:
    if db.scalar(select(User.id).where(User.email == payload.email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_EXISTS", "message": "这个邮箱已经注册，可以直接登录"},
        )
    is_first_user = (db.scalar(select(func.count(User.id))) or 0) == 0
    user = User(
        id=secrets.token_hex(16),
        email=payload.email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        workspace_key="legacy" if is_first_user else secrets.token_hex(16),
        is_admin=is_first_user,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_EXISTS", "message": "这个邮箱已经注册，可以直接登录"},
        ) from exc
    db.refresh(user)
    session_token, csrf_token, _session = create_session(db, user)
    _set_auth_cookies(response, session_token, csrf_token)
    return user


@router.post("/login", response_model=UserRead)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_auth_db)) -> User:
    user = db.scalar(select(User).where(User.email == payload.email))
    if not verify_login_password(user, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "邮箱或密码不正确"},
        )
    session_token, csrf_token, _session = create_session(db, user)
    _set_auth_cookies(response, session_token, csrf_token)
    return user


@router.get("/me", response_model=UserRead)
def me(response: Response, current_user: User = Depends(get_current_user)) -> User:
    response.headers["Cache-Control"] = "no-store"
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_auth_db),
) -> None:
    del current_user
    raw_token = request.cookies.get(SESSION_COOKIE)
    if raw_token:
        session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(raw_token)))
        if session is not None:
            db.delete(session)
            db.commit()
    _clear_auth_cookies(response)
