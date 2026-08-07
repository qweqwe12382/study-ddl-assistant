"""Replaceable providers for M4 structured extraction.

The local provider is deliberately deterministic so the demo and tests work
without credentials or network access.  An OpenAI-compatible provider can be
enabled entirely through environment variables when desired.
"""

from __future__ import annotations

import json
import re
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
)


class RuleBasedProvider:
    name = "local-rules"

    def extract(self, text: str, filename: str) -> dict[str, Any]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        course_name = None
        for line in lines:
            match = re.search(r"(?:课程(?:名称)?|course)\s*[：:]\s*(.+)", line, re.IGNORECASE)
            if match:
                course_name = match.group(1).strip(" 。")[:120]
                break

        tasks: list[dict[str, Any]] = []
        for index, line in enumerate(lines):
            lowered = line.lower()
            if not any(hint in line or hint in lowered for hint in _TASK_HINTS):
                continue
            name = re.sub(r"(?:截止|交作业|提交时间|due|submit(?: by)?)\s*[：:：]?\s*.+$", "", line, flags=re.IGNORECASE)
            name = name.strip(" -：:，,。;") or line[:200]
            task_type = self._task_type(line)
            confidence = 0.88 if _has_date_text(line) else 0.58
            tasks.append(
                {
                    "candidate_id": f"rule-{index + 1}",
                    "course_name": course_name,
                    "name": name[:200],
                    "task_type": task_type,
                    "description": line[:500],
                    "due_at": _find_date_text(line),
                    "priority": 4 if any(word in line for word in ("考试", "截止", "exam", "due")) else 3,
                    "source_quote": line[:1000],
                    "confidence": confidence,
                }
            )

        tags: list[str] = []
        for label, words in {
            "DDL": ("截止", "due", "submit"),
            "作业": ("作业", "assignment", "homework"),
            "实验": ("实验", "lab"),
            "考试": ("考试", "exam", "quiz"),
        }.items():
            if any(word in text.lower() for word in words):
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


def get_provider() -> LLMProvider:
    if settings.llm_api_key and settings.llm_model:
        return OpenAICompatibleProvider()
    return RuleBasedProvider()
