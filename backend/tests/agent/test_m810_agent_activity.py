from datetime import timedelta

from sqlalchemy import event

from app.time import utc_now


def _db_from_client(client):
    from app.database import get_db

    generator = client.app.dependency_overrides[get_db]()
    return generator, next(generator)


def _counts(db):
    from app.models.agent import ActionReceipt, AgentEvent, AgentRun, AgentSuggestion

    return {
        "events": db.query(AgentEvent).count(), "suggestions": db.query(AgentSuggestion).count(),
        "receipts": db.query(ActionReceipt).count(), "runs": db.query(AgentRun).count(),
    }


def test_m810_activity_orders_bounds_and_exposes_no_payloads(client):
    from app.models.agent import AgentEvent, AgentRun, AgentSuggestion

    generator, db = _db_from_client(client)
    try:
        now = utc_now()
        for index in range(55):
            db.add(AgentEvent(
                event_type="suggestion_created", entity_type="task", entity_id=index + 1,
                payload={"path": "C:/secret", "trace": "internal", "number": index},
                created_at=now - timedelta(minutes=index),
            ))
        run = AgentRun(trigger="manual_refresh", status="completed", input_snapshot={"secret": "nope"},
                       created_at=now - timedelta(hours=2), completed_at=now - timedelta(hours=2))
        suggestion = AgentSuggestion(
            action_type="adjust_priority", status="executed", source_type="task", source_id=1,
            source_name="不应作为标题", title="泄露标题", explanation="泄露说明", reason_code="test",
            current_payload={"path": "C:/secret"}, proposed_payload={"free": "payload"}, risk_level="low",
            confidence=0.9, expires_at=now, fingerprint="m810-order", created_at=now - timedelta(hours=3),
            updated_at=now - timedelta(hours=3), executed_at=now - timedelta(hours=3), run=run,
        )
        db.add_all([run, suggestion]); db.commit()
    finally:
        generator.close()

    response = client.get("/api/agent/activity")
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 50 and len(body["items"]) == 50
    assert body["items"][0]["activity_id"] == "event:1"
    assert [item["occurred_at"] for item in body["items"]] == sorted(
        (item["occurred_at"] for item in body["items"]), reverse=True
    )
    serialized = str(body)
    assert "C:/secret" not in serialized and "'trace'" not in serialized
    assert "泄露标题" not in serialized and "泄露说明" not in serialized
    assert {"activity_id", "kind", "event", "status", "occurred_at", "title", "description", "source"} <= set(body["items"][0])


def test_m810_activity_is_read_only_and_unknown_records_degrade_safely(client):
    from app.models.agent import AgentEvent, AgentReminder, WeeklyReviewSnapshot

    generator, db = _db_from_client(client)
    try:
        event = AgentEvent(event_type="future_internal_event", entity_type="external_url", entity_id=9,
                           payload={"stack": "do not return", "url": "https://private.invalid"})
        db.add(event); db.commit()
        before = {
            **_counts(db), "reminders": db.query(AgentReminder).count(),
            "snapshots": db.query(WeeklyReviewSnapshot).count(),
        }
        event_id = event.id
    finally:
        generator.close()

    response = client.get("/api/agent/activity")
    assert response.status_code == 200
    item = next(row for row in response.json()["items"] if row["activity_id"] == f"event:{event_id}")
    assert item["event"] == "unavailable" and item["status"] == "unavailable"
    assert item["source"] == {
        "status": "unavailable", "source_ref": None,
        "message": "该历史记录没有可安全跳转的站内来源。",
    }
    assert "private.invalid" not in str(response.json()) and "do not return" not in str(response.json())

    generator, db = _db_from_client(client)
    try:
        assert before == {
            **_counts(db), "reminders": db.query(AgentReminder).count(),
            "snapshots": db.query(WeeklyReviewSnapshot).count(),
        }
    finally:
        generator.close()


def test_m810_activity_links_receipt_and_distinguishes_lifecycle(client):
    from app.models.agent import ActionReceipt, AgentEvent, AgentSuggestion
    from app.models.task import Task

    generator, db = _db_from_client(client)
    try:
        now = utc_now()
        task = Task(name="活动关联任务")
        db.add(task); db.flush()
        suggestion = AgentSuggestion(
            action_type="start_task", status="executed", source_type="task", source_id=task.id,
            source_navigation_key=task.navigation_key,
            source_name=task.name, title="原始标题", explanation="原始说明", reason_code="test", current_payload={},
            proposed_payload={}, risk_level="low", confidence=0.9, expires_at=now, fingerprint="m810-receipt",
            created_at=now - timedelta(minutes=3), updated_at=now - timedelta(minutes=1),
            accepted_at=now - timedelta(minutes=2), executed_at=now - timedelta(minutes=1),
        )
        db.add(suggestion); db.flush()
        receipt = ActionReceipt(
            suggestion_id=suggestion.id, action_type="start_task", source_type="task", source_id=task.id,
            source_navigation_key=task.navigation_key,
            outcome="executed", applied_payload={"secret": "hidden"}, before_payload={}, after_payload={},
            message="原始回执消息", executed_at=now,
        )
        db.add(receipt); db.flush()
        db.add_all([
            AgentEvent(event_type="suggestion_created", suggestion_id=suggestion.id, entity_type="task", entity_id=task.id,
                       payload={"raw": "hidden"}, created_at=now - timedelta(minutes=3)),
            AgentEvent(event_type="suggestion_accepted", suggestion_id=suggestion.id, entity_type="task", entity_id=task.id,
                       payload={"raw": "hidden"}, created_at=now - timedelta(minutes=2)),
            AgentEvent(event_type="suggestion_executed", suggestion_id=suggestion.id, entity_type="task", entity_id=task.id,
                       payload={"raw": "hidden"}, created_at=now - timedelta(minutes=1)),
        ])
        db.commit()
        suggestion_id, receipt_id, receipt_navigation_key = suggestion.id, receipt.id, receipt.navigation_key
    finally:
        generator.close()

    response = client.get("/api/agent/activity", params={"limit": 50})
    assert response.status_code == 200
    items = response.json()["items"]
    lifecycle = {row["event"] for row in items if row["suggestion_id"] == suggestion_id}
    assert {"suggestion_generated", "suggestion_confirmed", "suggestion_executed", "execution_receipt"} <= lifecycle
    linked = next(row for row in items if row["activity_id"] == f"receipt:{receipt_id}")
    assert linked["source"] == {
        "status": "available",
        "source_ref": {
            "source_type": "action_receipt", "source_id": receipt_id,
            "navigation_key": receipt_navigation_key,
        },
        "message": "可使用站内证据导航查看关联来源。",
    }
    assert linked["receipt_id"] == receipt_id


def test_m810_activity_rejects_malformed_limit(client):
    assert client.get("/api/agent/activity", params={"limit": 0}).status_code == 422
    assert client.get("/api/agent/activity", params={"limit": 51}).status_code == 422
    assert client.get("/api/agent/activity", params={"limit": "bad"}).status_code == 422


def test_m810_activity_reads_only_public_projection_columns(client):
    """The feed must not select detailed audit JSON merely to omit it later."""

    from app.models.agent import ActionReceipt, AgentEvent, AgentRun, AgentSuggestion
    from app.services.activity import build_activity

    generator, db = _db_from_client(client)
    statements: list[str] = []
    listener = None
    try:
        now = utc_now()
        run = AgentRun(
            trigger="manual_refresh", status="completed", input_snapshot={"secret": "run input"},
            created_at=now - timedelta(minutes=4), completed_at=now - timedelta(minutes=4),
        )
        suggestion = AgentSuggestion(
            action_type="start_task", status="executed", source_type="task", source_id=1,
            source_name="private source name", title="private suggestion title",
            explanation="private suggestion explanation", reason_code="test",
            current_payload={"secret": "current"}, proposed_payload={"secret": "proposed"},
            risk_level="low", confidence=0.9, expires_at=now, fingerprint="m810-minimal-read",
            run=run, created_at=now - timedelta(minutes=3), updated_at=now - timedelta(minutes=2),
            executed_at=now - timedelta(minutes=2),
        )
        db.add_all([run, suggestion])
        db.flush()
        receipt = ActionReceipt(
            suggestion_id=suggestion.id, action_type="start_task", source_type="task", source_id=1,
            outcome="executed", applied_payload={"secret": "applied"},
            before_payload={"secret": "before"}, after_payload={"secret": "after"},
            message="private receipt message", executed_at=now - timedelta(minutes=1),
        )
        db.add_all([
            receipt,
            AgentEvent(
                event_type="suggestion_executed", entity_type="task", entity_id=1,
                run_id=run.id, suggestion_id=suggestion.id, payload={"secret": "event"},
                created_at=now,
            ),
        ])
        db.commit()
        # A fresh identity map makes the observed SQL decisive: otherwise the
        # just-created ORM objects would already carry their full JSON values.
        db.expunge_all()

        def _capture(_conn, _cursor, statement, _parameters, _context, _executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement.lower())

        listener = _capture
        event.listen(db.get_bind(), "before_cursor_execute", listener)
        activity = build_activity(db)
    finally:
        if listener is not None:
            event.remove(db.get_bind(), "before_cursor_execute", listener)
        generator.close()

    assert {item["kind"] for item in activity["items"]} == {"event", "suggestion", "receipt", "run"}
    by_table = {
        "agent_events": {"payload"},
        "agent_suggestions": {
            "source_name", "title", "explanation", "current_payload", "proposed_payload",
            "risk_level", "confidence", "expires_at", "fingerprint", "idempotency_key", "dismissal_reason",
        },
        "action_receipts": {"source_type", "source_id", "applied_payload", "before_payload", "after_payload", "message"},
        "agent_runs": {"trigger", "generated_count", "expired_count", "ruleset_version", "input_snapshot"},
    }
    selected_by_table = {
        table: [statement for statement in statements if f"from {table}" in statement]
        for table in by_table
    }
    assert len(selected_by_table["agent_events"]) == 1
    assert len(selected_by_table["agent_suggestions"]) == 1
    assert len(selected_by_table["action_receipts"]) == 2  # newest slice plus linked-receipt lookup
    assert len(selected_by_table["agent_runs"]) == 1
    for table, forbidden_columns in by_table.items():
        selected = "\n".join(selected_by_table[table])
        for column in forbidden_columns:
            assert f"{table}.{column}" not in selected
