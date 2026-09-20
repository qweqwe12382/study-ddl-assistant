from __future__ import annotations

import json
import re
from datetime import date, datetime, time
from typing import Any
from uuid import uuid4

from app.models.material import Material
from app.schemas.extraction import ExtractionResult, ExtractionTaskCandidate
from app.services.llm_provider import ProviderError, get_provider, parse_deadline_text
from app.services.material_intent import describe_material, is_learning_activity
from app.time import as_local, deadline_to_utc, utc_now


class ExtractionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def extract_material(material: Material, provider_name: str | None = None) -> tuple[ExtractionResult, str]:
    if material.extraction_status == "confirmed":
        raise ExtractionError("EXTRACTION_ALREADY_CONFIRMED", "该资料已经确认过抽取结果，如需重新抽取请先修改正文")
    if material.processing_status != "processed" or not (material.extracted_text or "").strip():
        raise ExtractionError("EXTRACTION_SOURCE_UNAVAILABLE", "资料尚未成功解析出正文，无法进行 AI 抽取")

    try:
        provider = get_provider(provider_name) if provider_name else get_provider()
        raw = provider.extract(material.extracted_text or "", material.original_filename)
        if isinstance(raw, str):
            raw = json.loads(raw)
        if not isinstance(raw, dict):
            raise ExtractionError("INVALID_PROVIDER_JSON", "抽取结果必须是 JSON 对象")
        # Field provenance is always reconstructed from the material itself.
        # In particular, do not retain a model/provider's claimed source,
        # explanation, URL, or quote in the persisted result.
        result = _normalize_result(raw, material, provider_name=provider.name)
        result = result.model_copy(update={"batch_id": uuid4().hex})
    except ExtractionError:
        raise
    except ProviderError as error:
        raise ExtractionError(error.code, error.message) from error
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        raise ExtractionError("INVALID_PROVIDER_JSON", "抽取结果无法通过 JSON 结构校验") from error

    material.extraction_status = "needs_review" if result.needs_review else "ready"
    material.extraction_result = result.model_dump(mode="json")
    material.extraction_provider = provider.name
    material.extraction_error = None
    material.extracted_at = utc_now()
    return result, provider.name


def mark_extraction_failed(material: Material, error: ExtractionError) -> None:
    material.extraction_status = "failed"
    material.extraction_error = error.message
    material.extracted_at = utc_now()


def stored_result(material: Material) -> ExtractionResult:
    if not material.extraction_result:
        raise ExtractionError("EXTRACTION_NOT_FOUND", "该资料还没有抽取结果")
    try:
        return ExtractionResult.model_validate(material.extraction_result)
    except (TypeError, ValueError) as error:
        raise ExtractionError("INVALID_STORED_EXTRACTION", "已保存的抽取结果格式无效，请重新抽取") from error


_EVIDENCE_SNIPPET_LIMIT = 180
_EVIDENCE_CONTEXT_RADIUS = 48
_EVIDENCE_TAG_LIMIT = 30
_URL_PATTERN = re.compile(r"(?i)\b(?:https?|ftp)://\S+")
_WINDOWS_PATH_PATTERN = re.compile(r"(?i)\b[a-z]:[\\/][^\s]+")
_UNIX_PATH_PATTERN = re.compile(r"(?<!\w)/(?:[^\s/]+/)+[^\s]+")


def _normalize_result(raw: dict[str, Any], material: Material, *, provider_name: str) -> ExtractionResult:
    raw_tasks = raw.get("tasks", [])
    if not isinstance(raw_tasks, list):
        raise ExtractionError("INVALID_PROVIDER_JSON", "抽取结果中的 tasks 必须是数组")
    raw_tags = raw.get("tags", [])
    if not isinstance(raw_tags, list):
        raise ExtractionError("INVALID_PROVIDER_JSON", "抽取结果中的 tags 必须是数组")
    if len(raw_tags) > _EVIDENCE_TAG_LIMIT:
        raise ExtractionError("INVALID_PROVIDER_JSON", f"抽取结果中的 tags 最多允许 {_EVIDENCE_TAG_LIMIT} 项")
    source_text = material.extracted_text or ""
    normalized_tasks: list[dict[str, Any]] = []
    result_warnings = [str(item) for item in raw.get("warnings", []) if item]
    for index, raw_task in enumerate(raw_tasks):
        if not isinstance(raw_task, dict):
            raise ExtractionError("INVALID_PROVIDER_JSON", "抽取结果中的任务必须是对象")
        task = dict(raw_task)
        name = str(task.get("name") or task.get("task_name") or "").strip()
        if not name:
            raise ExtractionError("INVALID_PROVIDER_JSON", "抽取到的任务缺少 name")
        task["name"] = name[:200]
        task["candidate_id"] = str(task.get("candidate_id") or f"candidate-{index + 1}")
        raw_source_quote = str(task.get("source_quote") or "")
        task["source_quote"] = raw_source_quote if raw_source_quote.strip() else None
        if task["source_quote"] and task["source_quote"] in source_text and is_learning_activity(task["source_quote"]):
            continue
        if task["source_quote"] and task["source_quote"] not in source_text:
            task.setdefault("warnings", []).append("SOURCE_QUOTE_NOT_FOUND")
        due_at, date_warnings = _parse_due_at(task, task["source_quote"] or name, material.source_time)
        task["due_at"] = due_at
        task.setdefault("confidence", 0.0)
        task["confidence"] = float(task["confidence"])
        task.setdefault("priority", 3)
        warnings = [str(item) for item in task.get("warnings", []) if item]
        warnings.extend(date_warnings)
        if due_at is None:
            warnings.append("MISSING_DUE_DATE")
        if task["confidence"] < 0.75:
            warnings.append("LOW_CONFIDENCE")
        task["warnings"] = list(dict.fromkeys(warnings))
        task["need_review"] = bool(task.get("need_review")) or bool(task["warnings"])
        normalized_tasks.append(task)

    result_warnings.extend(warning for task in normalized_tasks for warning in task["warnings"])
    result_warnings = list(dict.fromkeys(result_warnings))
    description = describe_material(source_text, material.original_filename, normalized_tasks)
    try:
        result = ExtractionResult.model_validate(
            {
                "course_name": raw.get("course_name"),
                "material_type": raw.get("material_type") or description["material_type"],
                "content_kind": description["content_kind"],
                "learning_points": description["learning_points"],
                "tags": raw_tags,
                "tasks": normalized_tasks,
                "warnings": result_warnings,
                "needs_review": bool(raw.get("needs_review")) or bool(result_warnings),
            }
        )
        # Never accept raw["field_evidence"]. Its only trusted input is the
        # server-held filename/body plus the final schema-validated values.
        result = ExtractionResult.model_validate(
            {
                **result.model_dump(),
                "field_evidence": _build_field_evidence(
                    course_name=result.course_name,
                    material_type=result.material_type,
                    tags=result.tags,
                    material=material,
                    provider_name=provider_name,
                ),
            }
        )
    except (TypeError, ValueError) as error:
        raise ExtractionError("INVALID_PROVIDER_JSON", "抽取结果未通过结构化字段校验") from error
    return result


def _safe_filename(filename: str | None) -> str:
    """Return a display-safe basename even for manually-created materials."""

    value = str(filename or "")
    return re.split(r"[\\/]", value)[-1].strip()


def _clean_evidence_excerpt(value: str) -> str:
    """Bound a material excerpt and remove URL/path-like data from it."""

    value = _URL_PATTERN.sub("[链接已省略]", value)
    value = _WINDOWS_PATH_PATTERN.sub("[路径已省略]", value)
    value = _UNIX_PATH_PATTERN.sub("[路径已省略]", value)
    value = re.sub(r"[\x00-\x1f\x7f]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= _EVIDENCE_SNIPPET_LIMIT:
        return value
    return f"{value[: _EVIDENCE_SNIPPET_LIMIT - 1].rstrip()}…"


def _excerpt_for_match(source: str, value: str) -> str | None:
    """Return one bounded excerpt only when a value literally occurs in source."""

    if not source or not value:
        return None
    match = re.search(re.escape(value), source, flags=re.IGNORECASE)
    if match is None:
        return None
    left = max(0, match.start() - _EVIDENCE_CONTEXT_RADIUS)
    right = min(len(source), match.end() + _EVIDENCE_CONTEXT_RADIUS)
    prefix = "…" if left else ""
    suffix = "…" if right < len(source) else ""
    excerpt = _clean_evidence_excerpt(f"{prefix}{source[left:right]}{suffix}")
    return excerpt or None


def _evidence_for_value(value: str | None, filename: str, text: str, provider_name: str) -> dict[str, Any] | None:
    """Classify a normalized value using only server-held material sources."""

    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    filename_excerpt = _excerpt_for_match(filename, value)
    text_excerpt = _excerpt_for_match(text, value)
    snippets = [item for item in (filename_excerpt, text_excerpt) if item]
    if filename_excerpt and text_excerpt:
        source = "both"
    elif filename_excerpt:
        source = "filename"
    elif text_excerpt:
        source = "text"
    elif provider_name == "local-rules":
        source = "rule_inference"
    else:
        source = "unconfirmed"
    return {"value": value, "source": source, "snippets": snippets}


def _build_field_evidence(
    *,
    course_name: Any,
    material_type: Any,
    tags: Any,
    material: Material,
    provider_name: str,
) -> dict[str, Any]:
    """Create bounded evidence without trusting provider-owned provenance.

    The values here have already passed Pydantic validation, so this helper
    only derives provenance for values that can actually be returned.
    A malformed or oversized provider ``field_evidence`` field is intentionally
    never read, so it cannot become an API response or database snapshot.
    """

    filename = _safe_filename(material.original_filename)
    text = material.extracted_text or ""
    return {
        "course_name": _evidence_for_value(course_name, filename, text, provider_name),
        "material_type": _evidence_for_value(material_type, filename, text, provider_name),
        "tags": [
            evidence
            for tag in tags
            if (evidence := _evidence_for_value(tag, filename, text, provider_name)) is not None
        ],
    }


def _parse_due_at(task: dict[str, Any], source: str, source_time: datetime | None) -> tuple[datetime | None, list[str]]:
    value = task.get("due_at") or task.get("due_date")
    reference = (as_local(source_time) if source_time is not None else as_local(utc_now())).replace(tzinfo=None)
    source_resolved, source_warnings = parse_deadline_text(source, reference)
    if "AMBIGUOUS_TASK_DATE" in source_warnings:
        return None, source_warnings
    if isinstance(value, datetime):
        normalized = deadline_to_utc(value)
        if source_resolved is not None and normalized != deadline_to_utc(source_resolved):
            return None, list(dict.fromkeys([*source_warnings, "DATE_CONFLICT_WITH_SOURCE"]))
        return (deadline_to_utc(source_resolved) if source_resolved is not None else normalized), source_warnings
    if isinstance(value, date):
        normalized = deadline_to_utc(datetime.combine(value, time(23, 59)))
        if source_resolved is not None and normalized != deadline_to_utc(source_resolved):
            return None, list(dict.fromkeys([*source_warnings, "DATE_CONFLICT_WITH_SOURCE"]))
        return (deadline_to_utc(source_resolved) if source_resolved is not None else normalized), source_warnings
    text = str(value or "").strip()
    if not text:
        if source_resolved is None:
            return None, source_warnings
        return deadline_to_utc(source_resolved), source_warnings
    combined = text if text == source else f"{text}\n{source}"
    resolved, warnings = parse_deadline_text(combined, reference)
    return (deadline_to_utc(resolved) if resolved is not None else None), warnings
