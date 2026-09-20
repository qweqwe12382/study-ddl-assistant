"""Separate learning content, reference schedules and actionable obligations.

These conservative local hints never turn a reference date into a task or an
exam date. Learning excerpts always come directly from the supplied document.
"""

import re

REVIEW_OUTLINE = re.compile(r"复习(?:计划|安排|日程|时间表)|学习(?:计划|安排|时间表)|study\s+(?:plan|schedule)", re.I)
LEARNING_ACTION = re.compile(r"复习|温习|背诵|梳理|阅读|自测|刷题|错题|巩固|知识点|练习题|review|revise", re.I)
OBLIGATION = re.compile(r"提交|上交|交齐|交作业|交报告|交实验|缴|报名|签到|参加|考试时间|测验时间|截止|(?:请|须|必须|需要|务必|完成)[^。；，\n]{0,10}(?:作业|实验报告|实验任务)|\bsubmit\b|\bdue\b", re.I)
LEARNING_TYPE = re.compile(r"复习资料|复习提纲|复习重点|知识点|知识梳理|错题|课件|讲义|教材|阅读材料|笔记|第.{1,8}章")


def is_learning_activity(text: str, filename: str = "") -> bool:
    """A dated revision activity is not an obligation; mixed notices still work."""
    if OBLIGATION.search(text):
        return False
    return bool(LEARNING_ACTION.search(text) or REVIEW_OUTLINE.search(text))


def describe_material(text: str, filename: str, tasks: list, material_type: str | None = None) -> dict:
    source = f"{filename}\n{text}"
    outline = bool(REVIEW_OUTLINE.search(source))
    quotes = [task.get("source_quote") if isinstance(task, dict) else task.source_quote for task in tasks]
    learning_text = text
    for quote in quotes:
        if quote:
            learning_text = learning_text.replace(quote, "")
    # "复习作业" in a task's own title does not establish learning content.
    learning = bool(LEARNING_TYPE.search(f"{filename}\n{learning_text}") or LEARNING_ACTION.search(learning_text))
    kind = "mixed" if tasks and (learning or outline) else "task_notice" if tasks else "review_outline" if outline else "study_material"
    inferred_type = ("复习安排" if outline else "作业要求" if tasks and not learning else "复习资料" if re.search(r"复习|错题|知识点", source)
                     else "课堂讲义" if re.search(r"课件|讲义|笔记", source)
                     else "作业要求" if tasks else "课程通知" if "通知" in source else None)
    points = []
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 4 or re.match(r"^课程\s*[：:]", line) or re.fullmatch(r"(?:复习|学习)(?:计划|安排|资料|提纲)(?:[（(].*?[）)])?", line):
            continue
        if any(quote and (line in quote or quote in line) for quote in quotes):
            continue
        if tasks and not (LEARNING_TYPE.search(line) or is_learning_activity(line)):
            continue
        # Do not label task-only requirements as knowledge points.
        if OBLIGATION.search(line):
            continue
        if line[:180] not in points:
            points.append(line[:180])
        if len(points) == 6:
            break
    return {"content_kind": kind, "learning_points": points, "material_type": material_type or inferred_type}


def material_source_option(material) -> dict:
    description = describe_material(material.extracted_text or material.summary or "", material.original_filename,
                                    (material.extraction_result or {}).get("tasks", []), material.material_type)
    usable = bool((material.extracted_text or material.summary or "").strip()) and material.processing_status not in {"failed", "processing"}
    reference = description["content_kind"] in {"task_notice", "review_outline"} or description["material_type"] in {"作业要求", "课程通知", "复习安排", "复习计划"} or (
        bool((material.extraction_result or {}).get("tasks")) and not description["learning_points"]
    )
    return {"source_id": material.id, "navigation_key": material.navigation_key, "revision": material.revision,
            "label": material.original_filename, **description, "available": usable,
            "recommended": usable and not reference,
            "hint": "请先补充正文或重新解析" if not usable else "参考安排，原日期不会导入新计划" if description["content_kind"] == "review_outline"
            else "通知与要求，可按需选入" if reference else "用于安排复习内容"}
