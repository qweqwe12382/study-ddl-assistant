from datetime import datetime
from pathlib import Path
import secrets
import logging

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.utils import commit_or_rollback, require_entity
from app.models.agent import AgentEvent
from app.models.course import Course
from app.models.material import Material
from app.models.task import Task
from app.schemas.extraction import (
    ExtractionConfirm,
    ExtractionPolicyRead,
    ExtractionProviderOption,
    ExtractionRead,
    ExtractionRequest,
)
from app.schemas.material import MaterialManualCreate, MaterialRead, MaterialSearchRead, MaterialUpdate
from app.config import settings
from app.services.file_parser import ALLOWED_FILE_TYPES, FileProcessingError, PreparedUpload, extract_text, prepare_upload
from app.services.extraction import ExtractionError, extract_material, mark_extraction_failed, stored_result
from app.services.agent_feedback import create_plan_delta_candidates
from app.services.llm_provider import external_provider_available
from app.services.edit_concurrency import check_edit_precondition
from app.models.user import User
from app.time import deadline_to_utc, utc_now
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/materials", tags=["materials"])
logger = logging.getLogger("learning_assistant.materials")


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "MATERIAL_NOT_FOUND", "message": "资料不存在"})


def _validate_course(db: Session, course_id: int | None) -> None:
    require_entity(db, Course, course_id, code="COURSE_NOT_FOUND", message="关联课程不存在")


def _resolve_stored_path(material: Material) -> Path | None:
    if not material.stored_path:
        return None
    path = (settings.upload_dir / material.stored_path).resolve()
    upload_root = settings.upload_dir.resolve()
    if upload_root not in path.parents:
        raise HTTPException(status_code=400, detail={"code": "INVALID_FILE_PATH", "message": "文件路径无效"})
    return path


def _stored_path(material: Material) -> Path:
    path = _resolve_stored_path(material)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "原始文件不存在"})
    return path


def _write_atomically(target: Path, content: bytes) -> None:
    temporary = target.with_name(f".{target.name}.{secrets.token_hex(8)}.part")
    try:
        temporary.write_bytes(content)
        temporary.replace(target)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def _parse_and_update(material: Material, prepared: PreparedUpload, db: Session) -> None:
    material.file_type = prepared.file_type
    material.file_size = len(prepared.content)
    material.content_hash = prepared.content_hash
    material.processing_status = "processing"
    material.processing_error = None
    material.extraction_status = "not_started"
    material.extraction_result = None
    material.extraction_provider = None
    material.extraction_error = None
    material.extracted_at = None
    try:
        material.extracted_text = extract_text(prepared.file_type, prepared.content)
        material.processing_status = "processed"
    except FileProcessingError as error:
        material.extracted_text = None
        material.processing_status = "failed"
        material.processing_error = error.message
    db.add(material)


def _auto_extract_local(material: Material) -> None:
    """Run the local candidate extractor after a successful file parse.

    Upload and retry must remain successful when candidate extraction fails. The
    parser result is still useful to the user, so extraction failure is stored on
    the material instead of aborting the surrounding upload transaction. The
    provider name is explicit here to prevent an automatic path from ever
    selecting an externally configured provider.
    """

    if material.processing_status != "processed":
        return
    try:
        extract_material(material, "local-rules")
    except ExtractionError as error:
        material.extraction_provider = "local-rules"
        mark_extraction_failed(material, error)
    except Exception:
        logger.exception("Local extraction failed for material %s", material.original_filename)
        material.extraction_provider = "local-rules"
        mark_extraction_failed(
            material,
            ExtractionError("LOCAL_EXTRACTION_FAILED", "本地规则抽取失败，请稍后重试"),
        )


def _match_snippets(text: str, keyword: str, *, radius: int = 80) -> list[str]:
    if not text or not keyword:
        return []
    lowered = text.casefold()
    target = keyword.casefold()
    snippets: list[str] = []
    start = 0
    while len(snippets) < 3:
        position = lowered.find(target, start)
        if position < 0:
            break
        left = max(0, position - radius)
        right = min(len(text), position + len(keyword) + radius)
        prefix = "…" if left else ""
        suffix = "…" if right < len(text) else ""
        snippets.append(f"{prefix}{text[left:right].strip()}{suffix}")
        start = position + len(keyword)
    return snippets


def _search_material(material: Material, keyword: str | None) -> MaterialSearchRead:
    result = MaterialSearchRead.model_validate(material)
    if not keyword:
        return result
    searchable = {
        "filename": material.original_filename or "",
        "summary": material.summary or "",
        "content": material.extracted_text or "",
        "tags": " ".join(material.tags or []),
    }
    matched_fields = [name for name, value in searchable.items() if keyword.casefold() in value.casefold()]
    snippets = _match_snippets(searchable["content"], keyword)
    if not snippets and "summary" in matched_fields:
        snippets = _match_snippets(searchable["summary"], keyword)
    return result.model_copy(update={"matched_fields": matched_fields, "match_snippets": snippets})


@router.get("", response_model=list[MaterialSearchRead])
def list_materials(
    q: str | None = Query(default=None, max_length=100),
    course_id: int | None = Query(default=None),
    material_type: str | None = Query(default=None, max_length=50),
    processing_status: str | None = Query(default=None, max_length=30),
    tag: str | None = Query(default=None, max_length=50),
    db: Session = Depends(get_db),
) -> list[MaterialSearchRead]:
    statement = select(Material).order_by(Material.created_at.desc())
    if course_id is not None:
        statement = statement.where(Material.course_id == course_id)
    if material_type:
        statement = statement.where(Material.material_type == material_type)
    if processing_status:
        statement = statement.where(Material.processing_status == processing_status)
    materials = list(db.scalars(statement).all())
    keyword = q.strip() if q else None
    normalized_tag = tag.strip().casefold() if tag else None
    results: list[MaterialSearchRead] = []
    for material in materials:
        if normalized_tag and not any(normalized_tag == item.casefold() for item in (material.tags or [])):
            continue
        result = _search_material(material, keyword)
        if keyword and not result.matched_fields:
            continue
        results.append(result)
    return results


@router.post("", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
def create_material(payload: MaterialManualCreate, db: Session = Depends(get_db)) -> Material:
    require_entity(
        db,
        Course,
        payload.course_id,
        code="COURSE_NOT_FOUND",
        message="关联课程不存在",
    )
    material_data = payload.model_dump()
    material_data["source_time"] = deadline_to_utc(payload.source_time) if payload.source_time is not None else utc_now()
    if payload.extracted_text:
        material_data["processing_status"] = "processed"
    material = Material(**material_data)
    db.add(material)
    commit_or_rollback(db)
    db.refresh(material)
    return material


@router.get("/upload-policy")
def upload_policy() -> dict[str, object]:
    return {
        "max_upload_size_mb": settings.max_upload_size_mb,
        "max_upload_files": settings.max_upload_files,
        "extensions": sorted(ALLOWED_FILE_TYPES),
    }


@router.get("/extraction-policy", response_model=ExtractionPolicyRead)
def extraction_policy() -> ExtractionPolicyRead:
    external_available = external_provider_available()
    return ExtractionPolicyRead(
        providers=[
            ExtractionProviderOption(
                id="local-rules",
                label="本地规则",
                description="在本机使用关键词和日期规则，不发送资料正文。",
                available=True,
                sends_data_externally=False,
            ),
            ExtractionProviderOption(
                id="openai-compatible",
                label="外部 AI API",
                description="使用后端配置的 OpenAI-compatible API 辅助理解复杂通知。",
                available=external_available,
                sends_data_externally=True,
                model=settings.llm_model or None,
            ),
        ]
    )


@router.post("/upload", response_model=list[MaterialRead], status_code=status.HTTP_201_CREATED)
def upload_materials(
    files: list[UploadFile] = File(...),
    course_id: int | None = Form(default=None),
    material_type: str | None = Form(default=None),
    source_time: datetime | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Material]:
    """Store and parse one or more supported learning-material files."""

    if not files:
        raise HTTPException(status_code=400, detail={"code": "NO_FILES", "message": "请选择至少一个文件"})
    if len(files) > settings.max_upload_files:
        raise HTTPException(
            status_code=400,
            detail={"code": "TOO_MANY_FILES", "message": f"一次最多上传 {settings.max_upload_files} 个文件"},
        )
    _validate_course(db, course_id)
    # Relative deadlines belong to the notification's reference instant, not
    # the date of a later extraction/retry. Naive input denotes Shanghai time.
    reference_time = deadline_to_utc(source_time) if source_time is not None else utc_now()

    prepared_files: list[PreparedUpload] = []
    existing_hashes = set(db.scalars(select(Material.content_hash).where(Material.content_hash.is_not(None))).all())
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    for upload in files:
        try:
            prepared = prepare_upload(upload.filename, upload.content_type, upload.file.read(max_bytes + 1))
        except FileProcessingError as error:
            raise HTTPException(status_code=400, detail={"code": error.code, "message": error.message}) from error
        if prepared.content_hash in existing_hashes or any(item.content_hash == prepared.content_hash for item in prepared_files):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "DUPLICATE_FILE", "message": f"文件“{prepared.original_filename}”已上传过"},
            )
        prepared_files.append(prepared)

    materials: list[Material] = []
    written_paths: list[Path] = []
    workspace_prefix = "" if current_user.workspace_key == "legacy" else current_user.workspace_key
    workspace_upload_dir = settings.upload_dir / workspace_prefix
    workspace_upload_dir.mkdir(parents=True, exist_ok=True)
    try:
        for prepared in prepared_files:
            stored_name = f"{secrets.token_hex(16)}.{prepared.file_type}"
            stored_path = str(Path(workspace_prefix) / stored_name) if workspace_prefix else stored_name
            target = settings.upload_dir / stored_path
            _write_atomically(target, prepared.content)
            written_paths.append(target)
            material = Material(
                course_id=course_id,
                original_filename=prepared.original_filename,
                stored_path=stored_path,
                file_type=prepared.file_type,
                material_type=material_type or None,
                source_time=reference_time,
                tags=[],
                processing_status="pending",
            )
            _parse_and_update(material, prepared, db)
            _auto_extract_local(material)
            materials.append(material)
        commit_or_rollback(db)
    except HTTPException:
        for path in written_paths:
            path.unlink(missing_ok=True)
        raise
    except OSError as exc:
        db.rollback()
        for path in written_paths:
            path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail={"code": "FILE_STORAGE_ERROR", "message": "文件保存失败，请稍后重试"}) from exc
    except Exception:
        db.rollback()
        for path in written_paths:
            path.unlink(missing_ok=True)
        raise

    for material in materials:
        db.refresh(material)
    return materials


@router.get("/{material_id}", response_model=MaterialRead)
def get_material(material_id: int, db: Session = Depends(get_db)) -> Material:
    material = db.get(Material, material_id)
    if material is None:
        raise _not_found()
    return material


@router.get("/{material_id}/file")
def download_material(material_id: int, db: Session = Depends(get_db)) -> FileResponse:
    material = db.get(Material, material_id)
    if material is None:
        raise _not_found()
    return FileResponse(_stored_path(material), filename=material.original_filename, media_type=None)


@router.post("/{material_id}/retry", response_model=MaterialRead)
def retry_material(material_id: int, db: Session = Depends(get_db), if_match: str | None = Header(default=None)) -> Material:
    material = db.get(Material, material_id)
    if material is None:
        raise _not_found()
    check_edit_precondition(db, material, if_match)
    if material.extraction_status == "confirmed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EXTRACTION_ALREADY_CONFIRMED",
                "message": "该资料的抽取结果已经确认，不能通过重试覆盖已确认快照",
            },
        )
    path = _stored_path(material)
    content = path.read_bytes()
    try:
        stored_type = Path(material.stored_path or "").suffix.lower().lstrip(".")
        prepared = prepare_upload(f"retry.{stored_type}", None, content)
    except FileProcessingError as error:
        material.processing_status = "failed"
        material.processing_error = error.message
        commit_or_rollback(db)
        db.refresh(material)
        return material
    _parse_and_update(material, prepared, db)
    _auto_extract_local(material)
    commit_or_rollback(db)
    db.refresh(material)
    return material


def _extraction_response(material: Material) -> ExtractionRead:
    result = stored_result(material)
    payload = result.model_dump()
    stored = material.extraction_result or {}
    payload.update(
        {
            "material_id": material.id,
            "material_navigation_key": material.navigation_key,
            "material_revision": material.revision,
            "status": material.extraction_status,
            "provider": material.extraction_provider,
            "error": material.extraction_error,
            "extracted_at": material.extracted_at,
            "confirmed_task_ids": stored.get("confirmed_task_ids", []),
            "confirmed_task_refs": stored.get("confirmed_task_refs", []),
        }
    )
    return ExtractionRead.model_validate(payload)


@router.post("/{material_id}/extract", response_model=ExtractionRead)
def extract_material_endpoint(
    material_id: int,
    payload: ExtractionRequest | None = None,
    db: Session = Depends(get_db),
    if_match: str | None = Header(default=None),
) -> ExtractionRead:
    material = db.get(Material, material_id)
    if material is None:
        raise _not_found()
    check_edit_precondition(db, material, if_match)
    try:
        extract_material(material, payload.provider if payload else None)
    except ExtractionError as error:
        if error.code != "EXTRACTION_ALREADY_CONFIRMED":
            mark_extraction_failed(material, error)
            commit_or_rollback(db)
        status_code = 409 if error.code == "EXTRACTION_ALREADY_CONFIRMED" else 422
        raise HTTPException(status_code=status_code, detail={"code": error.code, "message": error.message}) from error
    commit_or_rollback(db)
    db.refresh(material)
    return _extraction_response(material)


@router.get("/{material_id}/extraction", response_model=ExtractionRead)
def get_extraction(material_id: int, db: Session = Depends(get_db)) -> ExtractionRead:
    material = db.get(Material, material_id)
    if material is None:
        raise _not_found()
    try:
        return _extraction_response(material)
    except ExtractionError as error:
        raise HTTPException(status_code=404, detail={"code": error.code, "message": error.message}) from error


def _resolve_candidate_course(db: Session, material: Material, candidate, default_course_id: int | None) -> int | None:
    if candidate.course_id is not None:
        require_entity(db, Course, candidate.course_id, code="COURSE_NOT_FOUND", message="关联课程不存在")
        return candidate.course_id
    if candidate.course_name:
        course = db.scalar(select(Course).where(Course.name == candidate.course_name.strip()))
        if course:
            return course.id
    return default_course_id if default_course_id is not None else material.course_id


def confirm_extraction(material_id: int, payload: ExtractionConfirm, db: Session, if_match: str | None = None) -> ExtractionRead:
    material = db.get(Material, material_id)
    if material is None:
        raise _not_found()
    check_edit_precondition(db, material, if_match)
    if material.extraction_status == "confirmed":
        raise HTTPException(status_code=409, detail={"code": "EXTRACTION_ALREADY_CONFIRMED", "message": "该资料的抽取结果已经确认"})
    try:
        stored = stored_result(material)
    except ExtractionError as error:
        raise HTTPException(status_code=404, detail={"code": error.code, "message": error.message}) from error

    candidates = payload.tasks if payload.tasks is not None else stored.tasks
    selected = [candidate for candidate in candidates if candidate.selected]
    if not selected:
        raise HTTPException(status_code=400, detail={"code": "NO_TASKS_SELECTED", "message": "请至少确认一条任务"})
    if payload.course_id is not None:
        require_entity(db, Course, payload.course_id, code="COURSE_NOT_FOUND", message="关联课程不存在")
    default_course_id = payload.course_id if payload.course_id is not None else material.course_id
    batch_id = stored.batch_id
    if not batch_id:
        batch_id = secrets.token_hex(16)
        stored = stored.model_copy(update={"batch_id": batch_id})
    candidate_ids = [candidate.candidate_id for candidate in selected if candidate.candidate_id]
    if candidate_ids:
        existing_ids = set(
            db.scalars(
                select(Task.extraction_candidate_id).where(
                    Task.material_id == material.id,
                    Task.extraction_batch_id == batch_id,
                    Task.extraction_candidate_id.in_(candidate_ids),
                )
            ).all()
        )
        if existing_ids:
            raise HTTPException(status_code=409, detail={"code": "EXTRACTION_ALREADY_CONFIRMED", "message": "该批次的任务已经确认过"})
    created: list[Task] = []
    for candidate in selected:
        created.append(
            Task(
                course_id=_resolve_candidate_course(db, material, candidate, default_course_id),
                material_id=material.id,
                source_material_name=material.original_filename,
                name=candidate.name,
                task_type=candidate.task_type,
                description=candidate.description,
                due_at=candidate.due_at,
                priority=candidate.priority,
                estimated_minutes=candidate.estimated_minutes,
                remaining_minutes=candidate.remaining_minutes,
                confidence=candidate.confidence,
                need_review=False,
                source_quote=candidate.source_quote,
                extraction_batch_id=batch_id,
                extraction_candidate_id=candidate.candidate_id,
            )
        )
    db.add_all(created)
    db.flush()
    # Confirmed extraction is a first-class task creation path, so it must
    # produce the same M8.4 plan-difference audit as manual task creation.
    for task in created:
        create_plan_delta_candidates(db, task, "task_created")
    material.extraction_status = "confirmed"
    material.material_type = payload.material_type if payload.material_type is not None else stored.material_type or material.material_type
    if payload.tags is not None:
        material.tags = list(dict.fromkeys(tag.strip() for tag in payload.tags if tag.strip()))
    elif stored.tags:
        material.tags = list(dict.fromkeys(stored.tags))
    result_payload = stored.model_dump(mode="json")
    result_payload["material_type"] = material.material_type
    result_payload["tags"] = material.tags
    result_payload["tasks"] = [candidate.model_dump(mode="json") for candidate in selected]
    result_payload["needs_review"] = False
    result_payload["warnings"] = list(dict.fromkeys(warning for candidate in selected for warning in candidate.warnings))
    result_payload["confirmed_task_ids"] = [task.id for task in created]
    result_payload["confirmed_task_refs"] = [
        {"id": task.id, "navigation_key": task.navigation_key, "name": task.name}
        for task in created
    ]
    material.extraction_result = result_payload
    # The confirmation event belongs to the same transaction as the formal
    # tasks.  It is intentionally aggregate-only: detailed extraction content
    # remains on the material's audited result and is never used by the public
    # activity projection.
    db.add(AgentEvent(
        event_type="material_extraction_confirmed",
        entity_type="material",
        entity_id=material.id,
        entity_navigation_key=material.navigation_key,
        payload={"batch_id": batch_id, "confirmed_task_count": len(created)},
    ))
    try:
        commit_or_rollback(db)
    except HTTPException as error:
        if isinstance(error.detail, dict) and error.detail.get("code") == "DATABASE_CONSTRAINT_ERROR":
            raise HTTPException(status_code=409, detail={"code": "EXTRACTION_ALREADY_CONFIRMED", "message": "该批次的任务已经确认过"}) from error
        raise
    db.refresh(material)
    return _extraction_response(material)


@router.post("/{material_id}/extraction/confirm", response_model=ExtractionRead)
def confirm_extraction_endpoint(material_id: int, payload: ExtractionConfirm, db: Session = Depends(get_db), if_match: str | None = Header(default=None)) -> ExtractionRead:
    return confirm_extraction(material_id, payload, db, if_match)


@router.post("/{material_id}/confirm-extraction", response_model=ExtractionRead, include_in_schema=False)
def confirm_extraction_alias(material_id: int, payload: ExtractionConfirm, db: Session = Depends(get_db), if_match: str | None = Header(default=None)) -> ExtractionRead:
    return confirm_extraction(material_id, payload, db, if_match)


@router.patch("/{material_id}", response_model=MaterialRead)
def update_material(material_id: int, payload: MaterialUpdate, db: Session = Depends(get_db), if_match: str | None = Header(default=None)) -> Material:
    material = db.get(Material, material_id)
    if material is None:
        raise _not_found()
    check_edit_precondition(db, material, if_match)
    changes = payload.model_dump(exclude_unset=True)
    if material.stored_path and "file_type" in changes and changes["file_type"] != material.file_type:
        raise HTTPException(
            status_code=409,
            detail={"code": "FILE_TYPE_IMMUTABLE", "message": "已上传文件的格式不能手动修改"},
        )
    require_entity(
        db,
        Course,
        changes.get("course_id"),
        code="COURSE_NOT_FOUND",
        message="关联课程不存在",
    )
    text_changed = "extracted_text" in changes and changes["extracted_text"] != material.extracted_text
    if text_changed:
        changes["processing_status"] = "processed" if changes["extracted_text"] else "pending"
        changes["processing_error"] = None
        changes["extraction_status"] = "not_started"
        changes["extraction_result"] = None
        changes["extraction_provider"] = None
        changes["extraction_error"] = None
        changes["extracted_at"] = None
    for field, value in changes.items():
        setattr(material, field, value)
    commit_or_rollback(db)
    db.refresh(material)
    return material


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(material_id: int, db: Session = Depends(get_db), if_match: str | None = Header(default=None)) -> None:
    material = db.get(Material, material_id)
    if material is None:
        raise _not_found()
    check_edit_precondition(db, material, if_match)
    stored_path = _resolve_stored_path(material)
    for task in material.tasks:
        task.material_id = None
        task.source_material_name = task.source_material_name or material.original_filename
    db.delete(material)
    commit_or_rollback(db)
    if stored_path and stored_path.is_file():
        try:
            stored_path.unlink()
        except OSError:
            logger.warning("Failed to remove stored material file: %s", stored_path, exc_info=True)
