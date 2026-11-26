"""Email registration, browser-session and demo-mode endpoints."""

from __future__ import annotations

import secrets
import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth_database import get_auth_db
from app.config import settings
from app.models.user import AccountEmailCode, User, UserSession
from app.schemas.auth import (
    ChangePasswordRequest, ConfirmPassword, LoginRequest, RegisterRequest, RegistrationEmailRequest,
    ResetPasswordRequest, UserRead, VerifyRecoveryEmailRequest,
)
from app.services.auth import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    create_session,
    get_current_user,
    hash_password,
    hash_token,
    verify_login_password,
)
from app.services.signup_verification import (
    RESEND_DELAY, consume_account_code, consume_registration_code, email_codes_available,
    send_account_code, send_registration_code, verify_turnstile,
)


router = APIRouter(prefix="/api/auth", tags=["auth"])

DEMO_ACCOUNT_EMAIL = "demo@study.local"
DEMO_ACCOUNT_PASSWORD = "XuebanDemo2026"
RESET_PURPOSE = "找回密码"
VERIFY_PURPOSE = "验证找回邮箱"


def _allow_local_demo() -> bool:
    return settings.app_env.lower() in {"development", "test"}


def _seed_demo_workspace(workspace_key: str) -> None:
    """Fill one workspace with deterministic demo records; safe to repeat."""

    from app.database import _workspace_session_factory
    from app.services.demo_data import ensure_demo_data

    workspace_db = _workspace_session_factory(workspace_key)()
    try:
        ensure_demo_data(workspace_db)
        workspace_db.commit()
    finally:
        workspace_db.close()


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


def _require_available_email(db: Session, email: str) -> None:
    if email == DEMO_ACCOUNT_EMAIL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_RESERVED", "message": "这个邮箱用于演示模式，请使用自己的邮箱注册"},
        )
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_EXISTS", "message": "这个邮箱已经注册，可以直接登录"},
        )


@router.get("/config")
def auth_config(response: Response) -> dict[str, str | bool]:
    if settings.auth_turnstile_enabled and not settings.auth_turnstile_site_key:
        raise HTTPException(503, detail={"code": "TURNSTILE_UNAVAILABLE", "message": "人机验证暂不可用"})
    response.headers["Cache-Control"] = "no-store"
    return {
        "turnstile_site_key": settings.auth_turnstile_site_key if settings.auth_turnstile_enabled else "",
        "email_verification_required": settings.auth_email_verification_enabled,
        "password_recovery_available": email_codes_available(),
    }


@router.post("/register/code")
def request_registration_code(
    payload: RegistrationEmailRequest, response: Response, db: Session = Depends(get_auth_db)
) -> dict[str, int]:
    if not settings.auth_email_verification_enabled:
        raise HTTPException(404, detail={"code": "EMAIL_CODE_DISABLED", "message": "当前环境未启用邮箱验证码"})
    verify_turnstile(payload.turnstile_token, "register_code")
    _require_available_email(db, payload.email)
    response.headers["Cache-Control"] = "no-store"
    return {"retry_after_seconds": send_registration_code(db, payload.email)}


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_auth_db)) -> User:
    if settings.auth_email_verification_enabled:
        _require_available_email(db, payload.email)
        consume_registration_code(db, payload.email, payload.email_code)
    else:
        verify_turnstile(payload.turnstile_token, "register")
        _require_available_email(db, payload.email)
    claim_local_workspace = (
        settings.app_env.lower() in {"development", "test"}
        and (db.scalar(select(func.count(User.id)).where(User.is_demo.is_(False))) or 0) == 0
    )
    user = User(
        id=secrets.token_hex(16),
        email=payload.email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        email_verified=settings.auth_email_verification_enabled,
        workspace_key="legacy" if claim_local_workspace else secrets.token_hex(16),
        is_admin=claim_local_workspace,
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
    verify_turnstile(payload.turnstile_token, "login")
    user = db.scalar(select(User).where(User.email == payload.email))
    if not verify_login_password(user, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "邮箱或密码不正确"},
        )
    session_token, csrf_token, _session = create_session(db, user)
    _set_auth_cookies(response, session_token, csrf_token)
    return user


@router.post("/demo-login", response_model=UserRead)
def demo_login(response: Response, db: Session = Depends(get_auth_db)) -> User:
    """Find-or-create the shared demo account, seed its workspace, start a session.

    Satisfies the competition submission requirement that a login-protected
    work offers a test account or demo mode: judges reach a populated learning
    workspace in one click without registering. The demo account always uses
    its own isolated workspace and never administers the instance.
    """

    if not _allow_local_demo():
        raise HTTPException(
            status_code=404,
            detail={"code": "DEMO_DISABLED", "message": "当前环境不提供演示模式"},
        )

    user = db.scalar(select(User).where(User.email == DEMO_ACCOUNT_EMAIL))
    if user is None:
        user = User(
            id=secrets.token_hex(16),
            email=DEMO_ACCOUNT_EMAIL,
            display_name="演示同学",
            password_hash=hash_password(DEMO_ACCOUNT_PASSWORD),
            workspace_key=secrets.token_hex(16),
            is_admin=False,
            is_demo=True,
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            user = db.scalar(select(User).where(User.email == DEMO_ACCOUNT_EMAIL))
            if user is None:
                raise HTTPException(
                    status_code=500,
                    detail={"code": "DEMO_ACCOUNT_FAILED", "message": "演示账号创建失败，请稍后重试"},
                ) from None
    if not user.is_demo or user.is_admin or not re.fullmatch(r"[0-9a-f]{32}", user.workspace_key):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DEMO_ACCOUNT_CONFLICT",
                "message": "演示邮箱已关联到无法验证的旧账号，请用原密码登录；演示入口不会接管该账号。",
            },
        )
    _seed_demo_workspace(user.workspace_key)
    session_token, csrf_token, _session = create_session(db, user)
    _set_auth_cookies(response, session_token, csrf_token)
    return user


def _check_current_password(user: User, password: str) -> None:
    if user.is_demo:
        raise HTTPException(403, detail={"code": "DEMO_ACCOUNT", "message": "示例账号不支持修改安全设置"})
    if not verify_login_password(user, password):
        raise HTTPException(400, detail={"code": "INCORRECT_PASSWORD", "message": "当前密码不正确"})


def _save_password(db: Session, user: User, password: str) -> None:
    if verify_login_password(user, password):
        raise HTTPException(400, detail={"code": "PASSWORD_UNCHANGED", "message": "请使用与当前密码不同的新密码"})
    changed = db.execute(update(User).where(
        User.id == user.id, User.password_hash == user.password_hash,
    ).values(password_hash=hash_password(password)))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, detail={"code": "PASSWORD_CHANGED", "message": "账号凭据已更新，请重新登录或申请验证码"})
    db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    db.commit()


@router.post("/password/change", status_code=204)
def change_password(payload: ChangePasswordRequest, response: Response, user: User = Depends(get_current_user),
                    db: Session = Depends(get_auth_db)) -> None:
    _check_current_password(user, payload.current_password)
    _save_password(db, user, payload.new_password)
    _clear_auth_cookies(response)


def _require_recovery_mail() -> None:
    if not email_codes_available():
        raise HTTPException(503, detail={"code": "EMAIL_CODE_UNAVAILABLE", "message": "邮箱找回暂不可用，请稍后重试"})


@router.post("/recovery-email/code")
def request_recovery_email_verification(payload: ConfirmPassword, user: User = Depends(get_current_user),
                                        db: Session = Depends(get_auth_db)) -> dict[str, int]:
    _check_current_password(user, payload.current_password)
    _require_recovery_mail()
    if user.email_verified:
        raise HTTPException(409, detail={"code": "EMAIL_ALREADY_VERIFIED", "message": "找回邮箱已验证"})
    return {"retry_after_seconds": send_account_code(db, user, VERIFY_PURPOSE)}


@router.post("/recovery-email/verify", response_model=UserRead)
def verify_recovery_email(payload: VerifyRecoveryEmailRequest, user: User = Depends(get_current_user),
                          db: Session = Depends(get_auth_db)) -> User:
    _check_current_password(user, payload.current_password)
    _require_recovery_mail()
    consume_account_code(db, user, VERIFY_PURPOSE, payload.email_code)
    verified = db.execute(update(User).where(
        User.id == user.id, User.password_hash == user.password_hash,
    ).values(email_verified=True))
    if verified.rowcount != 1:
        db.rollback()
        raise HTTPException(409, detail={"code": "PASSWORD_CHANGED", "message": "账号凭据已更新，请重新登录"})
    # Enrollment is one-time. The first recovery request gets its own send budget.
    db.execute(delete(AccountEmailCode).where(AccountEmailCode.email == user.email))
    db.commit()
    db.refresh(user)
    return user


def _recovery_user(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(
        User.email == email, User.email_verified.is_(True), User.is_demo.is_(False),
    ))


def _deliver_reset_if_eligible(bind: Engine, email: str) -> None:
    with Session(bind) as db:
        user = _recovery_user(db, email)
        if user is not None:
            try:
                send_account_code(db, user, RESET_PURPOSE)
            except HTTPException:
                # Quotas and SMTP delivery outcomes are private to this mailbox.
                db.rollback()


@router.post("/password/reset/code", status_code=202)
def request_password_reset(payload: RegistrationEmailRequest, background: BackgroundTasks, response: Response,
                           db: Session = Depends(get_auth_db)) -> dict[str, int]:
    _require_recovery_mail()
    verify_turnstile(payload.turnstile_token, "password_reset")
    background.add_task(_deliver_reset_if_eligible, db.get_bind(), payload.email)
    response.headers["Cache-Control"] = "no-store"
    return {"retry_after_seconds": RESEND_DELAY}


@router.post("/password/reset", status_code=204)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_auth_db)) -> None:
    _require_recovery_mail()
    user = _recovery_user(db, payload.email)
    if user is None:
        raise HTTPException(400, detail={"code": "EMAIL_CODE_INVALID", "message": "验证码错误或已失效，请检查或重新获取"})
    consume_account_code(db, user, RESET_PURPOSE, payload.email_code)
    _save_password(db, user, payload.new_password)


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
