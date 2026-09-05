from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
import re
from typing import Any
from zoneinfo import ZoneInfo

from icalendar import Calendar


CHINA_ZONE = ZoneInfo("Asia/Shanghai")
WEEKDAY_CODES = {"MO": 1, "TU": 2, "WE": 3, "TH": 4, "FR": 5, "SA": 6, "SU": 7}
EXAM_WORDS = re.compile(r"考试|期中|期末|测验|考查|quiz|exam|midterm|final", re.IGNORECASE)
TEACHER_WORDS = re.compile(r"(?:任课)?教师\s*[：:]\s*([^\n;,，；]{1,40})", re.IGNORECASE)
MAX_CALENDAR_BYTES = 1_000_000


class AcademicCalendarImportError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def source_key(source_type: str, source_name: str) -> str:
    normalized = f"{source_type.strip().lower()}\n{source_name.strip().casefold()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _as_china_datetime(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=CHINA_ZONE)
    return value.astimezone(CHINA_ZONE)


def _decoded(component, key: str) -> Any:
    if component.get(key) is None:
        return None
    try:
        return component.decoded(key)
    except (AttributeError, TypeError, ValueError):
        return None


def _list_value(rule: Any, key: str) -> list[Any]:
    if not rule:
        return []
    value = rule.get(key, [])
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _first_int(rule: Any, key: str, default: int) -> int:
    values = _list_value(rule, key)
    if not values:
        return default
    try:
        return int(values[0])
    except (TypeError, ValueError):
        return default


def _first_text(rule: Any, key: str) -> str | None:
    values = _list_value(rule, key)
    if not values:
        return None
    value = values[0]
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value).upper()


def _week_number(day: date, semester_start: date) -> int:
    return ((day - semester_start).days // 7) + 1


def _rrule_end_week(rule: Any, raw_start_week: int, interval: int, semester_start: date, semester_weeks: int) -> int:
    until_values = _list_value(rule, "UNTIL")
    if until_values:
        until = until_values[0]
        if isinstance(until, datetime):
            until = (_as_china_datetime(until) or until).date()
        if isinstance(until, date):
            return min(semester_weeks, _week_number(until, semester_start))
    count = _first_int(rule, "COUNT", 0)
    if count > 0:
        return min(semester_weeks, raw_start_week + ((count - 1) * interval))
    return semester_weeks


def _first_active_week(raw_start_week: int, interval: int) -> int:
    week = max(1, raw_start_week)
    while (week - raw_start_week) % interval:
        week += 1
    return week


def _exam_course_name(summary: str) -> str:
    cleaned = EXAM_WORDS.sub("", summary)
    cleaned = re.sub(r"[\s·｜|—_-]+", " ", cleaned).strip(" ：:（）()[]【】")
    return (cleaned or summary or "未命名课程")[:120]


def _teacher_name(component, description: str | None) -> str | None:
    explicit = _text(component.get("X-TEACHER"), 120)
    if explicit:
        return explicit
    organizer = component.get("ORGANIZER")
    organizer_name = _text(getattr(organizer, "params", {}).get("CN") if organizer else None, 120)
    if organizer_name:
        return organizer_name
    match = TEACHER_WORDS.search(description or "")
    if match:
        return match.group(1).strip()[:120]
    plain = (description or "").strip()
    if re.fullmatch(r"[\u4e00-\u9fff·]{1,12}老师", plain):
        return plain
    return None


def parse_ical_calendar(
    *,
    calendar_text: str,
    source_name: str,
    semester_start: date,
    semester_weeks: int,
) -> tuple[str, list[dict[str, Any]], list[str]]:
    encoded_size = len(calendar_text.encode("utf-8"))
    if encoded_size > MAX_CALENDAR_BYTES:
        raise AcademicCalendarImportError("CALENDAR_TOO_LARGE", "日历文件不能超过 1 MB")
    try:
        calendar = Calendar.from_ical(calendar_text)
    except Exception as exc:
        raise AcademicCalendarImportError("CALENDAR_INVALID", "无法读取该 iCalendar 文件") from exc

    key = source_key("ical", source_name)
    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen_keys: set[str] = set()

    for event_index, component in enumerate(calendar.walk("VEVENT"), start=1):
        summary = _text(component.get("SUMMARY"), 160)
        location = _text(component.get("LOCATION"), 120) or None
        description = _text(component.get("DESCRIPTION"), 500) or None
        teacher = _teacher_name(component, description)
        uid = _text(component.get("UID"), 240) or hashlib.sha256(
            component.to_ical() + str(event_index).encode("ascii")
        ).hexdigest()
        starts_at = _as_china_datetime(_decoded(component, "DTSTART"))
        ends_at = _as_china_datetime(_decoded(component, "DTEND"))
        if starts_at is None or ends_at is None:
            warnings.append(f"{summary or '未命名事件'}：全天事件或时间不完整，未导入")
            continue
        if ends_at <= starts_at:
            warnings.append(f"{summary or '未命名事件'}：结束时间不晚于开始时间，未导入")
            continue

        rule = component.get("RRULE")
        is_exam = bool(EXAM_WORDS.search(f"{summary} {description or ''}"))
        if is_exam:
            external_uid = f"{uid}:exam"
            item = {
                "item_key": hashlib.sha256(f"{key}|exam|{external_uid}".encode()).hexdigest()[:24],
                "external_uid": external_uid,
                "kind": "exam",
                "course_name": _exam_course_name(summary),
                "title": summary or "考试",
                "exam_type": "midterm" if re.search(r"期中|midterm", summary, re.I) else (
                    "quiz" if re.search(r"测验|quiz", summary, re.I) else (
                        "final" if re.search(r"期末|final", summary, re.I) else "other"
                    )
                ),
                "starts_at": starts_at,
                "ends_at": ends_at,
                "location": location,
                "seat_number": None,
                "note": description,
            }
            if item["item_key"] not in seen_keys:
                items.append(item)
                seen_keys.add(item["item_key"])
            continue

        raw_start_week = _week_number(starts_at.date(), semester_start)
        if rule:
            frequency = _first_text(rule, "FREQ")
            interval = _first_int(rule, "INTERVAL", 1)
            if frequency != "WEEKLY" or interval not in {1, 2}:
                warnings.append(f"{summary or '未命名事件'}：仅支持每周或隔周重复，未导入")
                continue
            first_week = _first_active_week(raw_start_week, interval)
            end_week = _rrule_end_week(rule, raw_start_week, interval, semester_start, semester_weeks)
            if first_week > semester_weeks or end_week < first_week:
                continue
            weekday_codes = [str(value).upper()[-2:] for value in _list_value(rule, "BYDAY")]
            weekday_values = [WEEKDAY_CODES[code] for code in weekday_codes if code in WEEKDAY_CODES]
            if not weekday_values:
                weekday_values = [starts_at.isoweekday()]
            pattern = "all" if interval == 1 else ("odd" if first_week % 2 else "even")
        else:
            if raw_start_week < 1 or raw_start_week > semester_weeks:
                continue
            first_week = end_week = raw_start_week
            weekday_values = [starts_at.isoweekday()]
            pattern = "all"

        for weekday in weekday_values:
            external_uid = f"{uid}:weekday:{weekday}"
            item_key = hashlib.sha256(f"{key}|class_session|{external_uid}".encode()).hexdigest()[:24]
            if item_key in seen_keys:
                continue
            items.append(
                {
                    "item_key": item_key,
                    "external_uid": external_uid,
                    "kind": "class_session",
                    "course_name": (summary or "未命名课程")[:120],
                    "teacher": teacher,
                    "weekday": weekday,
                    "start_time": starts_at.time().replace(tzinfo=None),
                    "end_time": ends_at.time().replace(tzinfo=None),
                    "location": location,
                    "start_week": first_week,
                    "end_week": end_week,
                    "week_pattern": pattern,
                    "note": description,
                }
            )
            seen_keys.add(item_key)

    if not items:
        raise AcademicCalendarImportError("CALENDAR_EMPTY", "文件中没有可导入的课程或考试")
    return key, items, warnings[:20]


def class_payload(item: Any, course_name: str) -> dict[str, Any]:
    return {
        "kind": "class_session",
        "course_name": course_name,
        "weekday": item.weekday,
        "start_time": item.start_time.isoformat(timespec="minutes"),
        "end_time": item.end_time.isoformat(timespec="minutes"),
        "location": item.location,
        "start_week": item.start_week,
        "end_week": item.end_week,
        "week_pattern": item.week_pattern,
        "note": item.note,
    }


def exam_payload(item: Any, course_name: str) -> dict[str, Any]:
    def iso(value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo("UTC"))
        return value.astimezone(ZoneInfo("UTC")).isoformat()

    return {
        "kind": "exam",
        "course_name": course_name,
        "title": item.title,
        "exam_type": item.exam_type,
        "starts_at": iso(item.starts_at),
        "ends_at": iso(item.ends_at),
        "location": item.location,
        "seat_number": item.seat_number,
        "note": item.note,
    }
