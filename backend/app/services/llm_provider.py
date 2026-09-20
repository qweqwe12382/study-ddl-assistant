"""Replaceable providers for M4 structured extraction.

The local provider is deliberately deterministic so the demo and tests work
without credentials or network access.  An OpenAI-compatible provider can be
enabled entirely through environment variables when desired.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Protocol

from app.config import settings


class ProviderError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class LLMProvider(Protocol):
    name: str

    def extract(self, text: str, filename: str) -> dict[str, Any] | str: ...


_TASK_HINTS = (
    "作业",
    "实验",
    "报告",
    "考试",
    "测验",
    "提交",
    "截止",
    "完成",
    "assignment",
    "homework",
    "exam",
    "quiz",
    "submit",
    "due",
    "report",
    "lab",
    "ddl",
)

_TASK_ENTITY_PATTERN = re.compile(
    r"实验(?!室|课)(?:[一二三四五六七八九十0-9]+)?(?:报告)?|"
    r"(?:课程|期末|安全分析|语义分析)?报告|"
    r"作业(?:[一二三四五六七八九十0-9]+)?|考试|测验|"
    r"\b(?:assignment|homework|exam|quiz|lab(?:\s+\d+)?(?:\s+report)?|report)\b",
    re.IGNORECASE,
)
_COURSE_LINE_PATTERN = re.compile(r"^(?:课程(?:名称)?|course)\s*[：:]\s*(.+)$", re.IGNORECASE)
_CLAUSE_SEPARATOR_PATTERN = re.compile(r"[，,；;]")

# Student-owned actions.  These are intentionally narrower than arbitrary
# verbs such as "查看" or "恢复": a dated system event must not become a task.
_STUDENT_ACTION_PATTERN = re.compile(
    r"提交|上传|填写|登记|确认|参加|完成|预约|签到|报到|缴纳|"
    r"到[^，。；;！？\r\n]{1,30}?集合|"
    r"将[^，。；;！？\r\n]{1,80}?发给[^，。；;！？\r\n]{1,30}|"
    r"\b(?:submit|upload|complete|register|confirm|attend)\b",
    re.IGNORECASE,
)
_ACTION_WORD_PATTERN = re.compile(
    r"提交|上传|填写|登记|确认|参加|完成|预约|签到|报到|缴纳|集合|发给|"
    r"\b(?:submit|upload|complete|register|confirm|attend)\b",
    re.IGNORECASE,
)
_OBLIGATION_PATTERN = re.compile(
    r"请|须|务必|必须|应(?:当)?|需要|需在|各组|每组|所有|"
    r"\b(?:please|must|required|need\s+to)\b",
    re.IGNORECASE,
)
_NEGATED_OR_FINISHED_PATTERN = re.compile(
    r"已取消|已经取消|取消(?:本次|此次)?|(?:说法|安排|通知|截止)?作废|请勿|不要|不得|不要求|没有安排|"
    r"无需|不必|已经结束|已结束|已经完成|已完成|"
    r"\b(?:cancelled|canceled|do\s+not|don't|not\s+required|already\s+(?:ended|completed))\b",
    re.IGNORECASE,
)
_POSTPONED_PATTERN = re.compile(r"暂缓|暂停收取|暂停提交|待后续通知|另行通知|日期尚未确定|日期会.*确定")
_CONDITIONAL_AUDIENCE_PATTERN = re.compile(
    r"如需|仅(?:需|限)|需要[^，。；;！？]{0,30}的同学|首次[^，。；;！？]{0,30}的同学|"
    r"(?:选修|补做|毕业班|首次)[^，。；;！？]{0,30}的同学|毕业班同学|每组至少|"
    r"已(?:经)?[^，。；;！？]{0,24}(?:无需|不必)",
)
_INFORMATIONAL_UPLOAD_PATTERN = re.compile(r"(?:老师|教师|平台|系统|材料|资料|文件|答案)[^。；;！？]{0,24}(?:已|已经)上传")
_VAGUE_DATE_PATTERN = re.compile(r"近期|本周(?:内)?|下周(?![一二三四五六日天末])|日期.*(?:待|会).*(?:通知|确定)|具体.*(?:等|待).*(?:确认|通知)")
_STRONG_RESCHEDULE_PATTERN = re.compile(r"改到|改为|调整到|调整为")
_EXTENSION_RESCHEDULE_PATTERN = re.compile(r"(?:现(?:已)?|已经)?(?:延长|延后|延期)至|现延至|延期到")

_DATE_CORE = (
    r"(?:\d{4}年\s*\d{1,2}月\s*\d{1,2}日?"
    r"|\d{4}[-/]\d{1,2}[-/]\d{1,2}"
    r"|\d{1,2}月\s*\d{1,2}日?"
    r"|\d{1,2}/\d{1,2}"
    r"|大后天|今天|明天|后天|下周末|本周末|周末"
    r"|下周[一二三四五六日天]|本周[一二三四五六日天]|(?:星期|周)[一二三四五六日天]"
    r"|(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2}(?:,\s*\d{4})?"
    r"|today|tomorrow|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekend))"
)
_TIME_SUFFIX = (
    r"(?:\s*T?\s*(?:上午|下午|晚上|中午|早上|凌晨)?\s*\d{1,2}"
    r"(?:(?:[:：]\d{1,2})|(?:[点时](?:\s*\d{1,2}\s*分?)?))"
    r"(?:\s*(?:AM|PM))?)?"
)
_DEADLINE_PATTERN = re.compile(rf"(?P<date>{_DATE_CORE})(?P<time>{_TIME_SUFFIX})", re.IGNORECASE)


@dataclass(frozen=True)
class DeadlineMention:
    text: str
    start: int
    end: int


def find_deadline_mentions(value: str) -> list[DeadlineMention]:
    """Return all date expressions with their exact source spans.

    Candidate detection and normalization deliberately share this scanner so a
    date that creates a candidate is always understood by the parser as well.
    """

    return [DeadlineMention(match.group(0), match.start(), match.end()) for match in _DEADLINE_PATTERN.finditer(value)]


def parse_deadline_text(value: str, reference: datetime) -> tuple[datetime | None, list[str]]:
    """Resolve one unambiguous deadline against a fixed local reference time."""

    mentions = find_deadline_mentions(value)
    if not mentions:
        return None, []
    parsed: list[tuple[DeadlineMention, date, bool, time | None]] = []
    warnings: list[str] = []
    invalid_mention_seen = False
    for mention in mentions:
        try:
            parsed_date, year_inferred = _parse_mention_date(mention.text, reference.date())
            parsed_time = _parse_mention_time(mention.text)
        except ProviderError as error:
            # Keep the candidate and its verbatim source reviewable.  A stale
            # or revoked malformed date must not abort the surrounding notice,
            # and must never be silently coerced to a plausible time.
            warnings.append(error.code)
            invalid_mention_seen = True
            continue
        parsed.append((mention, parsed_date, year_inferred, parsed_time))
    if not parsed:
        return None, list(dict.fromkeys(warnings))
    # A changed time on the same calendar day is still an ambiguous deadline.
    # Exact duplicate mentions are harmless (normalization may combine an
    # explicit provider value with the same verbatim source quote).
    unique_deadlines = {(item[1], item[3]) for item in parsed}
    if invalid_mention_seen:
        # An invalid date/time may be the actual DDL.  Do not silently borrow
        # another valid mention such as an answer-session or class-start time.
        # Only a direct, existing replacement marker can select a valid date.
        replacement = _explicit_replacement_deadline(value, parsed)
        if replacement is None:
            return None, list(dict.fromkeys([*warnings, "MULTIPLE_DATES_IN_SOURCE", "AMBIGUOUS_TASK_DATE"]))
        selected_mention, selected, year_inferred, parsed_time = replacement
        warnings.extend(("MULTIPLE_DATES_IN_SOURCE", "DATE_UPDATED_FROM_SOURCE"))
    elif len(unique_deadlines) > 1:
        replacement = _explicit_replacement_deadline(value, parsed)
        if replacement is None:
            return None, list(dict.fromkeys([*warnings, "MULTIPLE_DATES_IN_SOURCE", "AMBIGUOUS_TASK_DATE"]))
        selected_mention, selected, year_inferred, parsed_time = replacement
        warnings.extend(("MULTIPLE_DATES_IN_SOURCE", "DATE_UPDATED_FROM_SOURCE"))
    else:
        selected_mention, selected, year_inferred, parsed_time = parsed[0]
    if parsed_time is None and _has_unquantified_time_constraint(value, selected_mention):
        return None, list(dict.fromkeys([*warnings, "AMBIGUOUS_TASK_DATE"]))
    if year_inferred:
        warnings.append("DATE_YEAR_INFERRED")
    if parsed_time is None:
        warnings.append("TIME_DEFAULTED_TO_END_OF_DAY")
    resolved = datetime.combine(selected, parsed_time or time(23, 59))
    if resolved < reference:
        warnings.append("DATE_IN_PAST")
    return resolved, list(dict.fromkeys(warnings))


def _has_unquantified_time_constraint(value: str, mention: DeadlineMention) -> bool:
    """Reject a date-only default when the source imposes an unknown earlier time."""

    return bool(re.match(r"\s*(?:中午|上午|下午|晚上|早上|上课|课)\s*前", value[mention.end:]))


def _explicit_replacement_deadline(
    value: str,
    parsed: list[tuple[DeadlineMention, date, bool, time | None]],
) -> tuple[DeadlineMention, date, bool, time | None] | None:
    """Select a clearly evidenced replacement without guessing between dates.

    A strong change verb ("改到/改为") is sufficient.  Extension wording is
    accepted only when the replacement repeats the year, which preserves the
    existing conservative handling of short "原截止 9 月…延期到 9 月…" notes.
    """

    markers = list(_STRONG_RESCHEDULE_PATTERN.finditer(value))
    markers.extend(_EXTENSION_RESCHEDULE_PATTERN.finditer(value))
    if not markers:
        return None
    marker = max(markers, key=lambda item: item.start())
    after = [item for item in parsed if item[0].start >= marker.end()]
    if len(after) != 1:
        return None
    # The replacement date must directly follow the change verb.  This avoids
    # treating "提交方式改为线上，答疑安排在 9 月 16 日" as a deadline change.
    between = value[marker.end():after[0][0].start]
    if not re.fullmatch(r"\s*(?:至|为)?\s*", between):
        return None
    if _EXTENSION_RESCHEDULE_PATTERN.fullmatch(marker.group(0)) and not re.search(r"\d{4}", after[0][0].text):
        return None
    return after[0]


def _parse_mention_date(value: str, reference: date) -> tuple[date, bool]:
    numeric = re.search(
        r"(?P<year>\d{4})年\s*(?P<month>\d{1,2})月\s*(?P<day>\d{1,2})日?"
        r"|(?P<year2>\d{4})[-/](?P<month2>\d{1,2})[-/](?P<day2>\d{1,2})"
        r"|(?P<month3>\d{1,2})月\s*(?P<day3>\d{1,2})日?"
        r"|(?P<month4>\d{1,2})/(?P<day4>\d{1,2})",
        value,
    )
    if numeric:
        year_text = numeric.group("year") or numeric.group("year2")
        year = int(year_text or reference.year)
        month = int(numeric.group("month") or numeric.group("month2") or numeric.group("month3") or numeric.group("month4"))
        day = int(numeric.group("day") or numeric.group("day2") or numeric.group("day3") or numeric.group("day4"))
        try:
            return date(year, month, day), year_text is None
        except ValueError as error:
            raise ProviderError("INVALID_DATE", f"抽取到无效日期：{year}-{month}-{day}") from error

    month_names = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    english = re.search(
        r"\b(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(?P<day>\d{1,2})(?:,\s*(?P<year>\d{4}))?",
        value,
        re.IGNORECASE,
    )
    if english:
        year_text = english.group("year")
        year = int(year_text or reference.year)
        try:
            return date(year, month_names[english.group("month").lower()], int(english.group("day"))), year_text is None
        except ValueError as error:
            raise ProviderError("INVALID_DATE", "抽取到无效英文日期") from error

    if "大后天" in value:
        return reference + timedelta(days=3), False
    for label, offset in (("今天", 0), ("明天", 1), ("后天", 2)):
        if label in value:
            return reference + timedelta(days=offset), False
    if "下周末" in value or "next weekend" in value.lower():
        return reference + timedelta(days=(7 - reference.weekday()) + 6), False
    if "本周末" in value or "周末" in value:
        return reference + timedelta(days=6 - reference.weekday()), False
    weekday_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
    relative_weekday = re.search(r"(下周|本周|星期|周)([一二三四五六日天])", value)
    if relative_weekday:
        prefix, weekday = relative_weekday.groups()
        if prefix == "下周":
            delta = 7 - reference.weekday() + weekday_map[weekday]
        elif prefix == "本周":
            delta = weekday_map[weekday] - reference.weekday()
        else:
            delta = (weekday_map[weekday] - reference.weekday()) % 7
        return reference + timedelta(days=delta), False
    lowered = value.lower()
    if "tomorrow" in lowered:
        return reference + timedelta(days=1), False
    if "today" in lowered:
        return reference, False
    english_weekday = re.search(r"next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", lowered)
    if english_weekday:
        names = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
        return reference + timedelta(days=7 - reference.weekday() + names.index(english_weekday.group(1))), False
    raise ProviderError("INVALID_DATE", "无法解析抽取到的日期")


def _parse_mention_time(value: str) -> time | None:
    prefix = re.search(
        r"(上午|下午|晚上|中午|早上|凌晨)\s*(\d{1,2})"
        r"(?:(?:[:：](\d{1,2}))|(?:[点时](?:\s*(\d{1,2})\s*分?)?))?",
        value,
    )
    suffix = re.search(r"(?<!\d)(\d{1,2})(?:[:：](\d{1,2}))?\s*(AM|PM)\b", value, re.IGNORECASE)
    plain = re.search(
        r"(?<!\d)(\d{1,2})(?:(?:[:：](\d{1,2}))|(?:[点时](?:\s*(\d{1,2})\s*分?)?))",
        value,
    )
    if prefix:
        meridiem = prefix.group(1)
        hour = int(prefix.group(2))
        minute = int(prefix.group(3) or prefix.group(4) or 0)
        if meridiem in {"下午", "晚上", "中午"} and hour < 12:
            hour += 12
        if meridiem in {"上午", "早上", "凌晨"} and hour == 12:
            hour = 0
    elif suffix:
        hour, minute = int(suffix.group(1)), int(suffix.group(2) or 0)
        if suffix.group(3).lower() == "pm" and hour < 12:
            hour += 12
        if suffix.group(3).lower() == "am" and hour == 12:
            hour = 0
    elif plain:
        hour = int(plain.group(1))
        minute = int(plain.group(2) or plain.group(3) or 0)
    else:
        return None
    if hour > 23 or minute > 59:
        raise ProviderError("INVALID_TIME", f"抽取到无效时间：{hour}:{minute:02d}")
    return time(hour, minute)


def _has_invalid_deadline_time(value: str) -> bool:
    """Detect malformed clock text without assigning it a replacement time."""

    for mention in find_deadline_mentions(value):
        try:
            _parse_mention_time(mention.text)
        except ProviderError as error:
            if error.code == "INVALID_TIME":
                return True
    return False

_FILENAME_TASK_SUFFIX = re.compile(
    r"^(?P<course>.+?)\s*[-_—–]\s*"
    r"(?P<hint>作业|实验|报告|考试|测验|DDL)"
    r"(?:通知|安排|要求|报告)?$",
    re.IGNORECASE,
)


def _filename_stem(filename: str) -> str:
    return Path(filename or "").stem.strip()


def _has_task_hint(value: str) -> bool:
    lowered = value.lower()
    return any(hint in value or hint in lowered for hint in _TASK_HINTS)


def _course_name_from_filename(filename: str) -> str | None:
    stem = _filename_stem(filename)
    match = _FILENAME_TASK_SUFFIX.fullmatch(stem)
    if not match:
        return None
    course = match.group("course").strip(" -_—–·。")
    if not course or course.casefold() in {"通知", "课程", "course", "作业", "实验", "报告", "考试", "ddl"}:
        return None
    return course[:120]


def _filename_task_name(filename: str) -> str:
    stem = _filename_stem(filename)
    if not stem:
        return "待确认任务"
    course = _course_name_from_filename(filename)
    if course:
        suffix = stem[len(course) :].strip(" -_—–·")
        if suffix:
            return suffix[:200]
    return stem[:200]


from app.services.material_intent import describe_material, is_learning_activity, REVIEW_OUTLINE


class RuleBasedProvider:
    name = "local-rules"

    def extract(self, text: str, filename: str) -> dict[str, Any]:
        lines = _source_lines(text)
        filename_stem = _filename_stem(filename)
        filename_course = _course_name_from_filename(filename)

        course_name = None
        for line, _, _ in lines:
            match = _COURSE_LINE_PATTERN.fullmatch(line)
            if match:
                course_name = match.group(1).strip(" 。")[:120]
                break
        course_name = course_name or filename_course

        parts = _task_parts(text)
        tasks: list[dict[str, Any]] = []
        consumed: set[int] = set()
        for index, part in enumerate(parts):
            line, start, end = part.text, part.start, part.end
            if index in consumed or _COURSE_LINE_PATTERN.fullmatch(line.strip("。！？")):
                continue
            if is_learning_activity(line, filename) or not _is_task_part(line):
                continue

            quote_start, quote_end = start, end
            mentions = find_deadline_mentions(line)
            header = re.match(
                r"^(?:关于[^：:\r\n]{1,60}|[^：:\r\n]{1,60}(?:通知|提醒|安排|任务如下))\s*[：:]",
                line,
            )
            if header and len(mentions) > 1:
                suffix = line[header.end():]
                if _ACTION_WORD_PATTERN.search(suffix) and find_deadline_mentions(suffix):
                    quote_start = start + header.end()
            if not mentions and index + 1 < len(parts):
                next_part = parts[index + 1]
                if _is_deadline_only(next_part.text):
                    quote_end = next_part.end
                    consumed.add(index + 1)
            if not find_deadline_mentions(text[quote_start:quote_end]) and index > 0 and _is_participation_part(line):
                previous = parts[index - 1]
                if find_deadline_mentions(previous.text) and _looks_like_event_context(previous.text):
                    quote_start = previous.start
            invalid_revoked_context = False
            if index > 0:
                previous = parts[index - 1]
                invalid_revoked_context = bool(
                    _NEGATED_OR_FINISHED_PATTERN.search(previous.text)
                    and _has_invalid_deadline_time(previous.text)
                )
            quote = text[quote_start:quote_end].strip()
            candidate = self._candidate(quote, quote_start, quote_end, text, filename_stem, course_name, filename)
            if invalid_revoked_context:
                # The original material remains unchanged and the candidate
                # points to the live replacement clause.  Flag it for review
                # instead of reviving the cancelled historical task or
                # inventing a value for its malformed clock.
                candidate["warnings"].append("INVALID_TIME")
                candidate["need_review"] = True
            tasks.append(candidate)

        # A task-specific filename can conservatively label a bare deadline,
        # preserving the original local-provider behavior.
        if not tasks and filename_course and _has_task_hint(filename_stem) and not REVIEW_OUTLINE.search(f"{filename}\n{text}") and not _clearly_informational_notice(text):
            for part in parts:
                if _is_deadline_only(part.text):
                    tasks.append(
                        self._candidate(
                            part.text, part.start, part.end, text, filename_stem, course_name, filename,
                            use_filename_name=True,
                        )
                    )
                    break

        for candidate_index, task in enumerate(tasks, start=1):
            task["candidate_id"] = f"rule-{candidate_index}"

        tags: list[str] = []
        for label, words in {
            "DDL": ("截止", "due", "submit", "ddl"),
            "作业": ("作业", "assignment", "homework"),
            "实验": ("实验", "lab"),
            "报告": ("报告", "report"),
            "考试": ("考试", "exam", "quiz"),
        }.items():
            if any(word in f"{filename_stem}\n{text}".lower() for word in words):
                tags.append(label)
        # Plain course notes can validly contain no task.  A deadline-looking
        # expression with no attributable task is the case that needs review.
        result_warnings = (
            ["NO_TASK_CANDIDATE"]
            if not tasks and find_deadline_mentions(text) and not REVIEW_OUTLINE.search(f"{filename}\n{text}") and not is_learning_activity(text) and not _clearly_informational_notice(text)
            else []
        )
        return {
            "course_name": course_name,
            "material_type": describe_material(text, filename, tasks)["material_type"],
            "tags": tags,
            "tasks": tasks,
            "warnings": result_warnings,
            "needs_review": bool(result_warnings),
        }

    def _candidate(
        self,
        quote: str,
        _start: int,
        _end: int,
        _source: str,
        filename_stem: str,
        course_name: str | None,
        filename: str,
        *,
        use_filename_name: bool = False,
    ) -> dict[str, Any]:
        mentions = find_deadline_mentions(quote)
        entity_count = len(_TASK_ENTITY_PATTERN.findall(quote))
        warnings: list[str] = []
        if len(mentions) > 1:
            warnings.append("MULTIPLE_DATES_IN_SOURCE")
        if entity_count > 1:
            warnings.append("AMBIGUOUS_TASK_ASSOCIATION")
        if _CONDITIONAL_AUDIENCE_PATTERN.search(quote):
            warnings.append("CONDITIONAL_AUDIENCE")
        if _POSTPONED_PATTERN.search(quote):
            warnings.append("DEADLINE_PENDING")
        if _VAGUE_DATE_PATTERN.search(quote) and not mentions:
            warnings.append("VAGUE_DUE_DATE")
        name = _filename_task_name(filename) if use_filename_name else _task_name(quote)
        task_type = self._task_type(quote)
        filename_task_type = self._task_type(filename_stem)
        if task_type in {"其他", "DDL"} and filename_task_type != "其他":
            task_type = filename_task_type
        combined = f"{filename_stem}\n{quote}".lower()
        return {
            "course_name": course_name,
            "name": (name or _filename_task_name(filename))[:200],
            "task_type": task_type,
            "description": quote[:500],
            "due_at": quote if mentions else None,
            "priority": 4 if any(word in combined for word in ("考试", "截止", "exam", "due", "ddl")) else 3,
            "source_quote": quote[:1000],
            "confidence": 0.92 if mentions and not warnings else 0.78 if mentions else 0.58,
            "warnings": warnings,
            "need_review": bool(warnings),
        }

    @staticmethod
    def _task_type(line: str) -> str:
        lowered = line.lower()
        if "考试" in line or "exam" in lowered or "quiz" in lowered:
            return "考试"
        if "实验" in line or "lab" in lowered:
            return "实验"
        if "报告" in line or "report" in lowered:
            return "报告"
        if "作业" in line or "assignment" in lowered or "homework" in lowered:
            return "作业"
        if "ddl" in lowered or "截止" in line or "due" in lowered or "submit" in lowered:
            return "DDL"
        return "其他"


@dataclass(frozen=True)
class SourcePart:
    text: str
    start: int
    end: int


def _task_parts(text: str) -> list[SourcePart]:
    """Split prose at safe task boundaries while retaining exact source spans."""

    sentences: list[SourcePart] = []
    for match in re.finditer(r"[^。！？\r\n]+[。！？]?", text):
        raw = match.group(0)
        left = len(raw) - len(raw.lstrip())
        right = len(raw.rstrip())
        if right > left:
            sentences.append(SourcePart(raw[left:right], match.start() + left, match.start() + right))

    parts: list[SourcePart] = []
    for sentence in sentences:
        semicolon_start = 0
        semicolon_matches = list(re.finditer(r"[；;]", sentence.text))
        for separator in semicolon_matches + [None]:
            semicolon_end = separator.start() if separator else len(sentence.text)
            raw_part = SourcePart(
                sentence.text[semicolon_start:semicolon_end],
                sentence.start + semicolon_start,
                sentence.start + semicolon_end,
            )
            parts.extend(_split_comma_task_boundaries(raw_part))
            semicolon_start = separator.end() if separator else len(sentence.text)
    return [part for part in parts if part.text.strip()]


def _split_comma_task_boundaries(part: SourcePart) -> list[SourcePart]:
    boundaries: list[int] = []
    cursor = 0
    for separator in re.finditer(r"[，,]", part.text):
        left = part.text[cursor:separator.start()]
        right_match = re.match(r"(?:但|但是|并且?|同时|另(?:外)?)?([^，,]*)", part.text[separator.end():])
        right = right_match.group(0) if right_match else part.text[separator.end():]
        if re.match(r"\s*(?:现|目前)?\s*(?:延长|延后|延期|延至|改到|改为|调整到|调整为)", right):
            continue
        left_action = bool(_ACTION_WORD_PATTERN.search(left))
        right_action = bool(_ACTION_WORD_PATTERN.search(right))
        both_dated = bool(find_deadline_mentions(left) and find_deadline_mentions(right))
        negative_then_active = bool(_NEGATED_OR_FINISHED_PATTERN.search(left) and right_action)
        conjoined_new_deadline = bool(re.match(r"(?:并|同时|另(?:外)?)\s*(?:请)?\s*(?:在|于)?", right)) and bool(
            find_deadline_mentions(right)
        )
        if right_action and (negative_then_active or (left_action and both_dated) or (left_action and conjoined_new_deadline)):
            boundaries.append(separator.start())
            cursor = separator.end()
    if not boundaries:
        return [SourcePart(part.text.strip(), part.start + len(part.text) - len(part.text.lstrip()), part.end - (len(part.text) - len(part.text.rstrip())))]

    results: list[SourcePart] = []
    begin = 0
    for boundary in boundaries + [len(part.text)]:
        raw = part.text[begin:boundary]
        left_trim = len(raw) - len(raw.lstrip(" ，,"))
        right_trim = len(raw.rstrip())
        if right_trim > left_trim:
            results.append(SourcePart(raw[left_trim:right_trim], part.start + begin + left_trim, part.start + begin + right_trim))
        begin = boundary + (1 if boundary < len(part.text) else 0)
    return results


def _is_task_part(value: str) -> bool:
    if _NEGATED_OR_FINISHED_PATTERN.search(value) and not _POSTPONED_PATTERN.search(value):
        return False
    if re.search(r"维护|(?:上传|提交|登记)功能[^。；;！？]{0,30}(?:恢复|开放)", value) and not _OBLIGATION_PATTERN.search(value):
        return False
    if re.search(r"(?:报名|预约|系统|平台|功能)[^。；;！？]{0,20}(?:已|已经)(?:开放|恢复)", value) and not _OBLIGATION_PATTERN.search(value):
        return False
    if _INFORMATIONAL_UPLOAD_PATTERN.search(value) and not _OBLIGATION_PATTERN.search(value):
        return False
    has_entity = bool(_TASK_ENTITY_PATTERN.search(value))
    actions = list(_ACTION_WORD_PATTERN.finditer(value))
    if actions and re.search(r"(?:等待?|待)[^，。；;！？]{0,12}确认|(?:场地|课堂|老师|教师)确认", value):
        actions = [match for match in actions if match.group(0) != "确认"]
    if actions:
        return has_entity or bool(find_deadline_mentions(value)) or bool(_OBLIGATION_PATTERN.search(value)) or bool(
            _POSTPONED_PATTERN.search(value)
        )
    if has_entity:
        return True
    # A rescheduled deadline can imply submission of the named document even
    # when the notice omits the verb in its shortened correction wording.
    return bool(
        ("截止" in value or _POSTPONED_PATTERN.search(value))
        and (_STRONG_RESCHEDULE_PATTERN.search(value) or _EXTENSION_RESCHEDULE_PATTERN.search(value))
    )


def _is_deadline_only(value: str) -> bool:
    return bool(find_deadline_mentions(value)) and not _ACTION_WORD_PATTERN.search(value) and not _TASK_ENTITY_PATTERN.search(value)


def _is_participation_part(value: str) -> bool:
    return bool(re.search(r"参加|\battend\b", value, re.IGNORECASE))


def _looks_like_event_context(value: str) -> bool:
    return bool(re.search(r"说明会|答疑|培训|会议|讲座|活动|实习|集合|\b(?:meeting|briefing|training|lecture)\b", value, re.IGNORECASE))


def _clearly_informational_notice(value: str) -> bool:
    return bool(
        _NEGATED_OR_FINISHED_PATTERN.search(value)
        or _INFORMATIONAL_UPLOAD_PATTERN.search(value)
        or re.search(r"维护|照常|自动恢复|仅供查看|只是通知|不是(?:提交|登记|参加).*截止", value)
    )


def _source_lines(text: str) -> list[tuple[str, int, int]]:
    records: list[tuple[str, int, int]] = []
    for match in re.finditer(r"[^\r\n]+", text):
        raw = match.group(0)
        left = len(raw) - len(raw.lstrip())
        right = len(raw.rstrip())
        if right > left:
            records.append((raw[left:right], match.start() + left, match.start() + right))
    return records


def _unambiguous_clauses(line: str, source_start: int) -> list[tuple[str, int, int]]:
    parts: list[tuple[str, int, int]] = []
    cursor = 0
    for separator in list(_CLAUSE_SEPARATOR_PATTERN.finditer(line)) + [None]:
        end = separator.start() if separator else len(line)
        raw = line[cursor:end]
        left = len(raw) - len(raw.lstrip())
        right = len(raw.rstrip())
        if right > left:
            clause = raw[left:right]
            parts.append((clause, source_start + cursor + left, source_start + cursor + right))
        cursor = separator.end() if separator else len(line)
    if len(parts) < 2:
        return []
    if all(len(_TASK_ENTITY_PATTERN.findall(part[0])) == 1 and len(find_deadline_mentions(part[0])) == 1 for part in parts):
        return parts
    return []


def _task_name(value: str) -> str:
    clean = value.strip()

    postponed = re.search(r"提交的(?P<object>[^，。；;！？]{1,100}?)(?:暂缓|暂停)", clean)
    if postponed:
        return f"提交{postponed.group('object').strip()}"

    implicit_document = re.search(
        r"(?:通知更正[:：]?\s*)?(?P<object>(?:《[^》]+》)?[^，。；;！？]{1,70}?)"
        r"原定[^，。；;！？]*截止",
        clean,
    )
    if implicit_document and (_STRONG_RESCHEDULE_PATTERN.search(clean) or _EXTENSION_RESCHEDULE_PATTERN.search(clean)):
        object_name = implicit_document.group("object").strip(" ：:")
        if object_name:
            return f"提交{object_name}"

    send_to = re.search(r"将(?P<object>[^，。；;！？]{1,80}?)发给(?P<recipient>[^，。；;！？]{1,30})", clean)
    if send_to:
        recipient = _strip_task_tail(send_to.group("recipient"))
        return f"将{send_to.group('object').strip()}发给{recipient}"

    gathering = re.search(r"到(?P<place>[^，。；;！？]{1,30}?)集合", clean)
    if gathering:
        return f"到{gathering.group('place').strip()}集合"

    registration = re.search(r"向(?P<recipient>[^，。；;！？]{1,20}?)登记", clean)
    if registration:
        condition = re.search(r"如需(?P<object>[^，。；;！？]{1,30})", clean)
        object_name = condition.group("object").strip() if condition else ""
        return f"向{registration.group('recipient').strip()}登记{object_name}"

    action_matches = [
        match
        for match in re.finditer(r"提交|上传|填写|登记|确认|参加|完成|预约|签到|报到|缴纳", clean)
        if not clean[match.end():].startswith("后")
        and not (match.group(0) == "登记" and clean[match.end():].startswith("表"))
        and not (match.group(0) == "提交" and re.match(r"(?:日期|时间|方式|要求|入口|平台|功能)", clean[match.end():]))
        and not (match.group(0) == "确认" and re.search(r"(?:场地|课堂|老师|教师)$", clean[:match.start()]))
    ]
    if action_matches:
        selected = action_matches[-1]
        for match in action_matches:
            if match.group(0) == "完成" and re.match(r"(?:线上|在线)?预约", clean[match.end():]):
                selected = match
                break
        action = selected.group(0)
        tail = _strip_task_tail(clean[selected.end():])
        if action == "完成" and tail in {"预约", "线上预约", "在线预约"}:
            context = re.search(r"需要参加(?P<object>[^，。；;！？]{1,50}?)的同学", clean)
            if context:
                tail = f"{context.group('object').strip()}{tail}"
        if action == "参加" and not tail:
            event = _event_name_from_context(clean[:selected.start()])
            if event:
                tail = event
        if action == "完成" and not tail:
            object_before = re.search(r"(?P<object>[^，。；;！？:：]{1,80}?)请(?:在)?(?:近期)?\s*$", clean[:selected.start()])
            if object_before:
                tail = object_before.group("object").strip()
        if tail:
            # Legacy entity-first forms such as "作业二：完成矩阵习题"
            # already have a concise and useful label.
            entity = _TASK_ENTITY_PATTERN.search(clean)
            if action == "提交" and entity and entity.start() >= selected.end() and not _OBLIGATION_PATTERN.search(clean):
                legacy = _legacy_task_name(clean)
                if legacy:
                    return legacy
            if entity and entity.start() < selected.start() and not re.search(r"课程提醒|通知更正|需要.*的同学", clean):
                legacy = _legacy_task_name(clean)
                if legacy:
                    return legacy
            return f"{action}{tail}"

    return _legacy_task_name(clean)


def _strip_task_tail(value: str) -> str:
    tail = value
    for mention in find_deadline_mentions(tail):
        tail = tail[:mention.start]
        break
    tail = re.split(r"[，,。；;！？]", tail, maxsplit=1)[0]
    tail = re.split(r"截止(?:日期|时间)?|(?:请)?在\s*$|(?:前)?(?:完成|提交)?后|届时|仍为|不要|无需|不必", tail, maxsplit=1)[0]
    tail = re.sub(r"^(?:请|于|在|前|向)\s*", "", tail)
    return tail.strip(" 的，,。；;：:、 ")


def _event_name_from_context(value: str) -> str:
    masked = value
    for mention in reversed(find_deadline_mentions(masked)):
        masked = f"{masked[:mention.start]} {masked[mention.end:]}"
    candidates = list(
        re.finditer(
            r"(?P<event>(?:《[^》]+》)?[^，。；;！？\r\n]{0,45}?(?:说明会|答疑|培训|会议|讲座|活动|实习))",
            masked,
        )
    )
    if not candidates:
        return ""
    event = candidates[-1].group("event")
    event = re.sub(r"^(?:因[^，。；;！？]+，)?(?:原定|安排在|召开|关于)\s*", "", event)
    event = re.sub(r"^(?:下午|上午|晚上|中午)?\s*\d{1,2}(?:[:：]\d{1,2})?\s*", "", event)
    event = re.sub(r"^.*?(?=《)", "", event) if "《" in event else event
    event = re.sub(r"^(?:的)?\s*", "", event)
    return event.strip(" ：:，,。；;、")


def _legacy_task_name(value: str) -> str:
    pieces: list[str] = []
    cursor = 0
    for mention in find_deadline_mentions(value):
        pieces.append(value[cursor:mention.start])
        cursor = mention.end
    pieces.append(value[cursor:])
    name = "".join(pieces)
    name = re.sub(
        r"\b(?:due|submit(?:\s+by)?)\b|截止(?:日期|时间)?到|截止(?:日期|时间)?|原截止|"
        r"延期到|现延至|延至|原定|提交时间|提交|开始|请在|请于",
        " ",
        name,
        flags=re.IGNORECASE,
    )
    name = re.sub(r"(?:于|前)\s*$", " ", name)
    name = re.sub(r"(?:分别)?在(?=\s*[,，、;；]|\s*$)", " ", name)
    name = re.sub(r"\s+", " ", name).strip(" -：:，,。；;、")
    return name


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def extract(self, text: str, filename: str) -> dict[str, Any] | str:
        if not settings.llm_api_key or not settings.llm_model:
            raise ProviderError("LLM_NOT_CONFIGURED", "未配置 LLM_API_KEY 和 LLM_MODEL，已回退到本地规则抽取")
        try:
            from openai import OpenAI

            client_kwargs = {"api_key": settings.llm_api_key}
            if settings.llm_base_url:
                client_kwargs["base_url"] = settings.llm_base_url
            client = OpenAI(
                **client_kwargs,
                timeout=settings.llm_timeout_seconds,
                max_retries=settings.llm_max_retries,
            )
            response = client.chat.completions.create(
                model=settings.llm_model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你负责整理学习资料并识别真实义务。只输出JSON，字段为 course_name、material_type、tags、tasks。"
                            "tasks中的每项包含name、task_type、description、due_at、priority、source_quote、confidence。"
                            "tasks仅包含需要提交、参加或完成的正式任务。复习提纲、阅读安排、自测练习和个人复习计划中的日期不属于截止任务；没有任务时返回空数组。混合文档仍须保留明确的提交要求。"
                            "material_type区分复习资料、复习安排、课堂讲义、作业要求、课程通知等。无法确认的字段使用null，并保留原文source_quote。"
                        ),
                    },
                    {"role": "user", "content": f"文件名：{filename}\n正文：\n{text}"},
                ],
            )
            content = response.choices[0].message.content or ""
            return json.loads(content)
        except ProviderError:
            raise
        except json.JSONDecodeError as exc:
            raise ProviderError("INVALID_PROVIDER_JSON", "模型返回的结构化结果不是有效 JSON") from exc
        except Exception as exc:
            raise ProviderError("LLM_REQUEST_FAILED", "模型调用失败，请稍后重试或使用本地规则抽取") from exc


def external_provider_available() -> bool:
    return bool(settings.llm_api_key and settings.llm_model)


def get_provider(provider_name: str = "local-rules") -> LLMProvider:
    if provider_name == "local-rules":
        return RuleBasedProvider()
    if provider_name == "openai-compatible":
        if not external_provider_available():
            raise ProviderError("LLM_NOT_CONFIGURED", "外部 AI API 尚未配置，请先设置 LLM_API_KEY 和 LLM_MODEL")
        return OpenAICompatibleProvider()
    raise ProviderError("INVALID_EXTRACTION_PROVIDER", "不支持的抽取方式")
