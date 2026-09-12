"""Notification dates keep their explicit reference time across later reads."""

from datetime import datetime, timezone

import pytest


NOTICE = "课程：数据结构\n实验报告，截止明天18:00"


def _utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _upload(client, source_time=None):
    data = {"material_type": "课程通知"}
    if source_time is not None:
        data["source_time"] = source_time
    return client.post(
        "/api/materials/upload",
        data=data,
        files={"files": ("课程通知.txt", NOTICE.encode("utf-8"), "text/plain")},
    )


@pytest.mark.parametrize("reference", ["2026-09-09T09:00:00", "2026-09-09T01:00:00Z", "2026-09-09T03:00:00+02:00"])
def test_notification_upload_uses_explicit_reference_and_waits_for_confirmation(client, isolated_upload_dir, reference):
    response = _upload(client, reference)
    assert response.status_code == 201, response.text
    material = response.json()[0]
    assert _utc(material["source_time"]) == datetime(2026, 9, 9, 1, tzinfo=timezone.utc)
    assert material["extraction_provider"] == "local-rules"
    candidates = material["extraction_result"]["tasks"]
    assert len(candidates) == 1
    assert _utc(candidates[0]["due_at"]) == datetime(2026, 9, 10, 10, tzinfo=timezone.utc)
    assert client.get("/api/tasks").json() == []
    assert client.get("/api/courses").json() == []


def test_omitted_reference_is_frozen_and_reextraction_does_not_move_deadline(client, isolated_upload_dir, monkeypatch):
    import app.api.materials as materials_api
    import app.services.extraction as extraction

    original = datetime(2026, 9, 9, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(materials_api, "utc_now", lambda: original)
    response = _upload(client)
    assert response.status_code == 201, response.text
    material = response.json()[0]
    assert _utc(material["source_time"]) == original
    first_deadline = material["extraction_result"]["tasks"][0]["due_at"]
    monkeypatch.setattr(extraction, "utc_now", lambda: datetime(2026, 10, 1, tzinfo=timezone.utc))
    headers = {"If-Match": f'"{material["navigation_key"]}:{material["revision"]}"'}
    rerun = client.post(f'/api/materials/{material["id"]}/extract', json={"provider": "local-rules"}, headers=headers)
    assert rerun.status_code == 200, rerun.text
    assert rerun.json()["tasks"][0]["due_at"] == first_deadline
    assert client.get("/api/tasks").json() == []


def test_duplicate_notice_does_not_replace_reference_or_write_a_second_file(client, isolated_upload_dir):
    original = _upload(client, "2026-09-09T09:00:00").json()[0]
    duplicate = _upload(client, "2026-09-10T09:00:00")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_FILE"
    materials = client.get("/api/materials").json()
    assert len(materials) == 1
    assert materials[0]["source_time"] == original["source_time"]
    assert len(list(isolated_upload_dir.iterdir())) == 1


def test_invalid_reference_rejected_before_file_creation(client, isolated_upload_dir):
    response = _upload(client, "not-a-date")
    assert response.status_code == 422
    assert client.get("/api/materials").json() == []
    assert list(isolated_upload_dir.iterdir()) == []


def test_manual_notification_reference_uses_same_timezone_semantics(client):
    response = client.post("/api/materials", json={
        "original_filename": "课程通知.txt", "extracted_text": NOTICE,
        "source_time": "2026-09-09T09:00:00",
    })
    assert response.status_code == 201, response.text
    assert _utc(response.json()["source_time"]) == datetime(2026, 9, 9, 1, tzinfo=timezone.utc)


def test_confirmed_notification_retains_original_task_identity_after_deletion(client, isolated_upload_dir):
    material = _upload(client, "2026-09-09T09:00:00").json()[0]
    headers = {"If-Match": f'"{material["navigation_key"]}:{material["revision"]}"'}
    response = client.post(f'/api/materials/{material["id"]}/extraction/confirm', json={}, headers=headers)
    assert response.status_code == 200, response.text
    confirmed = response.json()
    task = client.get("/api/tasks").json()[0]
    expected_ref = {"id": task["id"], "navigation_key": task["navigation_key"], "name": task["name"]}
    assert confirmed["confirmed_task_refs"] == [expected_ref]
    assert client.delete(f'/api/tasks/{task["id"]}').status_code == 204
    replacement = client.post("/api/tasks", json={"name": "另一项新任务"}).json()
    assert replacement["navigation_key"] != task["navigation_key"]
    snapshot = client.get(f'/api/materials/{material["id"]}/extraction').json()
    assert snapshot["confirmed_task_refs"] == [expected_ref]
    source_ref = {"source_type": "task", "source_id": str(task["id"]), "navigation_key": task["navigation_key"]}
    resolved = client.post("/api/agent/source-navigation/resolve", json={"source_refs": [source_ref]})
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["items"][0]["available"] is False
