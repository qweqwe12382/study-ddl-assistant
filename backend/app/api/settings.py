from fastapi import APIRouter, Depends

from app.config import llm_settings_payload, update_llm_settings
from app.schemas.settings import LLMSettingsRead, LLMSettingsUpdate
from app.services.auth import require_admin_user


router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[Depends(require_admin_user)])


@router.get("/llm", response_model=LLMSettingsRead)
def get_llm_settings() -> LLMSettingsRead:
    return LLMSettingsRead.model_validate(llm_settings_payload())


@router.put("/llm", response_model=LLMSettingsRead)
def save_llm_settings(payload: LLMSettingsUpdate) -> LLMSettingsRead:
    updated = update_llm_settings(**payload.model_dump())
    return LLMSettingsRead.model_validate(updated)
