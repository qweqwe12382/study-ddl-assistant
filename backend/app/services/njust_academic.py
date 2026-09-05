"""Privacy-bounded NJUST academic-calendar adapter.

Only the opaque captcha session and the upstream cookie jar live in process
memory.  Credentials, raw teaching-system HTML and cookies are never written
to disk.  The upstream URLs are deliberately fixed so this adapter cannot be
turned into a credential-forwarding or SSRF endpoint.
"""

from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from datetime import date, datetime, time
import hashlib
import re
import secrets
from threading import Lock
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, NavigableString
import requests

from app.services.academic_calendar_sync import source_key


NJUST_ORIGIN = "http://202.119.81.112:9080"
NJUST_PORTAL_ORIGIN = "http://202.119.81.112:8080"
NJUST_PORTAL_INIT_URL = f"{NJUST_PORTAL_ORIGIN}/Logon.do?method=logonurl"
NJUST_PORTAL_LOGIN_URL = f"{NJUST_PORTAL_ORIGIN}/Logon.do?method=logon"
NJUST_PORTAL_CAPTCHA_URL = f"{NJUST_PORTAL_ORIGIN}/verifycode.servlet"
NJUST_DIRECT_LOGIN_URL = f"{NJUST_ORIGIN}/njlgdx/xk/LoginToXk"
NJUST_DIRECT_CAPTCHA_URL = f"{NJUST_ORIGIN}/njlgdx/verifycode.servlet"
NJUST_SCHEDULE_URL = f"{NJUST_ORIGIN}/njlgdx/xskb/xskb_list.do?Ves632DSdyV=NEW_XSD_PYGL"
NJUST_EXAMS_URL = f"{NJUST_ORIGIN}/njlgdx/xsks/xsksap_list"
NJUST_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
SESSION_TTL_SECONDS = 300
MAX_REMOTE_BYTES = 3_000_000
CHINA_ZONE = ZoneInfo("Asia/Shanghai")

SECTION_TIMES: dict[int, tuple[time, time]] = {
    1: (time(8, 0), time(8, 45)),
    2: (time(8, 50), time(9, 35)),
    3: (time(9, 40), time(10, 25)),
    4: (time(10, 40), time(11, 25)),
    5: (time(11, 30), time(12, 15)),
    6: (time(14, 0), time(14, 45)),
    7: (time(14, 50), time(15, 35)),
    8: (time(15, 50), time(16, 35)),
    9: (time(16, 40), time(17, 25)),
    10: (time(17, 30), time(18, 15)),
    11: (time(19, 0), time(19, 45)),
    12: (time(19, 50), time(20, 35)),
    13: (time(20, 40), time(21, 25)),
}


class NjustAcademicError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass
class _SessionEntry:
    owner_key: str
    session: requests.Session
    strategy: str
    expires_at: float


class NjustSessionStore:
    """Small, owner-bound, one-shot in-memory cookie store."""

    def __init__(self) -> None:
        self._entries: dict[str, _SessionEntry] = {}
        self._lock = Lock()

    @staticmethod
    def _new_http_session() -> requests.Session:
        session = requests.Session()
        # Do not let environment-configured proxies see NJUST credentials.
        session.trust_env = False
        session.headers.update({"User-Agent": NJUST_USER_AGENT})
        return session

    def _purge_locked(self, now: float) -> None:
        expired = [key for key, entry in self._entries.items() if entry.expires_at <= now]
        for key in expired:
            self._entries.pop(key).session.close()

    @staticmethod
    def _captcha_response(session: requests.Session, strategy: str) -> requests.Response:
        if strategy == "portal_post":
            session.get(NJUST_PORTAL_INIT_URL, timeout=(4, 8), allow_redirects=True).raise_for_status()
            return session.get(NJUST_PORTAL_CAPTCHA_URL, timeout=(4, 8), allow_redirects=False)
        return session.get(NJUST_DIRECT_CAPTCHA_URL, timeout=(4, 8), allow_redirects=False)

    @staticmethod
    def _captcha_payload(response: requests.Response) -> tuple[bytes, str]:
        response.raise_for_status()
        content = response.content
        declared = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
        detected = (
            "image/jpeg" if content.startswith(b"\xff\xd8\xff") else
            "image/png" if content.startswith(b"\x89PNG\r\n\x1a\n") else
            "image/gif" if content.startswith((b"GIF87a", b"GIF89a")) else ""
        )
        content_type = detected or declared
        if content_type not in {"image/jpeg", "image/png", "image/gif"} or not content or len(content) > 1_000_000:
            raise NjustAcademicError("NJUST_CAPTCHA_INVALID", "教务系统返回了无效验证码，请稍后重试", 502)
        return content, content_type

    def create(self, owner_key: str) -> tuple[str, str]:
        session: requests.Session | None = None
        last_error: Exception | None = None
        for strategy in ("portal_post", "direct_get"):
            session = self._new_http_session()
            try:
                content, content_type = self._captcha_payload(self._captcha_response(session, strategy))
                break
            except (NjustAcademicError, requests.RequestException) as exc:
                last_error = exc
                session.close()
        else:
            if isinstance(last_error, NjustAcademicError):
                raise last_error
            raise NjustAcademicError(
                "NJUST_NETWORK_UNAVAILABLE",
                "无法连接南理工教务系统，请确认已连接校园网或学校 VPN",
                502,
            ) from None
        assert session is not None

        session_id = secrets.token_urlsafe(32)
        with self._lock:
            now = monotonic()
            self._purge_locked(now)
            # Bound memory even if a client repeatedly abandons captcha flows.
            if len(self._entries) >= 100:
                oldest_key = min(self._entries, key=lambda key: self._entries[key].expires_at)
                self._entries.pop(oldest_key).session.close()
            self._entries[session_id] = _SessionEntry(owner_key, session, strategy, now + SESSION_TTL_SECONDS)
        return session_id, f"data:{content_type};base64,{b64encode(content).decode('ascii')}"

    def consume(self, session_id: str, owner_key: str) -> tuple[requests.Session, str]:
        with self._lock:
            now = monotonic()
            self._purge_locked(now)
            entry = self._entries.get(session_id)
            if entry is None or entry.owner_key != owner_key:
                raise NjustAcademicError("NJUST_SESSION_EXPIRED", "验证码会话已过期，请重新获取", 400)
            self._entries.pop(session_id)
        return entry.session, entry.strategy

    def discard(self, session_id: str, owner_key: str) -> None:
        with self._lock:
            entry = self._entries.get(session_id)
            if entry is None or entry.owner_key != owner_key:
                return
            self._entries.pop(session_id)
        entry.session.close()


njust_session_store = NjustSessionStore()


def _safe_remote_text(response: requests.Response) -> str:
    response.raise_for_status()
    if len(response.content) > MAX_REMOTE_BYTES:
        raise NjustAcademicError("NJUST_RESPONSE_TOO_LARGE", "教务系统返回内容异常，已停止读取", 502)
    declared = (response.encoding or "").lower()
    candidates = [declared] if declared and declared not in {"iso-8859-1", "ascii"} else []
    candidates.extend(["utf-8", "gb18030"])
    for encoding in dict.fromkeys(candidates):
        try:
            return response.content.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return response.content.decode("utf-8", errors="replace")


def fetch_njust_pages(
    session: requests.Session,
    *,
    strategy: str,
    username: str,
    password: str,
    captcha: str,
    term: str,
) -> tuple[str, str]:
    """Authenticate once, fetch schedule/exams, then let the caller close the session."""

    try:
        if strategy == "portal_post":
            login = session.post(
                NJUST_PORTAL_LOGIN_URL,
                data={
                    "USERNAME": username,
                    "PASSWORD": password,
                    "useDogCode": "",
                    "RANDOMCODE": captcha,
                    "encoded": "",
                },
                headers={"Referer": NJUST_PORTAL_INIT_URL},
                timeout=(4, 10),
                allow_redirects=True,
            )
        else:
            login = session.get(
                NJUST_DIRECT_LOGIN_URL,
                params={"method": "verify", "USERNAME": username, "PASSWORD": password, "RANDOMCODE": captcha},
                timeout=(4, 10),
                allow_redirects=False,
            )
        if login.status_code != 302:
            body = _safe_remote_text(login)
            if not any(marker in body for marker in ("退出", "欢迎", "个人信息", "个人中心", "理论课表", "main.jsp", "logout")):
                raise NjustAcademicError("NJUST_AUTH_FAILED", "账号、密码或验证码不正确，请重新获取验证码后再试", 401)

        schedule = session.post(
            NJUST_SCHEDULE_URL,
            data={"xnxq01id": term, "zc": ""},
            timeout=(4, 12),
            allow_redirects=False,
        )
        exams = session.post(
            NJUST_EXAMS_URL,
            data={"xnxqid": term},
            timeout=(4, 12),
            allow_redirects=False,
        )
        schedule_text = _safe_remote_text(schedule)
        exams_text = _safe_remote_text(exams)
        if "kbtable" not in schedule_text and "kbcontent" not in schedule_text:
            raise NjustAcademicError("NJUST_SCHEDULE_UNAVAILABLE", "教务系统未返回课表，请核对学期或稍后重试", 502)
        return schedule_text, exams_text
    except NjustAcademicError:
        raise
    except requests.RequestException:
        raise NjustAcademicError(
            "NJUST_NETWORK_UNAVAILABLE",
            "读取南理工教务数据失败，请确认校园网连接后重试",
            502,
        ) from None


def _clean(value: Any, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _course_blocks(cell) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    for div in cell.find_all("div", class_="kbcontent"):
        current: dict[str, str] = {}
        for node in div.contents:
            if getattr(node, "name", None) == "br":
                continue
            title = ""
            if isinstance(node, NavigableString):
                text_value = _clean(node, 160)
            else:
                title = _clean(node.get("title", ""), 30)
                text_value = _clean(node.get_text(" ", strip=True), 160)
            if not text_value:
                continue
            if "---" in text_value:
                if current.get("name"):
                    blocks.append(current)
                current = {}
            elif title == "老师":
                current["teacher"] = text_value
            elif title == "周次(节次)":
                current["weeks"] = text_value
            elif title == "教室":
                current["room"] = text_value
            else:
                if current.get("name") and any(current.get(key) for key in ("teacher", "weeks", "room")):
                    blocks.append(current)
                    current = {}
                current.setdefault("name", text_value)
        if current.get("name"):
            blocks.append(current)
    return blocks


def parse_njust_schedule(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    day_names = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7}
    exact_times: dict[tuple[str, int], tuple[int, int]] = {}
    data_rows: list[dict[str, Any]] = []
    detail_table = soup.find("table", id="dataList")
    if detail_table:
        for row in detail_table.find_all("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 6:
                continue
            name_text = _clean(cells[3].get_text(), 120)
            name = re.sub(r"\s+", "", name_text)
            detail = cells[5].get_text(" ", strip=True)
            for match in re.finditer(r"星期([一二三四五六日])\D*(\d+)\D*-\D*(\d+)\D*节", detail):
                day_name, start_value, end_value = match.groups()
                exact_times[(name, day_names[day_name])] = (int(start_value), int(end_value))
                data_rows.append(
                    {
                        "course_id": _clean(cells[1].get_text(), 80) if len(cells) > 1 else "",
                        "name": name_text,
                        "teacher": _clean(cells[4].get_text(), 120) or None if len(cells) > 4 else None,
                        "weeks": "",
                        "room": _clean(cells[7].get_text(), 120) or None if len(cells) > 7 else None,
                        "weekday": day_names[day_name],
                        "start_section": int(start_value),
                        "end_section": int(end_value),
                    }
                )

    table = soup.find("table", id="kbtable") or soup.find(
        lambda tag: tag.name == "table" and tag.find(class_="kbcontent") is not None
    )
    if table is None:
        return data_rows

    # The visual timetable carries the explicit week list that dataList omits.
    # Read it as a hint and merge by course/day/large section.
    hints: list[dict[str, Any]] = []
    large_sections = {
        "第一大节": (1, 3), "第二大节": (4, 5), "第三大节": (6, 7),
        "第四大节": (8, 10), "第五大节": (11, 13), "中午": (14, 14),
    }
    for row in table.find_all("tr")[1:]:
        header = _clean(row.find("th").get_text(), 80) if row.find("th") else ""
        section_range = next((value for label, value in large_sections.items() if label in header.replace(" ", "")), None)
        if section_range is None:
            continue
        for index, cell in enumerate(row.find_all("td", recursive=False)[:7], start=1):
            for div in cell.find_all("div", class_="kbcontent1"):
                text_value = div.get_text("\n", strip=True).replace("----------------------", "\n")
                pattern = re.compile(r"([^\r\n]+?)\s*([0-9]{1,2}(?:\s*-\s*[0-9]{1,2})?(?:\s*,\s*[0-9]{1,2}(?:\s*-\s*[0-9]{1,2})?)*)\s*\(周\)")
                for match in pattern.finditer(text_value):
                    hints.append(
                        {
                            "name": _clean(match.group(1), 120),
                            "weekday": index,
                            "start_section": section_range[0],
                            "end_section": section_range[1],
                            "weeks": f"{match.group(2)}(周)",
                        }
                    )

    if data_rows:
        for course in data_rows:
            large_start = next(
                (start for start, end in large_sections.values() if start <= course["start_section"] <= end),
                course["start_section"],
            )
            normalized_name = re.sub(r"\s+", "", course["name"]).casefold()
            match = next(
                (
                    hint
                    for hint in hints
                    if re.sub(r"\s+", "", hint["name"]).casefold() == normalized_name
                    and hint["weekday"] == course["weekday"]
                    and hint["start_section"] == large_start
                ),
                None,
            )
            if match:
                course["weeks"] = match["weeks"]
        return data_rows

    occupied: set[tuple[int, int]] = set()
    anchors: dict[tuple[int, int], Any] = {}
    for row_index, row in enumerate(table.find_all("tr")):
        column = 0
        for cell in row.find_all(["td", "th"], recursive=False):
            while (row_index, column) in occupied:
                column += 1
            rowspan = max(1, int(cell.get("rowspan", 1)))
            colspan = max(1, int(cell.get("colspan", 1)))
            anchors[(row_index, column)] = cell
            for row_delta in range(rowspan):
                for column_delta in range(colspan):
                    occupied.add((row_index + row_delta, column + column_delta))
            column += colspan

    monday_column = next(
        (column for (row, column), cell in anchors.items() if row == 0 and re.search(r"星期?一|周一", cell.get_text())),
        2,
    )
    slot_defaults = {1: (1, 3), 2: (4, 5), 3: (6, 7), 4: (8, 10), 5: (11, 13)}
    courses: list[dict[str, Any]] = []
    for (row, column), cell in anchors.items():
        day = column - monday_column + 1
        if row == 0 or day not in range(1, 8):
            continue
        default_sections = slot_defaults.get(row)
        if default_sections is None:
            continue
        for block in _course_blocks(cell):
            name = _clean(block.get("name"), 120)
            if not name:
                continue
            section_range = exact_times.get((re.sub(r"\s+", "", name), day))
            if section_range is None:
                section_match = re.search(r"(\d+)\D*-\D*(\d+)\D*节", block.get("weeks", ""))
                section_range = tuple(map(int, section_match.groups())) if section_match else default_sections
            courses.append(
                {
                    "name": name,
                    "course_id": "",
                    "teacher": _clean(block.get("teacher"), 120) or None,
                    "weeks": _clean(block.get("weeks"), 120),
                    "room": _clean(block.get("room"), 120) or None,
                    "weekday": day,
                    "start_section": section_range[0],
                    "end_section": section_range[1],
                }
            )
    return courses


def parse_njust_exams(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="dataList") or soup.find("table", class_="Nsb_r_list")
    if table is None:
        return []
    exams: list[dict[str, str]] = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 7:
            continue
        exams.append(
            {
                "session": _clean(cells[1].get_text(), 80),
                "course_id": _clean(cells[2].get_text(), 80),
                "course_name": _clean(cells[3].get_text(), 120),
                "time": _clean(cells[4].get_text(), 120),
                "room": _clean(cells[5].get_text(), 120),
                "seat": _clean(cells[6].get_text(), 50),
            }
        )
    return exams


def _week_ranges(raw: str, semester_weeks: int) -> list[tuple[int, int, str]]:
    week_part = raw.split("节", 1)[0]
    explicit_pattern = "odd" if "单" in week_part else ("even" if "双" in week_part else None)
    numbers: set[int] = set()
    for start_value, end_value in re.findall(r"(\d+)\s*-\s*(\d+)\s*周?", week_part):
        start, end = sorted((int(start_value), int(end_value)))
        numbers.update(range(max(1, start), min(semester_weeks, end) + 1))
    without_ranges = re.sub(r"\d+\s*-\s*\d+\s*周?", " ", week_part)
    numbers.update(int(value) for value in re.findall(r"\d+", without_ranges) if 1 <= int(value) <= semester_weeks)
    if not numbers:
        numbers.update(range(1, semester_weeks + 1))
    if explicit_pattern:
        parity = 1 if explicit_pattern == "odd" else 0
        numbers = {week for week in numbers if week % 2 == parity}
    ordered = sorted(numbers)
    if not ordered:
        return []
    ranges: list[tuple[int, int, str]] = []
    remaining = set(ordered)
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


def _item_key(key: str, kind: str, external_uid: str) -> str:
    return hashlib.sha256(f"{key}|{kind}|{external_uid}".encode()).hexdigest()[:24]


def normalize_njust_calendar(
    *,
    schedule_html: str,
    exams_html: str,
    term: str,
    semester_start: date,
    semester_weeks: int,
) -> tuple[str, str, list[dict[str, Any]], list[str]]:
    source_name = f"南京理工大学教务系统 · {term}"
    key = source_key("ical", source_name)
    warnings: list[str] = []
    items: list[dict[str, Any]] = []
    occurrences: dict[tuple[str, int], int] = {}

    for course in parse_njust_schedule(schedule_html):
        start_section = course["start_section"]
        end_section = course["end_section"]
        if start_section not in SECTION_TIMES or end_section not in SECTION_TIMES or end_section < start_section:
            warnings.append(f"{course['name']}：无法识别第 {start_section}–{end_section} 节的时间，未导入")
            continue
        occurrence_key = (course["name"].casefold(), course["weekday"])
        occurrence = occurrences.get(occurrence_key, 0) + 1
        occurrences[occurrence_key] = occurrence
        if not course["weeks"]:
            warnings.append(f"{course['name']}：教务页面未提供明确周次，已按整个学期导入，请在预览中核对")
        ranges = _week_ranges(course["weeks"], semester_weeks)
        if not ranges:
            warnings.append(f"{course['name']}：无法识别上课周次，未导入")
            continue
        for range_index, (start_week, end_week, pattern) in enumerate(ranges, start=1):
            identity = course.get("course_id") or course["name"]
            external_uid = f"njust:{term}:course:{hashlib.sha256(f'{identity}|{course['weekday']}|{occurrence}|{range_index}'.encode()).hexdigest()[:24]}"
            items.append(
                {
                    "item_key": _item_key(key, "class_session", external_uid),
                    "external_uid": external_uid,
                    "kind": "class_session",
                    "course_name": course["name"],
                    "teacher": course["teacher"],
                    "weekday": course["weekday"],
                    "start_time": SECTION_TIMES[start_section][0],
                    "end_time": SECTION_TIMES[end_section][1],
                    "start_week": start_week,
                    "end_week": end_week,
                    "week_pattern": pattern,
                    "location": course["room"],
                    "note": f"南理工教务导入 · {term}",
                }
            )

    exam_time_pattern = re.compile(
        r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})日?\s+(\d{1,2}):(\d{2})\s*[-~～至]\s*(\d{1,2}):(\d{2})"
    )
    for exam in parse_njust_exams(exams_html):
        match = exam_time_pattern.search(exam["time"])
        if not match:
            warnings.append(f"{exam['course_name'] or '未命名考试'}：考试时间未公布或无法识别，未导入")
            continue
        year, month, day, start_hour, start_minute, end_hour, end_minute = map(int, match.groups())
        try:
            starts_at = datetime(year, month, day, start_hour, start_minute, tzinfo=CHINA_ZONE)
            ends_at = datetime(year, month, day, end_hour, end_minute, tzinfo=CHINA_ZONE)
        except ValueError:
            warnings.append(f"{exam['course_name'] or '未命名考试'}：考试日期无效，未导入")
            continue
        if ends_at <= starts_at:
            warnings.append(f"{exam['course_name'] or '未命名考试'}：考试结束时间无效，未导入")
            continue
        identity = exam["course_id"] or exam["course_name"]
        external_uid = f"njust:{term}:exam:{hashlib.sha256(f'{identity}|{exam['session']}'.encode()).hexdigest()[:24]}"
        items.append(
            {
                "item_key": _item_key(key, "exam", external_uid),
                "external_uid": external_uid,
                "kind": "exam",
                "course_name": exam["course_name"] or "未命名课程",
                "title": f"{exam['course_name'] or '课程'} · {exam['session'] or '考试'}",
                "exam_type": "midterm" if "期中" in exam["session"] else ("final" if "期末" in exam["session"] else "other"),
                "starts_at": starts_at,
                "ends_at": ends_at,
                "location": exam["room"] or None,
                "seat_number": exam["seat"] or None,
                "note": f"南理工教务导入 · {term}",
            }
        )

    if not items:
        raise NjustAcademicError("NJUST_CALENDAR_EMPTY", "该学期没有可导入的课程或已公布考试")
    # Semester start is intentionally part of user confirmation but not source
    # identity: changing it affects display dates, not recurring week numbers.
    del semester_start
    return key, source_name, items, warnings[:20]
