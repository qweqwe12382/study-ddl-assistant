"""Subprocess-only real application probe; environment paths supplied by test."""
import json
from pathlib import Path
import sys
from datetime import timedelta

from fastapi.testclient import TestClient
from app.main import app
from app.time import as_local, utc_now


mode, evidence_file = sys.argv[1:]
expected = {} if mode == "seed" else json.loads(Path(evidence_file).read_text())
with TestClient(app) as client:
    assert not app.dependency_overrides
    if mode != "seed":
        client.cookies.set("study_session", expected["_old_session"])
        assert client.get("/api/courses").status_code == 401
    for index in range(2):
        client.cookies.clear()
        account = {"email": f"backup-{index}@example.test", "password": "SyntheticBackup2026"}
        if mode == "seed":
            response = client.post("/api/auth/register", json={**account, "display_name": f"合成学生{index}"})
            assert response.status_code == 201, response.text
        else:
            response = client.post("/api/auth/login", json=account)
            assert response.status_code == 200, response.text
        headers = {"X-CSRF-Token": client.cookies.get("study_csrf")}
        if mode == "seed" and index == 0:
            expected["_old_session"] = client.cookies.get("study_session")
        content = f"合成学生{index}的通知正文".encode()
        if mode == "seed":
            course_response = client.post("/api/courses", json={"name": f"备份课程{index}"}, headers=headers)
            assert course_response.status_code == 201
            course = course_response.json()
            uploaded = client.post("/api/materials/upload", files={"files": (f"notice-{index}.txt", content, "text/plain")}, data={"course_id": course["id"]}, headers=headers)
            assert uploaded.status_code == 201, uploaded.text
            material = uploaded.json()[0]
            created = client.post("/api/tasks", json={"name": f"备份任务{index}", "material_id": material["id"], "course_id": course["id"]}, headers=headers)
            assert created.status_code == 201, created.text
            task = created.json()
            plan_response = client.post("/api/study-plans/generate", json={"course_id": course["id"], "exam_date": (as_local(utc_now()).date() + timedelta(days=1)).isoformat(), "daily_minutes": 60}, headers=headers)
            assert plan_response.status_code == 201, plan_response.text
            expected[str(index)] = {"material": material["navigation_key"], "task": task["navigation_key"], "plan": plan_response.json()["navigation_key"]}
        materials = client.get("/api/materials").json()
        tasks = client.get("/api/tasks").json()
        assert len(materials) == len(tasks) == 1
        material, task = materials[0], tasks[0]
        assert material["navigation_key"] == expected[str(index)]["material"]
        assert task["navigation_key"] == expected[str(index)]["task"]
        assert task["material_id"] == material["id"]
        plans = client.get("/api/study-plans").json()
        assert len(plans) == 1 and plans[0]["navigation_key"] == expected[str(index)]["plan"]
        assert len(client.get("/api/courses").json()) == 1
        downloaded = client.get(f"/api/materials/{material['id']}/file")
        assert downloaded.status_code == 200 and downloaded.content == content
    if mode != "seed":
        assert client.post("/api/tasks", json={"name": "仅写入恢复目录"}, headers=headers).status_code == 201
if mode == "seed":
    Path(evidence_file).write_text(json.dumps(expected), encoding="utf-8")
print("Real application account, upload and source identity checks passed")
