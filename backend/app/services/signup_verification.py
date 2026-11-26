"""Server-side Turnstile checks and single-use email challenges."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import smtplib
import ssl
import time
from email.errors import MessageError
from email.headerregistry import Address
from email.message import EmailMessage

import requests
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import AccountEmailCode, RegistrationEmailCode, User


logger = logging.getLogger(__name__)
SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
CODE_LIFETIME = 10 * 60
RESEND_DELAY = 60
SEND_WINDOW = 60 * 60
MAX_SENDS = 5
MAX_ATTEMPTS = 5
CodeTable = type[RegistrationEmailCode] | type[AccountEmailCode]


def verify_turnstile(token: str | None, action: str) -> None:
    if not settings.auth_turnstile_enabled:
        return
    if not (
        settings.auth_turnstile_site_key
        and settings.auth_turnstile_secret_key
        and settings.auth_turnstile_hostname
    ):
        raise HTTPException(503, detail={"code": "TURNSTILE_UNAVAILABLE", "message": "人机验证暂不可用"})
    if token:
        try:
            response = requests.post(
                SITEVERIFY_URL,
                data={"secret": settings.auth_turnstile_secret_key, "response": token},
                timeout=(3, 5),
            )
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError):
            raise HTTPException(
                503, detail={"code": "TURNSTILE_UNAVAILABLE", "message": "人机验证暂不可用，请稍后重试"}
            ) from None
        if (
            isinstance(result, dict)
            and result.get("success") is True
            and result.get("action") == action
            and result.get("hostname") == settings.auth_turnstile_hostname
        ):
            return
    raise HTTPException(400, detail={"code": "TURNSTILE_REQUIRED", "message": "请重新完成人机验证"})


def _code_digest(email: str, challenge_id: str, code: str) -> str:
    if len(settings.auth_email_code_secret) < 32:
        raise HTTPException(
            503, detail={"code": "EMAIL_CODE_UNAVAILABLE", "message": "邮箱验证暂不可用"}
        )
    return hmac.new(
        settings.auth_email_code_secret.encode(),
        f"{email}\n{challenge_id}\n{code}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _send_email_code(email: str, code: str, purpose: str = "注册") -> None:
    try:
        recipient = Address(addr_spec=email)
    except (ValueError, MessageError):
        raise HTTPException(400, detail={"code": "INVALID_EMAIL", "message": "请输入有效的邮箱地址"}) from None
    try:
        message = EmailMessage()
        message["From"] = Address(display_name="学伴管家", addr_spec=settings.auth_smtp_from)
        message["To"] = recipient
        message["Subject"] = f"学伴管家{purpose}验证码"
        message.set_content(f"你的{purpose}验证码为 {code}，10 分钟内有效。\n如果你没有发起此操作，可以忽略此邮件。")
        context = ssl.create_default_context()
        if settings.auth_smtp_starttls:
            client = smtplib.SMTP(settings.auth_smtp_host, settings.auth_smtp_port, timeout=8)
        else:
            client = smtplib.SMTP_SSL(
                settings.auth_smtp_host, settings.auth_smtp_port, timeout=8, context=context
            )
        with client:
            if settings.auth_smtp_starttls:
                client.starttls(context=context)
            client.login(settings.auth_smtp_username, settings.auth_smtp_password)
            client.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError, MessageError) as exc:
        logger.warning("verification_email_send_failed error_type=%s", type(exc).__name__)
        raise HTTPException(
            503, detail={"code": "EMAIL_CODE_UNAVAILABLE", "message": "暂时无法发送验证码，请稍后重试"}
        ) from None


def _rate_limited(wait_seconds: int) -> HTTPException:
    return HTTPException(
        429,
        detail={"code": "EMAIL_CODE_RATE_LIMITED", "message": f"发送过于频繁，请在 {wait_seconds} 秒后重试"},
        headers={"Retry-After": str(wait_seconds)},
    )


def email_codes_available() -> bool:
    return len(settings.auth_email_code_secret) >= 32 and all((
        settings.auth_smtp_host, settings.auth_smtp_username, settings.auth_smtp_password, settings.auth_smtp_from,
    ))


def send_registration_code(db: Session, email: str) -> int:
    return _issue_code(db, RegistrationEmailCode, email, email, "注册")


def _account_binding(user: User, purpose: str) -> str:
    return f"{purpose}\n{user.id}\n{user.password_hash}\n{user.email}"


def send_account_code(db: Session, user: User, purpose: str) -> int:
    return _issue_code(db, AccountEmailCode, user.email, _account_binding(user, purpose), purpose)


def _issue_code(db: Session, model: CodeTable, email: str, binding: str, purpose: str) -> int:
    if not email_codes_available():
        raise HTTPException(
            503, detail={"code": "EMAIL_CODE_UNAVAILABLE", "message": "邮箱验证暂不可用"}
        )
    now = int(time.time())
    previous = db.get(model, email)
    window_start = now
    sends_in_window = 0
    if previous is not None:
        if previous.retry_at > now:
            raise _rate_limited(previous.retry_at - now)
        if previous.window_start + SEND_WINDOW > now:
            window_start = previous.window_start
            sends_in_window = previous.sends_in_window
            if sends_in_window >= MAX_SENDS:
                raise _rate_limited(window_start + SEND_WINDOW - now)

    challenge_id = secrets.token_hex(16)
    code = f"{secrets.randbelow(1_000_000):06d}"
    values = {
        "challenge_id": challenge_id,
        "digest": _code_digest(binding, challenge_id, code),
        "delivered": False,
        "expires_at": now + CODE_LIFETIME,
        "retry_at": now + RESEND_DELAY,
        "window_start": window_start,
        "sends_in_window": sends_in_window + 1,
        "attempts_remaining": MAX_ATTEMPTS,
    }
    if previous is None:
        db.add(model(email=email, **values))
    else:
        reserved = db.execute(
            update(model)
            .where(model.email == email, model.challenge_id == previous.challenge_id)
            .values(**values)
        )
        if reserved.rowcount != 1:
            db.rollback()
            raise _rate_limited(RESEND_DELAY)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _rate_limited(RESEND_DELAY) from None

    _send_email_code(email, code, purpose)
    delivered = db.execute(
        update(model)
        .where(model.email == email, model.challenge_id == challenge_id)
        .values(delivered=True)
    )
    db.commit()
    if delivered.rowcount != 1:
        raise HTTPException(
            409, detail={"code": "EMAIL_CODE_SUPERSEDED", "message": "已申请新的验证码，请使用最新邮件"}
        )
    return RESEND_DELAY


def consume_registration_code(db: Session, email: str, code: str | None) -> None:
    _consume_code(db, RegistrationEmailCode, email, email, code)


def consume_account_code(db: Session, user: User, purpose: str, code: str) -> None:
    _consume_code(db, AccountEmailCode, user.email, _account_binding(user, purpose), code)


def _consume_code(db: Session, model: CodeTable, email: str, binding: str, code: str | None) -> None:
    invalid = HTTPException(
        400, detail={"code": "EMAIL_CODE_INVALID", "message": "验证码错误或已失效，请检查或重新获取"}
    )
    if not code:
        raise invalid
    now = int(time.time())
    challenge = db.get(model, email)
    if (
        challenge is None
        or not challenge.delivered
        or challenge.expires_at <= now
        or challenge.attempts_remaining <= 0
    ):
        raise invalid
    active_challenge = update(model).where(
        model.email == email,
        model.challenge_id == challenge.challenge_id,
        model.delivered.is_(True),
        model.expires_at > now,
        model.attempts_remaining > 0,
    )
    if not hmac.compare_digest(challenge.digest, _code_digest(binding, challenge.challenge_id, code)):
        db.execute(active_challenge.values(attempts_remaining=model.attempts_remaining - 1))
        db.commit()
        raise invalid
    # The caller commits consumption together with the authorized account change.
    consumed = db.execute(active_challenge.values(delivered=False, digest="", attempts_remaining=0))
    if consumed.rowcount != 1:
        raise invalid
