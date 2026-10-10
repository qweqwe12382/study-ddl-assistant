from __future__ import annotations

from datetime import date, datetime, time, timedelta
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


def _rule_positive_int(rule: Any, key: str, default: int | None) -> int | None:
    values = _list_value(rule, key)
    if not values:
        return default
    if len(values) != 1 or not re.fullmatch(r"[1-9][0-9]*", str(values[0])):
        raise ValueError(f"重复规则 {key} 无效")
    return int(values[0])


def _excluded_starts(component, source_start: datetime) -> set[datetime]:
    excluded = set()
    values = component.get("EXDATE", [])
    for value in values if isinstance(values, list) else [values]:
        dates = getattr(value, "dts", None)
        if dates is None:
            raise ValueError("排除日期 EXDATE 无法识别")
        for entry in dates:
            day = getattr(entry, "dt", None)
            if not isinstance(day, datetime):
                raise ValueError("排除日期 EXDATE 必须包含明确的课程开始时间")
            if day.tzinfo is None:
                if getattr(value, "params", {}).get("TZID"):
                    raise ValueError("排除日期 EXDATE 的时区无法识别")
                day = day.replace(tzinfo=source_start.tzinfo)
            excluded.add(day.astimezone(CHINA_ZONE))
    return excluded


def _course_occurrences(component, semester_start: date, semester_weeks: int) -> list[datetime]:
    """Expand our supported weekly subset, then apply exclusions.

    COUNT counts all starts, including ones before the requested semester and
    subsequently removed by EXDATE. Work is bounded by the semester window,
    even when DTSTART is many years in the past.
    """
    source_start = _decoded(component, "DTSTART")
    if source_start.tzinfo is None:
        source_start = source_start.replace(tzinfo=CHINA_ZONE)
    excluded = _excluded_starts(component, source_start)
    rule = component.get("RRULE")
    if not rule:
        start = source_start.astimezone(CHINA_ZONE)
        return [start] if start not in excluded and 1 <= _week_number(start.date(), semester_start) <= semester_weeks else []
    if isinstance(rule, list) or not hasattr(rule, "keys"):
        raise ValueError("不支持同一事件的多条重复规则")
    if any(len(_list_value(rule, key)) > 1 for key in ("FREQ", "WKST")):
        raise ValueError("重复频率或周起点不能包含多个值")
    unsupported = set(rule.keys()) - {"FREQ", "INTERVAL", "COUNT", "UNTIL", "BYDAY", "WKST"}
    if unsupported:
        raise ValueError(f"暂不支持重复规则 {', '.join(sorted(unsupported))}")
    interval = _rule_positive_int(rule, "INTERVAL", 1)
    if _first_text(rule, "FREQ") != "WEEKLY" or interval not in {1, 2}:
        raise ValueError("仅支持每周或隔周重复")
    count = _rule_positive_int(rule, "COUNT", None)
    until_values = _list_value(rule, "UNTIL")
    if count is not None and until_values:
        raise ValueError("重复规则不能同时指定 COUNT 和 UNTIL")
    until = until_values[0] if len(until_values) == 1 else None
    if until_values and not isinstance(until, datetime):
        if not isinstance(until, date):
            raise ValueError("重复截止 UNTIL 必须包含明确时间")
        # RFC 5545 requires a datetime UNTIL when DTSTART is a datetime, yet
        # real exporters emit plain dates. The intent is unambiguous: that
        # final day still happens, so bound it at end of day in source time.
        until = datetime.combine(until, time(23, 59, 59))
    if until is not None and until.tzinfo is None:
        until = until.replace(tzinfo=source_start.tzinfo)
    days = [str(value).upper() for value in _list_value(rule, "BYDAY")]
    if any(day not in WEEKDAY_CODES for day in days):
        raise ValueError("星期重复 BYDAY 无效或包含不支持的序数")
    weekdays = {WEEKDAY_CODES[day] for day in days} or {source_start.isoweekday()}
    if source_start.isoweekday() not in weekdays:
        raise ValueError("开始日期与重复星期 BYDAY 不一致")
    week_start = _first_text(rule, "WKST") or "MO"
    if week_start not in WEEKDAY_CODES:
        raise ValueError("重复周起点 WKST 无效")
    offsets = sorted((weekday - WEEKDAY_CODES[week_start]) % 7 for weekday in weekdays)
    start_offset = (source_start.isoweekday() - WEEKDAY_CODES[week_start]) % 7
    anchor = source_start.date() - timedelta(days=start_offset)
    initial_offsets = [offset for offset in offsets if offset >= start_offset]
    # One extra source week covers timezone/date changes at either boundary.
    first_cycle = max(0, (semester_start - anchor).days // (7 * interval) - 1)
    last_cycle = (semester_start + timedelta(weeks=semester_weeks) - anchor).days // (7 * interval) + 1
    occurrences = []
    for cycle in range(first_cycle, last_cycle + 1):
        active_offsets = initial_offsets if cycle == 0 else offsets
        for index, offset in enumerate(active_offsets):
            ordinal = index + 1 if cycle == 0 else len(initial_offsets) + (cycle - 1) * len(offsets) + index + 1
            if count is not None and ordinal > count:
                return occurrences
            day = anchor + timedelta(days=cycle * 7 * interval + offset)
            occurrence = datetime.combine(day, source_start.timetz())
            if until is not None and occurrence > until:
                return occurrences
            start = occurrence.astimezone(CHINA_ZONE)
            if start not in excluded and 1 <= _week_number(start.date(), semester_start) <= semester_weeks:
                occurrences.append(start)
    return occurrences


def _occurrence_ranges(weeks: set[int]) -> list[tuple[int, int, str]]:
    """Represent an exact week set without filling gaps left by EXDATE."""
    remaining = set(weeks)
    ranges = []
    while remaining:
        first = min(remaining)
        consecutive = [first]
        while consecutive[-1] + 1 in remaining:
            consecutive.append(consecutive[-1] + 1)
        alternating = [first]
        while alternating[-1] + 2 in remaining:
            alternating.append(alternating[-1] + 2)
        chosen = consecutive if len(consecutive) >= len(alternating) else alternating
        pattern = "all" if chosen is consecutive or len(chosen) == 1 else ("odd" if first % 2 else "even")
        ranges.append((chosen[0], chosen[-1], pattern))
        remaining.difference_update(chosen)
    return ranges


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

    events = calendar.walk("VEVENT")
    # An override belongs to its master UID. Importing the master while simply
    # dropping a moved/cancelled override would resurrect the original class.
    override_uids = {
        _text(event.get("UID"), 240)
        for event in events if event.get("RECURRENCE-ID") is not None
    }
    cancelled_uids = {
        _text(event.get("UID"), 240)
        for event in events
        if _text(event.get("STATUS"), 30).upper() == "CANCELLED" and event.get("RECURRENCE-ID") is None
    }
    override_warned: set[str] = set()
    for event_index, component in enumerate(events, start=1):
        summary = _text(component.get("SUMMARY"), 160)
        location = _text(component.get("LOCATION"), 120) or None
        description = _text(component.get("DESCRIPTION"), 500) or None
        teacher = _teacher_name(component, description)
        uid = _text(component.get("UID"), 240) or hashlib.sha256(
            component.to_ical() + str(event_index).encode("ascii")
        ).hexdigest()
        label = summary or '未命名事件'
        if uid in override_uids or component.get("RECURRENCE-ID") is not None:
            # One warning per series: the master and each override component
            # describe the same rejected group and would otherwise crowd out
            # the capped warning list.
            if uid not in override_warned:
                override_warned.add(uid)
                warnings.append(f"{label}：含单次改期或取消覆盖 RECURRENCE-ID，整组未导入，请核对后手工录入")
            continue
        if uid in cancelled_uids or _text(component.get("STATUS"), 30).upper() == "CANCELLED" or _text(calendar.get("METHOD"), 30).upper() == "CANCEL":
            warnings.append(f"{label}：已取消，未导入；已有本地日程不会自动删除，请核对")
            continue
        if component.get("RDATE") is not None or component.get("EXRULE") is not None:
            warnings.append(f"{label}：暂不支持附加日期或排除重复规则 RDATE/EXRULE，未导入")
            continue
        if getattr(component, "errors", None):
            warnings.append(f"{label}：日历字段无法完整解析，未导入，请核对原文件")
            continue
        if any(
            getattr(component.get(field), "params", {}).get("TZID")
            and isinstance(_decoded(component, field), datetime)
            and _decoded(component, field).tzinfo is None
            for field in ("DTSTART", "DTEND")
        ):
            warnings.append(f"{label}：时区无法识别，未导入，请核对原文件")
            continue
        starts_at = _as_china_datetime(_decoded(component, "DTSTART"))
        ends_at = _as_china_datetime(_decoded(component, "DTEND"))
        if ends_at is not None and _decoded(component, "DURATION") is not None:
            warnings.append(f"{label}：同时包含 DTEND 与 DURATION，已按 DTEND 处理")
        if ends_at is None and starts_at is not None:
            duration = _decoded(component, "DURATION")
            if isinstance(duration, timedelta):
                # RFC 5545 allows DURATION in place of DTEND; some exporters
                # only emit it. Both datetimes are aware, so the sum keeps the
                # same instant and later checks (cross-midnight, ordering)
                # apply unchanged.
                ends_at = _as_china_datetime(starts_at + duration)
        if starts_at is None or ends_at is None:
            warnings.append(f"{summary or '未命名事件'}：全天事件或时间不完整，未导入")
            continue
        if ends_at <= starts_at:
            warnings.append(f"{summary or '未命名事件'}：结束时间不晚于开始时间，未导入")
            continue

        rule = component.get("RRULE")
        is_exam = bool(EXAM_WORDS.search(f"{summary} {description or ''}"))
        if is_exam:
            if rule:
                warnings.append(f"{label}：重复考试暂不支持，未导入，请逐场录入")
                continue
            try:
                source_start = _decoded(component, "DTSTART")
                if source_start.tzinfo is None:
                    source_start = source_start.replace(tzinfo=CHINA_ZONE)
                if starts_at in _excluded_starts(component, source_start):
                    warnings.append(f"{label}：考试已被 EXDATE 排除，未导入")
                    continue
            except ValueError as exc:
                warnings.append(f"{label}：{exc}，未导入")
                continue
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

        if starts_at.date() != ends_at.date():
            warnings.append(f"{label}：跨午夜课程暂不支持，未导入，请按每天的时段分别录入")
            continue
        try:
            occurrences = _course_occurrences(component, semester_start, semester_weeks)
        except (ValueError, OverflowError) as exc:
            reason = str(exc) if isinstance(exc, ValueError) else "重复日期超出可处理范围"
            warnings.append(f"{label}：{reason}，未导入")
            continue
        if not occurrences:
            warnings.append(f"{label}：本学期没有实际发生的课程（可能已被排除或超出学期范围），未导入")
            continue
        if any(start.time().replace(tzinfo=None) != starts_at.time().replace(tzinfo=None) for start in occurrences):
            warnings.append(f"{label}：重复课程受时区切换影响，无法用固定北京时间表达，未导入")
            continue
        weeks_by_day: dict[int, set[int]] = {}
        for occurrence in occurrences:
            weeks_by_day.setdefault(occurrence.isoweekday(), set()).add(_week_number(occurrence.date(), semester_start))
        for weekday, weeks in sorted(weeks_by_day.items()):
            for range_index, (first_week, end_week, pattern) in enumerate(_occurrence_ranges(weeks), start=1):
                # Preserve existing one-range identities. Further ranges have
                # deterministic bounded suffixes, including for a long ICS UID.
                suffix = "" if range_index == 1 else f":s{range_index}"
                external_uid = f"{uid}:weekday:{weekday}{suffix}"
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

    if not items and not warnings:
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
