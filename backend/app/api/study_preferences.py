"""Single-user learning-capacity preference API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.utils import commit_or_rollback
from app.models.study_preference import StudyPreference
from app.schemas.study_preference import StudyPreferenceRead, StudyPreferenceUpdate
from app.services.study_preferences import get_or_create_preference

router = APIRouter(prefix="/api/study-preferences", tags=["study-preferences"])


@router.get("", response_model=StudyPreferenceRead)
def get_study_preferences(db: Session = Depends(get_db)) -> StudyPreference:
    return get_or_create_preference(db)


@router.put("", response_model=StudyPreferenceRead)
def update_study_preferences(payload: StudyPreferenceUpdate, db: Session = Depends(get_db)) -> StudyPreference:
    preference = get_or_create_preference(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(preference, field, value)
    commit_or_rollback(db)
    db.refresh(preference)
    return preference


@router.post("/reset", response_model=StudyPreferenceRead)
def reset_study_preferences(db: Session = Depends(get_db)) -> StudyPreference:
    db.execute(delete(StudyPreference))
    preference = StudyPreference(id=1)
    db.add(preference)
    db.commit()
    db.refresh(preference)
    return preference
