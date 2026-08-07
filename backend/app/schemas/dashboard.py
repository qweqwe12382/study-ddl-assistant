from pydantic import BaseModel, Field

from app.schemas.material import MaterialSearchRead
from app.schemas.task import TaskRead


class DashboardTaskRead(TaskRead):
    course_name: str | None = None
    material_name: str | None = None
    source_available: bool = False


class DashboardMaterialRead(MaterialSearchRead):
    course_name: str | None = None


class DashboardRead(BaseModel):
    active_task_count: int = Field(ge=0)
    due_soon_count: int = Field(ge=0)
    overdue_count: int = Field(ge=0)
    completed_task_count: int = Field(ge=0)
    materials_count: int = Field(ge=0)
    courses_count: int = Field(ge=0)
    upcoming_tasks: list[DashboardTaskRead] = Field(default_factory=list)
    overdue_tasks: list[DashboardTaskRead] = Field(default_factory=list)
    recent_materials: list[DashboardMaterialRead] = Field(default_factory=list)
    next_action: str | None = None
