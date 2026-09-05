from datetime import datetime, timedelta, timezone


def _db_from_client(client):
    from app.database import get_db

    generator = client.app.dependency_overrides[get_db]()
    return generator, next(generator)


def _resolve(client, source_refs):
    response = client.post("/api/agent/source-navigation/resolve", json={"source_refs": source_refs})
    assert response.status_code == 200
    return response.json()["items"]


def _assert_unavailable(item):
    assert item["available"] is False
    assert item["target"] is None


def test_m87_resolves_task_material_plan_and_current_plan_item_to_fixed_routes(client):
    from app.models.material import Material
    from app.models.study_plan import StudyPlan
    from app.models.task import Task
    from app.schemas.study_plan import StudyPlanItem
    from app.services.source_identity import new_navigation_key
    from app.services.study_plan import encode_plan_content

    generator, db = _db_from_client(client)
    try:
        task = Task(name="任务来源")
        material = Material(original_filename="讲义.pdf")
        item = StudyPlanItem(
            id="第 1 节:重点", navigation_key=new_navigation_key(), date=datetime(2026, 8, 22).date(), phase="复习", title="第一节",
            content="复盘课堂内容", minutes=30,
        )
        plan = StudyPlan(title="期末复习计划", status="active", plan_content=encode_plan_content([item], [], material_count=0, task_count=0))
        db.add_all([task, material, plan])
        db.commit()
        refs = [
            {"source_type": "task", "source_id": task.id, "navigation_key": task.navigation_key},
            {"source_type": "material", "source_id": material.id, "navigation_key": material.navigation_key},
            {"source_type": "study_plan", "source_id": plan.id, "navigation_key": plan.navigation_key},
            {"source_type": "study_plan_item", "source_id": f"{plan.id}:{item.id}", "navigation_key": item.navigation_key},
        ]
    finally:
        generator.close()

    items = _resolve(client, refs)
    assert [item["available"] for item in items] == [True, True, True, True]
    assert items[0]["target"] == {
        "path": "/tasks", "query": {"task_id": str(task.id), "navigation_key": task.navigation_key}
    }
    assert items[1]["target"] == {
        "path": "/materials", "query": {"material_id": str(material.id), "navigation_key": material.navigation_key}
    }
    assert items[2]["target"] == {
        "path": "/study-plans", "query": {"plan_id": str(plan.id), "navigation_key": plan.navigation_key}
    }
    assert items[3]["target"] == {
        "path": "/study-plans",
        "query": {"plan_id": str(plan.id), "item_id": "第 1 节:重点", "navigation_key": item.navigation_key},
    }
    assert all("http" not in item["target"]["path"] for item in items)


def test_m87_resolves_only_named_collections_and_never_accepts_client_routes(client):
    refs = [
        {"source_type": "task_collection", "source_id": "weekly_overdue"},
        {"source_type": "material_collection", "source_id": "failed_materials"},
        {"source_type": "study_plan_collection", "source_id": "weekly_plan_delays"},
        {"source_type": "capacity", "source_id": "next_7_days"},
    ]
    items = _resolve(client, refs)
    assert [item["target"] for item in items] == [
        {"path": "/tasks", "query": {"view": "weekly_overdue"}},
        {"path": "/materials", "query": {"view": "failed_materials"}},
        {"path": "/study-plans", "query": {"view": "weekly_plan_delays"}},
        {"path": "/tasks", "query": {"view": "capacity_next_7_days"}},
    ]

    unknown = _resolve(client, [{"source_type": "task_collection", "source_id": "../../settings?admin=true"}])[0]
    assert unknown["available"] is False
    assert unknown["target"] is None

    # A source reference is an identity, not a client-controlled destination.
    forbidden_payload = client.post("/api/agent/source-navigation/resolve", json={
        "source_refs": [{"source_type": "task", "source_id": 1, "path": "https://example.invalid"}],
    })
    assert forbidden_payload.status_code == 422
    forbidden_type = client.post("/api/agent/source-navigation/resolve", json={
        "source_refs": [{"source_type": "external_url", "source_id": "https://example.invalid"}],
    })
    assert forbidden_type.status_code == 422


def test_m87_rejects_control_character_ids_and_bounds_live_labels_without_writes(client):
    from app.models.agent import AgentEvent, WeeklyReviewSnapshot
    from app.models.material import Material

    generator, db = _db_from_client(client)
    try:
        material = Material(original_filename="超长文件名" * 40 + ".pdf")
        db.add(material)
        db.commit()
        material_id = material.id
        material_navigation_key = material.navigation_key
        before = {
            "events": db.query(AgentEvent).count(),
            "snapshots": db.query(WeeklyReviewSnapshot).count(),
            "materials": db.query(Material).count(),
        }
    finally:
        generator.close()

    response = client.post("/api/agent/source-navigation/resolve", json={
        "source_refs": [{"source_type": "task", "source_id": "1\n2"}],
    })
    assert response.status_code == 422

    item = _resolve(client, [{
        "source_type": "material", "source_id": material_id, "navigation_key": material_navigation_key,
    }])[0]
    assert item["available"] is True
    assert len(item["label"]) == 200
    assert item["target"] == {
        "path": "/materials",
        "query": {"material_id": str(material_id), "navigation_key": material_navigation_key},
    }

    generator, db = _db_from_client(client)
    try:
        assert before == {
            "events": db.query(AgentEvent).count(),
            "snapshots": db.query(WeeklyReviewSnapshot).count(),
            "materials": db.query(Material).count(),
        }
    finally:
        generator.close()


def test_m87_historic_evidence_survives_deleted_source_but_navigation_is_unavailable(client):
    from app.models.agent import AgentEvent
    from app.models.task import Task
    from app.services.weekly_review import build_weekly_review
    from app.services.weekly_review_history import materialize_weekly_review, snapshot_read

    generator, db = _db_from_client(client)
    try:
        now = datetime(2026, 8, 22, 4, tzinfo=timezone.utc)
        task = Task(name="将被删除的历史任务", status="completed", completed_at=now - timedelta(minutes=5))
        db.add(task)
        db.commit()
        task_id = task.id
        snapshot = materialize_weekly_review(db, build_weekly_review(db, evaluated_at=now), evaluated_at=now)
        historic = snapshot_read(snapshot)
        historic_updated_at = snapshot.updated_at
        historic_ref = historic["review"]["completed_tasks"]["source_refs"][0]
        historic_name = historic_ref["source_name"]
        historic_navigation_key = historic_ref["navigation_key"]
        task.name = "当前已改名的任务"
        db.commit()
    finally:
        generator.close()

    assert historic["review"]["completed_tasks"]["source_refs"][0]["source_id"] == task_id
    renamed = _resolve(client, [{
        "source_type": "task", "source_id": task_id, "navigation_key": historic_navigation_key,
    }])[0]
    assert renamed["available"] is True
    assert renamed["label"] == "当前已改名的任务"
    assert renamed["target"] == {
        "path": "/tasks", "query": {"task_id": str(task_id), "navigation_key": historic_navigation_key}
    }
    # A legacy numeric-only reference must never be backfilled from a current
    # row with the same ID; historical evidence without its key is unavailable.
    _assert_unavailable(_resolve(client, [{"source_type": "task", "source_id": task_id}])[0])

    generator, db = _db_from_client(client)
    try:
        # Resolution is read-only: later live changes never rewrite the
        # retained snapshot evidence or generate a new agent event.
        stored = db.get(type(snapshot), snapshot.id)
        assert snapshot_read(stored)["review"]["completed_tasks"]["source_refs"][0]["source_name"] == historic_name
        # SQLite returns stored timestamps without a tzinfo, whereas the
        # in-memory object retains UTC.  Compare the persisted instant's
        # wall-clock value to prove the resolver did not write the snapshot.
        assert stored.updated_at.replace(tzinfo=None) == historic_updated_at.replace(tzinfo=None)
        assert db.query(AgentEvent).count() == 0
        db.delete(db.get(Task, task_id))
        db.commit()
    finally:
        generator.close()

    result = _resolve(client, [{
        "source_type": "task", "source_id": task_id, "navigation_key": historic_navigation_key,
    }])[0]
    assert result == {
        "source_ref": {
            "source_type": "task", "source_id": str(task_id), "navigation_key": historic_navigation_key,
        },
        "available": False,
        "target": None,
        "label": None,
        "message": "该历史任务已不存在或身份已变化，保留证据但不提供跳转",
    }
    history = client.get("/api/agent/weekly-reviews")
    assert history.status_code == 200
    assert history.json()["items"][0]["review"]["completed_tasks"]["source_refs"][0]["source_id"] == task_id
    assert history.json()["items"][0]["review"]["completed_tasks"]["source_refs"][0]["source_name"] == historic_name
    assert history.json()["items"][0]["review"]["completed_tasks"]["source_refs"][0]["navigation_key"] == historic_navigation_key


def test_m87_resolves_action_receipt_through_its_server_source_and_marks_missing_unavailable(client):
    from app.models.agent import ActionReceipt, AgentSuggestion
    from app.models.task import Task

    generator, db = _db_from_client(client)
    try:
        now = datetime(2026, 8, 22, 4, tzinfo=timezone.utc)
        task = Task(name="回执关联任务")
        db.add(task)
        db.flush()
        suggestion = AgentSuggestion(
            action_type="start_task", status="executed", source_type="task", source_id=task.id,
            source_navigation_key=task.navigation_key,
            source_name=task.name, title="开始", explanation="测试", reason_code="test", current_payload={},
            proposed_payload={}, risk_level="low", confidence=0.9, expires_at=now + timedelta(days=1),
            fingerprint="m87-receipt", created_at=now, updated_at=now,
        )
        db.add(suggestion)
        db.flush()
        receipt = ActionReceipt(
            suggestion_id=suggestion.id, action_type="start_task", source_type="task", source_id=task.id,
            source_navigation_key=task.navigation_key,
            outcome="executed", applied_payload={}, before_payload={}, after_payload={}, message="已开始", executed_at=now,
        )
        db.add(receipt)
        db.commit()
        receipt_id, receipt_navigation_key, task_id = receipt.id, receipt.navigation_key, task.id
    finally:
        generator.close()

    available = _resolve(client, [{
        "source_type": "action_receipt", "source_id": receipt_id, "navigation_key": receipt_navigation_key,
    }])[0]
    assert available["available"] is True
    assert available["target"] == {
        "path": "/tasks", "query": {"task_id": str(task_id), "navigation_key": task.navigation_key}
    }

    generator, db = _db_from_client(client)
    try:
        db.delete(db.get(Task, task_id))
        db.commit()
    finally:
        generator.close()

    # The receipt itself remains the historic audit source, but it cannot turn
    # into a stale task link after its current task has been removed.
    result = _resolve(client, [{
        "source_type": "action_receipt", "source_id": receipt_id, "navigation_key": receipt_navigation_key,
    }])[0]
    assert result["source_ref"] == {
        "source_type": "action_receipt", "source_id": str(receipt_id), "navigation_key": receipt_navigation_key,
    }
    assert result["available"] is False
    assert result["target"] is None
    assert str(task_id) not in result["message"]


def test_m87_resolves_actual_weekly_action_and_reminder_refs_without_permitting_invalid_ids(client):
    from app.models.task import Task
    from app.services.weekly_review import build_weekly_review, sync_weekly_reminders

    generator, db = _db_from_client(client)
    try:
        now = datetime(2026, 8, 22, 4, tzinfo=timezone.utc)
        overdue = Task(name="真实逾期来源", due_at=now - timedelta(hours=2), status="not_started")
        db.add(overdue)
        db.commit()
        review = build_weekly_review(db, evaluated_at=now)
        reminders = sync_weekly_reminders(db, review, evaluated_at=now)
        action = next(row for row in review["next_week_actions"] if row["action_type"] == "review_overdue_tasks")
        reminder = next(row for row in reminders if row.reason_code == "weekly_overdue_tasks")
        action_ref = action["source_refs"][0]
        reminder_ref = reminder.source_refs[0]
    finally:
        generator.close()

    resolved = _resolve(client, [
        {
            "source_type": action_ref["source_type"], "source_id": action_ref["source_id"],
            "navigation_key": action_ref["navigation_key"],
        },
        {
            "source_type": reminder_ref["source_type"], "source_id": reminder_ref["source_id"],
            "navigation_key": reminder_ref["navigation_key"],
        },
    ])
    assert all(item["available"] for item in resolved)
    assert all(item["target"]["path"] == "/tasks" for item in resolved)
    assert all(item["target"]["query"]["navigation_key"] == overdue.navigation_key for item in resolved)

    invalid_id = _resolve(client, [{"source_type": "task", "source_id": "not-an-id"}])[0]
    assert invalid_id["available"] is False
    assert invalid_id["target"] is None
