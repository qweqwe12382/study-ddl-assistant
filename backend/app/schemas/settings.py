from pydantic import BaseModel, ConfigDict, Field


class LLMSettingsRead(BaseModel):
    model_config = ConfigDict(extra="ignore")

    base_url: str | None = None
    model: str | None = None
    api_key_configured: bool
    api_key_hint: str | None = None
    timeout_seconds: float = Field(ge=1, le=300)
    max_retries: int = Field(ge=0, le=5)


class LLMSettingsUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=200)
    timeout_seconds: float | None = Field(default=None, ge=1, le=300)
    max_retries: int | None = Field(default=None, ge=0, le=5)
    clear_api_key: bool = False
