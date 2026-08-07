from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.course import Course
from app.schemas.course import CourseCreate, CourseRead, CourseUpdate
from app.api.utils import commit_or_rollback

router = APIRouter(prefix="/api/courses", tags=["courses"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "COURSE_NOT_FOUND", "message": "课程不存在"})


@router.get("", response_model=list[CourseRead])
def list_courses(db: Session = Depends(get_db)) -> list[Course]:
    return list(db.scalars(select(Course).order_by(Course.created_at.desc())).all())


@router.post("", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
def create_course(payload: CourseCreate, db: Session = Depends(get_db)) -> Course:
    course = Course(**payload.model_dump())
    db.add(course)
    commit_or_rollback(db)
    db.refresh(course)
    return course


@router.get("/{course_id}", response_model=CourseRead)
def get_course(course_id: int, db: Session = Depends(get_db)) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise _not_found()
    return course


@router.patch("/{course_id}", response_model=CourseRead)
def update_course(course_id: int, payload: CourseUpdate, db: Session = Depends(get_db)) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise _not_found()
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(course, field, value)
    commit_or_rollback(db)
    db.refresh(course)
    return course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: int, db: Session = Depends(get_db)) -> None:
    course = db.get(Course, course_id)
    if course is None:
        raise _not_found()
    db.delete(course)
    commit_or_rollback(db)
