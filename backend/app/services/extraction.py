from __future__ import annotations

import json
import re
from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import uuid4

from app.models.material import Material
from app.schemas.extraction import ExtractionResult, ExtractionTaskCandidate
from app.services.llm_provider import ProviderError, get_provider
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
        task["source_quote"] = str(task.get("source_quote") or "").strip() or None
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
    try:
        result = ExtractionResult.model_validate(
            {
                "course_name": raw.get("course_name"),
                "material_type": raw.get("material_type"),
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
    if value is None:
        value = source
    if isinstance(value, datetime):
        return deadline_to_utc(value), []
    if isinstance(value, date):
        return deadline_to_utc(datetime.combine(value, time(23, 59))), []
    text = str(value).strip()
    if not text:
        return None, []
    reference = (as_local(source_time) if source_time is not None else as_local(utc_now())).replace(tzinfo=None)
    dates = _find_dates(text)
    source_dates = _find_dates(source)
    warnings: list[str] = []
    if len({item.isoformat() for item in dates + source_dates}) > 1:
        warnings.append("MULTIPLE_DATES_IN_SOURCE")
    if not dates:
        dates = source_dates
    if not dates:
        relative = _parse_relative(text, reference.date())
        if relative:
            dates = [relative]
    if not dates:
        return None, warnings
    selected = dates[0]
    if selected.year == 1900:
        year = reference.year
        selected = selected.replace(year=year)
        warnings.append("DATE_YEAR_INFERRED")
    parsed_time = _find_time(text) or _find_time(source)
    if parsed_time is None:
        warnings.append("TIME_DEFAULTED_TO_END_OF_DAY")
    resolved = datetime.combine(selected, parsed_time or time(23, 59))
    if resolved < reference:
        warnings.append("DATE_IN_PAST")
    return deadline_to_utc(resolved), warnings


def _find_dates(value: str) -> list[date]:
    matches: list[date] = []
    for match in re.finditer(r"(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日?|(?P<month2>\d{1,2})月(?P<day2>\d{1,2})日?|(?P<year3>\d{4})[-/](?P<month3>\d{1,2})[-/](?P<day3>\d{1,2})|(?P<month4>\d{1,2})/(?P<day4>\d{1,2})", value):
        year = int(match.group("year") or match.group("year3") or 1900)
        month = int(match.group("month") or match.group("month2") or match.group("month3") or match.group("month4"))
        day = int(match.group("day") or match.group("day2") or match.group("day3") or match.group("day4"))
        try:
            matches.append(date(year, month, day))
        except ValueError as error:
            raise ExtractionError("INVALID_DATE", f"抽取到无效日期：{year}-{month}-{day}") from error
    month_names = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    for match in re.finditer(
        r"\b(?P<month_name>January|February|March|April|May|June|July|August|September|October|November|December)\s+(?P<day_name>\d{1,2})(?:,\s*(?P<year_name>\d{4}))?",
        value,
        re.IGNORECASE,
    ):
        month = month_names[match.group("month_name").lower()]
        day = int(match.group("day_name"))
        year = int(match.group("year_name") or 1900)
        try:
            matches.append(date(year, month, day))
        except ValueError as error:
            raise ExtractionError("INVALID_DATE", f"抽取到无效日期：{year}-{month}-{day}") from error
    return matches


def _find_time(value: str) -> time | None:
    prefix_meridiem_match = re.search(r"(上午|下午|晚上|中午)\s*(\d{1,2})(?:[:：](\d{2}))?\s*[点时]?", value)
    if prefix_meridiem_match:
        meridiem = prefix_meridiem_match.group(1)
        hour, minute = int(prefix_meridiem_match.group(2)), int(prefix_meridiem_match.group(3) or 0)
        if meridiem in {"下午", "晚上", "中午"} and hour < 12:
            hour += 12
        if hour > 23 or minute > 59:
            raise ExtractionError("INVALID_TIME", f"抽取到无效时间：{hour}:{minute:02d}")
        return time(hour, minute)
    meridiem_match = re.search(r"(?<!\d)(\d{1,2})(?:[:：](\d{2}))?\s*(AM|PM|上午|下午|晚上|中午)", value, re.IGNORECASE)
    if meridiem_match:
        hour, minute = int(meridiem_match.group(1)), int(meridiem_match.group(2) or 0)
        meridiem = meridiem_match.group(3).lower()
        if meridiem in {"pm", "下午", "晚上", "中午"} and hour < 12:
            hour += 12
        if meridiem in {"am", "上午"} and hour == 12:
            hour = 0
        if hour > 23 or minute > 59:
            raise ExtractionError("INVALID_TIME", f"抽取到无效时间：{hour}:{minute:02d}")
        return time(hour, minute)
    match = re.search(r"(?<!\d)(\d{1,2})\s*[点时:：](\d{1,2})?\s*分?", value)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2) or 0)
    if hour > 23 or minute > 59:
        raise ExtractionError("INVALID_TIME", f"抽取到无效时间：{hour}:{minute:02d}")
    return time(hour, minute)


def _parse_relative(value: str, reference: date) -> date | None:
    if "大后天" in value:
        return reference + timedelta(days=3)
    for label, offset in (("今天", 0), ("明天", 1), ("后天", 2)):
        if label in value:
            return reference + timedelta(days=offset)
    if "下周末" in value:
        return reference + timedelta(days=(7 - reference.weekday()) + 6)
    if "本周末" in value or "周末" in value:
        return reference + timedelta(days=6 - reference.weekday())
    match = re.search(r"下周([一二三四五六日天])", value)
    if match:
        day_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
        days_until_next_monday = 7 - reference.weekday()
        return reference + timedelta(days=days_until_next_monday + day_map[match.group(1)])
    match = re.search(r"本周([一二三四五六日天])", value)
    if match:
        day_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
        return reference + timedelta(days=day_map[match.group(1)] - reference.weekday())
    match = re.search(r"(?:星期|周)([一二三四五六日天])", value)
    if match:
        day_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
        delta = (day_map[match.group(1)] - reference.weekday()) % 7
        return reference + timedelta(days=delta)
    if "today" in value.lower():
        return reference
    if "tomorrow" in value.lower():
        return reference + timedelta(days=1)
    match = re.search(r"next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", value, re.IGNORECASE)
    if match:
        day_map = {name: index for index, name in enumerate(("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"))}
        days_until_next_monday = 7 - reference.weekday()
        return reference + timedelta(days=days_until_next_monday + day_map[match.group(1).lower()])
    if "next weekend" in value.lower():
        return reference + timedelta(days=(7 - reference.weekday()) + 6)
    return None
