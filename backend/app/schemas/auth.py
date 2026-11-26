"""Public account API contracts."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from app.schemas.timestamps import UtcDateTime


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class RegistrationEmailRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(min_length=5, max_length=254)
    turnstile_token: str | None = Field(default=None, max_length=2048, repr=False)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("请输入有效的邮箱地址")
        return normalized


def _password_policy(value: str) -> str:
    if value.isspace() or value.strip() != value:
        raise ValueError("密码首尾不能包含空格")
    if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
        raise ValueError("密码需同时包含字母和数字")
    return value


NewPassword = Annotated[str, Field(min_length=8, max_length=128, repr=False), AfterValidator(_password_policy)]
EmailCode = Annotated[str, Field(pattern=r"^[0-9]{6}$", repr=False)]


class RegisterRequest(RegistrationEmailRequest):
    password: NewPassword
    display_name: str = Field(min_length=1, max_length=40)
    email_code: str | None = Field(default=None, pattern=r"^[0-9]{6}$", repr=False)

class ConfirmPassword(BaseModel):
    current_password: str = Field(min_length=1, max_length=128, repr=False)


class ChangePasswordRequest(ConfirmPassword):
    new_password: NewPassword


class VerifyRecoveryEmailRequest(ConfirmPassword):
    email_code: EmailCode


class ResetPasswordRequest(RegistrationEmailRequest):
    model_config = ConfigDict(str_strip_whitespace=False)
    new_password: NewPassword
    email_code: EmailCode


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)
    turnstile_token: str | None = Field(default=None, max_length=2048, repr=False)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.casefold()


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    is_admin: bool
    is_demo: bool
    email_verified: bool
    created_at: UtcDateTime
