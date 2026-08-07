from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CourseBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    teacher: str | None = Field(default=None, max_length=120)
    semester: str | None = Field(default=None, max_length=40)
    color: str | None = Field(default=None, max_length=20)


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=120)
    teacher: str | None = Field(default=None, max_length=120)
    semester: str | None = Field(default=None, max_length=40)
    color: str | None = Field(default=None, max_length=20)


class CourseRead(CourseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
