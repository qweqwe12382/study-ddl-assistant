"""Isolated regressions for provider deadlines, malformed output and mixed PDFs."""

from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO

import fitz
from PIL import Image
import pytest

from app.services import extraction, file_parser
from app.models.material import Material
from app.services.llm_provider import RuleBasedProvider


def test_report_content_requirements_do_not_create_extra_tasks(client):
    material = _material(client, '《数据结构》课程通知：请于2026年10月15日20:00前提交图遍历实验报告。报告需包含算法说明、实验结果和总结。')
    response = client.post(f"/api/materials/{material['id']}/extract")
    assert response.status_code == 200
    preview = response.json()
    assert len(preview['tasks']) == 1
    candidate = preview['tasks'][0]
    assert candidate['name'] == '提交图遍历实验报告'
    assert _instant(candidate['due_at']) == datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
    # The UI submits this explicit Shanghai wall clock after displaying UTC.
    candidate['due_at'] = '2026-10-15T20:00:00'
    confirmation = client.post(f"/api/materials/{material['id']}/extraction/confirm", json={'tasks': [candidate]})
    assert confirmation.status_code == 200
    task_id = confirmation.json()['confirmed_task_ids'][0]
    assert _instant(client.get(f'/api/tasks/{task_id}').json()['due_at']) == datetime(2026, 10, 15, 12, tzinfo=timezone.utc)


def test_report_requirements_with_separate_submission_keep_the_task():
    result = RuleBasedProvider().extract('报告需包含实验结果，请于2026年10月16日20:00前提交报告。', '课程通知.txt')
    assert len(result['tasks']) == 1


def _material(client, source="请提交作业。"):
    response = client.post("/api/materials", json={
        "original_filename": "课程通知.txt", "extracted_text": source,
        "source_time": "2026-09-10T01:00:00Z",
    })
    assert response.status_code == 201
    return response.json()


def _provider(monkeypatch, payload):
    class Provider:
        name = "openai-compatible"

        def extract(self, _text, _filename):
            return deepcopy(payload)

    monkeypatch.setattr(extraction, "get_provider", lambda *_: Provider())


def _payload(source="请提交作业。", deadline="2026-09-18T12:30:00Z"):
    return {"tags": [], "tasks": [{
        "name": "提交作业", "source_quote": source, "due_at": deadline, "confidence": 0.95,
    }]}


def _instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_iso_provider_deadline_keeps_utc_in_candidate_and_confirmed_task(client, monkeypatch):
    material = _material(client)
    _provider(monkeypatch, _payload())

    response = client.post(f"/api/materials/{material['id']}/extract")
    assert response.status_code == 200
    candidate = response.json()["tasks"][0]
    expected = datetime(2026, 9, 18, 12, 30, tzinfo=timezone.utc)
    assert _instant(candidate["due_at"]) == expected
    confirmation = client.post(f"/api/materials/{material['id']}/extraction/confirm", json={"tasks": [candidate]})
    assert confirmation.status_code == 200
    task_id = confirmation.json()["confirmed_task_ids"][0]
    assert _instant(client.get(f"/api/tasks/{task_id}").json()["due_at"]) == expected


def test_null_candidate_warnings_records_failure_instead_of_server_error(client, monkeypatch):
    material = _material(client)
    payload = _payload(source="模型捏造的来源")
    payload["tasks"][0]["warnings"] = None
    _provider(monkeypatch, payload)

    response = client.post(f"/api/materials/{material['id']}/extract")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_PROVIDER_JSON"
    saved = client.get(f"/api/materials/{material['id']}").json()
    assert saved["extraction_status"] == "failed"
    assert saved["extraction_error"]
    assert saved["extracted_at"]
    assert client.get("/api/tasks").json() == []


def _pdf(pages):
    image = BytesIO()
    Image.new("RGB", (40, 40), "black").save(image, format="PNG")
    with fitz.open() as document:
        for text in pages:
            page = document.new_page()
            if text is None:
                page.insert_image(fitz.Rect(20, 20, 100, 100), stream=image.getvalue())
            else:
                page.insert_text((30, 30), text)
        return document.tobytes()


def test_mixed_pdf_extracts_scanned_page_in_original_order(monkeypatch):
    calls = []
    monkeypatch.setattr(file_parser, "_extract_image_ocr", lambda image: calls.append(image) or "Scanned assignment")

    text = file_parser.extract_text("pdf", _pdf(["Text cover", None, "Text appendix"]))

    assert len(calls) == 1
    assert text.splitlines() == ["Text cover", "Scanned assignment", "Text appendix"]


def test_chinese_half_hour_is_not_silently_rounded_down(client):
    material = _material(client, "请于2026年9月18日下午3点半提交作业。")

    response = client.post(f"/api/materials/{material['id']}/extract")

    assert response.status_code == 200
    candidate = response.json()["tasks"][0]
    assert _instant(candidate["due_at"]) == datetime(2026, 9, 18, 7, 30, tzinfo=timezone.utc)
    assert "INVALID_TIME" not in candidate["warnings"]


@pytest.mark.parametrize("deadline,expected", [
    ("2026-09-18T20:30:00+08:00", "2026-09-18T12:30:00+00:00"),
    ("2026-09-18T20:30:00+08", "2026-09-18T12:30:00+00:00"),
    ("2026-09-18T08:30:00-04:00", "2026-09-18T12:30:00+00:00"),
    ("2026-09-18T20:30:00", "2026-09-18T12:30:00+00:00"),
    ("2026-09-18T12:30:45.123456Z", "2026-09-18T12:30:45.123456+00:00"),
    ("2026-09-18", "2026-09-18T15:59:00+00:00"),
    ("2026-09-18 3:30 PM", "2026-09-18T07:30:00+00:00"),
])
def test_provider_clock_formats_keep_their_instant(monkeypatch, deadline, expected):
    _provider(monkeypatch, _payload(deadline=deadline))
    material = Material(original_filename="通知.txt", extracted_text="请提交作业。", processing_status="processed",
                        source_time=datetime(2026, 9, 10, tzinfo=timezone.utc))

    result, _ = extraction.extract_material(material)

    assert result.tasks[0].due_at == _instant(expected)
    assert "DATE_CONFLICT_WITH_SOURCE" not in result.tasks[0].warnings
    if deadline == "2026-09-18":
        assert "TIME_DEFAULTED_TO_END_OF_DAY" in result.tasks[0].warnings


@pytest.mark.parametrize("source", [
    "请于2026年9月18日20:30提交作业。",
    "请于2026-09-18T12:30:00Z提交作业。",
    "请于2026-09-18T08:30:00-04:00提交作业。",
])
def test_source_and_provider_compare_equivalent_timezones(monkeypatch, source):
    _provider(monkeypatch, _payload(source=source))
    material = Material(original_filename="通知.txt", extracted_text=source, processing_status="processed",
                        source_time=datetime(2026, 9, 10, tzinfo=timezone.utc))

    result, _ = extraction.extract_material(material)

    assert result.tasks[0].due_at == datetime(2026, 9, 18, 12, 30, tzinfo=timezone.utc)
    assert not result.tasks[0].warnings


def test_iso_provider_still_rejects_actual_source_conflict(monkeypatch):
    source = "请于2026年9月18日21:30提交作业。"
    _provider(monkeypatch, _payload(source=source))
    material = Material(original_filename="通知.txt", extracted_text=source, processing_status="processed")

    result, _ = extraction.extract_material(material)

    assert result.tasks[0].due_at is None
    assert "DATE_CONFLICT_WITH_SOURCE" in result.tasks[0].warnings


@pytest.mark.parametrize("scope,field,value", [
    ("result", "warnings", None), ("result", "warnings", "not an array"),
    ("result", "warnings", [{}]), ("result", "tasks", {}), ("result", "tags", None),
    ("task", "warnings", {}), ("task", "warnings", "not an array"),
    ("task", "warnings", [None]), ("task", "name", {}), ("task", "source_quote", []),
    ("task", "due_at", {}), ("task", "confidence", {}), ("task", "priority", []),
])
def test_malformed_nested_output_is_recorded_and_can_be_retried(client, monkeypatch, scope, field, value):
    material = _material(client)
    payload = _payload()
    (payload if scope == "result" else payload["tasks"][0])[field] = value
    _provider(monkeypatch, payload)

    response = client.post(f"/api/materials/{material['id']}/extract")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_PROVIDER_JSON"
    saved = client.get(f"/api/materials/{material['id']}").json()
    assert saved["extraction_status"] == "failed"
    assert saved["extraction_provider"] == "openai-compatible"
    assert saved["extraction_error"]
    assert client.get("/api/tasks").json() == []

    _provider(monkeypatch, _payload())
    retried = client.post(f"/api/materials/{material['id']}/extract")
    assert retried.status_code == 200
    assert retried.json()["status"] == "ready"
    assert retried.json()["error"] is None


@pytest.mark.parametrize("clock,utc_hour,minute", [
    ("下午3点半", 7, 30), ("下午三点半", 7, 30), ("15时半", 7, 30),
    ("下午三点一刻", 7, 15), ("下午三点三刻", 7, 45), ("下午三点三十五分", 7, 35),
    ("下午3点一并", 7, 0), ("下午3:30", 7, 30),
])
def test_chinese_minutes_share_the_scanner_and_normalizer(clock, utc_hour, minute):
    text = f"请于2026年9月18日{clock}提交作业。"
    material = Material(original_filename="通知.txt", extracted_text=text, processing_status="processed",
                        source_time=datetime(2026, 9, 10, tzinfo=timezone.utc))
    raw = RuleBasedProvider().extract(text, material.original_filename)

    result = extraction._normalize_result(raw, material, provider_name="local-rules")

    assert result.tasks[0].due_at == datetime(2026, 9, 18, utc_hour, minute, tzinfo=timezone.utc)
    assert "INVALID_TIME" not in result.tasks[0].warnings


@pytest.mark.parametrize("clock", ["下午3点四刻", "下午3点半左右", "下午3点差一刻", "下午3点多"])
def test_unsupported_clock_expressions_require_review_without_guessing(clock):
    text = f"请于2026年9月18日{clock}提交作业。"
    material = Material(original_filename="通知.txt", extracted_text=text, processing_status="processed")
    raw = RuleBasedProvider().extract(text, material.original_filename)

    result = extraction._normalize_result(raw, material, provider_name="local-rules")

    assert result.tasks[0].due_at is None
    assert "INVALID_TIME" in result.tasks[0].warnings
    assert result.tasks[0].need_review is True


@pytest.mark.parametrize("code", ["OCR_UNAVAILABLE", "OCR_FAILED", "OCR_NO_TEXT"])
def test_incomplete_pdf_keeps_original_and_succeeds_after_retry(client, isolated_upload_dir, monkeypatch, code):
    def unavailable(_image):
        raise file_parser.FileProcessingError(code, "模拟识别失败")

    monkeypatch.setattr(file_parser, "_extract_image_ocr", unavailable)
    content = _pdf(["Text cover", None, "Text appendix"])

    uploaded = client.post("/api/materials/upload", files={"files": ("mixed.pdf", content, "application/pdf")})

    assert uploaded.status_code == 201
    material = uploaded.json()[0]
    assert material["processing_status"] == "failed"
    assert "第 2 页" in material["processing_error"]
    assert material["extracted_text"] is None
    assert material["extraction_status"] == "not_started"
    assert (isolated_upload_dir / material["stored_path"]).read_bytes() == content

    monkeypatch.setattr(file_parser, "_extract_image_ocr", lambda _: "Recovered scanned page")
    retried = client.post(f"/api/materials/{material['id']}/retry")
    assert retried.status_code == 200
    assert retried.json()["processing_status"] == "processed"
    assert retried.json()["processing_error"] is None
    assert retried.json()["extracted_text"].splitlines() == ["Text cover", "Recovered scanned page", "Text appendix"]


def test_ocr_limit_counts_only_pages_without_text(monkeypatch):
    calls = []
    monkeypatch.setattr(file_parser, "_extract_image_ocr", lambda image: calls.append(image) or "Scanned page")
    pages = [f"Text page {index}" for index in range(file_parser.MAX_PDF_OCR_PAGES + 1)] + [None]

    text = file_parser.extract_text("pdf", _pdf(pages))

    assert len(calls) == 1
    assert len(text.splitlines()) == len(pages)
    assert text.splitlines()[-1] == "Scanned page"


def test_too_many_scanned_pages_fails_before_any_ocr(monkeypatch):
    monkeypatch.setattr(file_parser, "_extract_image_ocr", lambda _: pytest.fail("OCR limit must be checked first"))

    with pytest.raises(file_parser.FileProcessingError) as error:
        file_parser.extract_text("pdf", _pdf(["Text cover"] + [None] * (file_parser.MAX_PDF_OCR_PAGES + 1)))

    assert error.value.code == "PDF_TOO_MANY_OCR_PAGES"


def test_empty_ocr_response_cannot_silently_drop_a_page(monkeypatch):
    monkeypatch.setattr(file_parser, "_extract_image_ocr", lambda _: "  ")

    with pytest.raises(file_parser.FileProcessingError) as error:
        file_parser.extract_text("pdf", _pdf(["Text cover", None]))

    assert error.value.code == "OCR_NO_TEXT"
    assert "第 2 页" in error.value.message
