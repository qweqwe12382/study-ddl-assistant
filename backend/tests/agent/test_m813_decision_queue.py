"""M8.13 bounded, read-only briefing decision queue."""

from datetime import timedelta

from app.time import utc_now
from app.models.task import Task
from app.services.agent import task_fingerprint


def _db_from_client(client):
    from app.database import get_db

    generator = client.app.dependency_overrides[get_db]()
    return generator, next(generator)


def _create_task(client, *, name="任务", due_hours=48, estimated_minutes=None):
    body = {
        "name": name,
        "due_at": (utc_now() + timedelta(hours=due_hours)).isoformat(),
    }
    if estimated_minutes is not None:
        body.update({"estimated_minutes": estimated_minutes, "remaining_minutes": estimated_minutes})
    return client.post("/api/tasks", json=body).json()


def test_m813_queue_is_bounded_stable_and_failure_first(client):
    from app.models.material import Material

    generator, db = _db_from_client(client)
    try:
        db.add_all([
            Material(original_filename=f"失败-{index}.txt", processing_status="failed", extraction_status="failed")
            for index in range(7)
        ])
        db.commit()
    finally:
        generator.close()

    first = client.get("/api/agent/briefing")
    second = client.get("/api/agent/briefing")

    assert first.status_code == second.status_code == 200
    queue = first.json()["decision_queue"]
    assert [item["decision_id"] for item in queue] == [item["decision_id"] for item in second.json()["decision_queue"]]
    assert len(queue) == 5
    assert [item["decision_id"] for item in queue] == [f"material:{index}:failed" for index in range(1, 6)]
    assert all(item["priority"] == "critical" for item in queue)
    assert all(item["kind"] == "material_failed" for item in queue)


def test_m813_material_statuses_have_fixed_priority_and_safe_minimal_evidence(client):
    from app.models.material import Material

    generator, db = _db_from_client(client)
    try:
        db.add_all([
            Material(original_filename="不应泄漏的失败文件.txt", processing_status="failed", extraction_status="not_started"),
            Material(original_filename="不应泄漏的待复核文件.txt", processing_status="processed", extraction_status="needs_review"),
            Material(original_filename="不应泄漏的就绪文件.txt", processing_status="processed", extraction_status="ready"),
        ])
        db.commit()
    finally:
        generator.close()

    queue = client.get("/api/agent/briefing").json()["decision_queue"]
    by_kind = {item["kind"]: item for item in queue}

    assert [item["kind"] for item in queue[:3]] == [
        "material_failed", "material_needs_review", "material_ready",
    ]
    assert [by_kind[kind]["priority"] for kind in ("material_failed", "material_needs_review", "material_ready")] == [
        "critical", "medium", "normal",
    ]
    assert by_kind["material_failed"]["reason_code"] == "material_processing_failed"
    for item in queue:
        source = item["source_refs"][0]
        material = client.get(f"/api/materials/{source['source_id']}").json()
        assert item["source_refs"] == [{"source_type": "material", "source_id": material["id"], "navigation_key": material["navigation_key"]}]
        assert set(source) == {"source_type", "source_id", "navigation_key"}
        assert "path" not in item and "payload" not in item
        assert all("不应泄漏" not in str(value) for value in item.values())

    resolved = client.post("/api/agent/source-navigation/resolve", json={
        "source_refs": [item["source_refs"][0] for item in queue],
    })
    assert resolved.status_code == 200
    assert all(item["available"] and item["target"]["path"] == "/materials" for item in resolved.json()["items"])


def test_m813_queue_hides_expired_suggestions_and_deduplicates_task_capacity_decisions(client):
    from app.models.agent import AgentSuggestion

    task = _create_task(client, name="同一任务不得重复", due_hours=48)
    generator, db = _db_from_client(client)
    try:
        now = utc_now()
        db.add_all([
            AgentSuggestion(
                action_type="adjust_priority", status="pending", source_type="task", source_id=task["id"], source_navigation_key=task["navigation_key"],
                source_name="不应进入响应", title="不应进入响应", explanation="不应进入响应",
                reason_code="internal", current_payload={"secret": "must-not-leak"}, proposed_payload={"priority": 5},
                risk_level="high", confidence=0.9, expires_at=now + timedelta(days=1),
                fingerprint=task_fingerprint(db.get(Task, task["id"])), created_at=now, updated_at=now,
            ),
            AgentSuggestion(
                action_type="adjust_priority", status="pending", source_type="task", source_id=task["id"], source_navigation_key=task["navigation_key"],
                source_name="过期", title="过期", explanation="过期", reason_code="internal",
                current_payload={}, proposed_payload={}, risk_level="high", confidence=0.9,
                expires_at=now - timedelta(minutes=1), fingerprint="m813-expired-priority", created_at=now, updated_at=now,
            ),
            AgentSuggestion(
                action_type="adjust_priority", status="pending", source_type="external_url", source_id=task["id"],
                source_name="外部来源", title="外部来源", explanation="外部来源", reason_code="internal",
                current_payload={"url": "https://example.invalid"}, proposed_payload={}, risk_level="high", confidence=0.9,
                expires_at=now + timedelta(days=1), fingerprint="m813-unsupported-source", created_at=now, updated_at=now,
            ),
        ])
        db.commit()
    finally:
        generator.close()

    queue = client.get("/api/agent/briefing").json()["decision_queue"]
    task_decisions = [item for item in queue if item["source_refs"] == [{"source_type": "task", "source_id": task["id"], "navigation_key": task["navigation_key"]}]]

    # The existing capacity projection also offers an estimate-review card for
    # this task.  The queue retains the higher-priority pending suggestion once.
    assert len(task_decisions) == 1
    assert task_decisions[0]["kind"] == "suggestion_priority_review"
    assert task_decisions[0]["decision_id"] == "priority_suggestion:1"
    assert "expired" not in " ".join(item["decision_id"] for item in queue)
    assert "external" not in str(queue)
    assert "example.invalid" not in str(queue)
    assert "must-not-leak" not in str(queue)
    assert "不应进入响应" not in str(queue)


def test_m813_queue_projects_only_current_plan_delta_as_navigation_review(client):
    from datetime import date

    course = client.post("/api/courses", json={"name": "计划差异课程"}).json()
    plan = client.post("/api/study-plans/generate", json={
        "course_id": course["id"], "exam_date": (date.today() + timedelta(days=5)).isoformat(), "daily_minutes": 60,
    }).json()
    task = client.post("/api/tasks", json={
        "course_id": course["id"], "name": "生成计划差异", "estimated_minutes": 45, "remaining_minutes": 45,
        "due_at": (utc_now() + timedelta(days=2)).isoformat(),
    }).json()
    delta = next(item for item in client.get("/api/agent/plan-deltas").json()
                 if item["current_payload"]["task_id"] == task["id"])

    queue = client.get("/api/agent/briefing").json()["decision_queue"]
    decision = next(item for item in queue if item["kind"] == "plan_delta_review")

    assert decision["decision_id"] == f"plan_delta:{delta['id']}"
    assert decision["source_refs"] == [{"source_type": "study_plan", "source_id": plan["id"], "navigation_key": plan["navigation_key"]}]
    assert decision["action_label"] == "查看计划差异"
    assert decision["description"] == "计划差异仅供人工复核，确认前不会改动复习计划。"
    assert str(delta["proposed_payload"]) not in str(decision)


def test_m813_builder_is_read_only_and_plan_delta_is_navigation_only(client):
    from app.api.agent import _capacity_action_candidates
    from app.models.agent import ActionReceipt, AgentEvent, AgentReminder, AgentSuggestion, WeeklyReviewSnapshot
    from app.services.decision_queue import build_decision_queue
    from app.services.study_preferences import build_capacity

    task = _create_task(client, name="只读决策队列", due_hours=48, estimated_minutes=30)
    generator, db = _db_from_client(client)
    try:
        now = utc_now()
        # A valid ordinary pending suggestion is enough to prove the builder
        # never exposes JSON payload or creates an execution record.  Plan
        # deltas themselves are revalidated by the briefing before this call.
        suggestion = AgentSuggestion(
            action_type="adjust_priority", status="pending", source_type="task", source_id=task["id"], source_navigation_key=task["navigation_key"],
            source_name="内部名称", title="内部标题", explanation="内部说明", reason_code="internal",
            current_payload={"internal": "hidden"}, proposed_payload={"priority": 5}, risk_level="high",
            confidence=0.9, expires_at=now + timedelta(days=1), fingerprint="m813-read-only", created_at=now, updated_at=now,
        )
        db.add(suggestion)
        db.commit()
        capacity = build_capacity(db, evaluated_at=now)
        before = {
            "suggestions": db.query(AgentSuggestion).count(),
            "events": db.query(AgentEvent).count(),
            "reminders": db.query(AgentReminder).count(),
            "receipts": db.query(ActionReceipt).count(),
            "snapshots": db.query(WeeklyReviewSnapshot).count(),
        }
        queue = build_decision_queue(
            db, pending=[suggestion], capacity_candidates=_capacity_action_candidates(capacity, [suggestion]), evaluated_at=now,
        )
        after = {
            "suggestions": db.query(AgentSuggestion).count(),
            "events": db.query(AgentEvent).count(),
            "reminders": db.query(AgentReminder).count(),
            "receipts": db.query(ActionReceipt).count(),
            "snapshots": db.query(WeeklyReviewSnapshot).count(),
        }
        assert before == after
        assert not db.new and not db.dirty and not db.deleted
    finally:
        generator.close()

    assert queue[0]["kind"] == "suggestion_priority_review"
    assert queue[0]["source_refs"] == [{"source_type": "task", "source_id": task["id"], "navigation_key": task["navigation_key"]}]
    assert queue[0]["calculation_basis"]["ordering_rule"] == "risk_then_kind_then_source"
    assert "hidden" not in str(queue)
