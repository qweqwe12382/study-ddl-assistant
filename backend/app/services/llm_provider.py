"""Replaceable providers for M4 structured extraction.

The local provider is deliberately deterministic so the demo and tests work
without credentials or network access.  An OpenAI-compatible provider can be
enabled entirely through environment variables when desired.
"""

from __future__ import annotations

import json
import re
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


class RuleBasedProvider:
    name = "local-rules"

    def extract(self, text: str, filename: str) -> dict[str, Any]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        filename_stem = _filename_stem(filename)
        filename_course = _course_name_from_filename(filename)
        filename_has_task_hint = _has_task_hint(filename_stem)

        course_name = None
        for line in lines:
            match = re.search(r"(?:课程(?:名称)?|course)\s*[：:]\s*(.+)", line, re.IGNORECASE)
            if match:
                course_name = match.group(1).strip(" 。")[:120]
                break
        course_name = course_name or filename_course

        tasks: list[dict[str, Any]] = []
        for index, line in enumerate(lines):
            line_has_task_hint = _has_task_hint(line)
            if not line_has_task_hint and not (filename_has_task_hint and _has_date_text(line)):
                continue

            if line_has_task_hint:
                name = re.sub(
                    r"(?:截止|交作业|提交时间|due|submit(?: by)?)\s*[：:：]?\s*.+$",
                    "",
                    line,
                    flags=re.IGNORECASE,
                )
                name = name.strip(" -：:，,。;") or line[:200]
            else:
                # The date is still evidenced by the body; the filename only
                # supplies the conservative task label/type.
                name = _filename_task_name(filename)

            task_type = self._task_type(line)
            filename_task_type = self._task_type(filename_stem)
            if task_type in {"其他", "DDL"} and filename_task_type != "其他":
                task_type = filename_task_type
            confidence = 0.88 if _has_date_text(line) else 0.58
            combined_line = f"{filename_stem}\n{line}".lower()
            tasks.append(
                {
                    "candidate_id": f"rule-{index + 1}",
                    "course_name": course_name,
                    "name": name[:200],
                    "task_type": task_type,
                    "description": line[:500],
                    "due_at": _find_date_text(line),
                    "priority": 4
                    if any(word in combined_line for word in ("考试", "截止", "exam", "due", "ddl"))
                    else 3,
                    "source_quote": line[:1000],
                    "confidence": confidence,
                }
            )

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
        return {
            "course_name": course_name,
            "material_type": "作业要求" if tasks else None,
            "tags": tags,
            "tasks": tasks,
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


def _has_date_text(value: str) -> bool:
    return bool(re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2}|今天|明天|后天|下周[一二三四五六日天]|\b(?:due|submit)\b", value, re.IGNORECASE))


def _find_date_text(value: str) -> str | None:
    patterns = (
        r"\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:\s+\d{1,2}[:：]\d{2})?",
        r"\d{4}年\d{1,2}月\d{1,2}日?(?:\s*\d{1,2}[点:：]\d{0,2}分?)?",
        r"\d{1,2}月\d{1,2}日?(?:\s*\d{1,2}[点:：]\d{0,2}分?)?",
        r"\d{1,2}/\d{1,2}(?:\s+\d{1,2}[:：]\d{2})?",
        r"今天|明天|后天|大后天|下周末|本周末|周末|下周[一二三四五六日天]|本周[一二三四五六日天]|(?:星期|周)[一二三四五六日天]",
        r"\b(?:today|tomorrow|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekend))\b",
        r"\b(?:due|submit)\s+(?:on\s+)?[A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?",
    )
    for pattern in patterns:
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


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
                            "你是学习资料DDL抽取器。只输出JSON，字段为 course_name、material_type、tags、tasks。"
                            "tasks中的每项包含name、task_type、description、due_at、priority、source_quote、confidence。"
                            "无法确认的字段使用null，并保留原文source_quote。"
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
