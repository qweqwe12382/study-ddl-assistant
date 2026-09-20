from sqlalchemy import event
from sqlalchemy.exc import IntegrityError


def _db_from_client(client):
    from app.database import get_db

    generator = client.app.dependency_overrides[get_db]()
    return generator, next(generator)


def _prepared_material(client):
    material = client.post(
        "/api/materials",
        json={
            "original_filename": "M8.11 作业通知.txt",
            "extracted_text": "课程作业：提交实验报告，截止时间：2026年9月1日 20:00",
        },
    ).json()
    extracted = client.post(f"/api/materials/{material['id']}/extract")
    assert extracted.status_code == 200
    return material, extracted.json()["tasks"][0]


def _confirmation_events(db, material_id):
    from app.models.agent import AgentEvent

    return list(db.query(AgentEvent).filter(
        AgentEvent.event_type == "material_extraction_confirmed",
        AgentEvent.entity_type == "material",
        AgentEvent.entity_id == material_id,
    ).all())


def test_m811_confirmation_records_aggregate_event_and_safe_activity_projection(client):
    material, candidate = _prepared_material(client)

    confirmed = client.post(
        f"/api/materials/{material['id']}/extraction/confirm",
        json={"tasks": [candidate]},
    )

    assert confirmed.status_code == 200
    confirmed_body = confirmed.json()
    generator, db = _db_from_client(client)
    try:
        from app.models.material import Material

        events = _confirmation_events(db, material["id"])
        assert len(events) == 1
        event_row = events[0]
        stored_material = db.get(Material, material["id"])
        assert stored_material is not None
        assert stored_material.navigation_key == material["navigation_key"]
        assert event_row.entity_navigation_key == stored_material.navigation_key
        assert event_row.payload == {
            "batch_id": confirmed_body["batch_id"],
            "confirmed_task_count": len(confirmed_body["confirmed_task_ids"]),
        }
        event_id = event_row.id
    finally:
        generator.close()

    activity = client.get("/api/agent/activity", params={"limit": 50})
    assert activity.status_code == 200
    item = next(row for row in activity.json()["items"] if row["activity_id"] == f"event:{event_id}")
    assert item["event"] == "material_extraction_confirmed"
    assert item["status"] == "recorded"
    assert item["title"] == "资料抽取已确认"
    assert item["description"] == "资料已整理，可在来源中查看本次确认结果。"
    assert item["source"] == {
        "status": "available",
        "source_ref": {
            "source_type": "material", "source_id": material["id"],
            "navigation_key": material["navigation_key"],
        },
        "message": "可使用站内证据导航查看关联来源。",
    }
    assert confirmed_body["batch_id"] not in str(item)

    repeated = client.post(
        f"/api/materials/{material['id']}/extraction/confirm",
        json={"tasks": [candidate]},
    )
    assert repeated.status_code == 409
    generator, db = _db_from_client(client)
    try:
        assert len(_confirmation_events(db, material["id"])) == 1
    finally:
        generator.close()


def test_m811_transaction_failure_rolls_back_event_before_a_retry(client):
    from fastapi import HTTPException

    from app.api.materials import confirm_extraction
    from app.schemas.extraction import ExtractionConfirm
    from app.models.agent import AgentEvent
    from app.models.material import Material
    from app.models.task import Task

    material, candidate = _prepared_material(client)
    generator, db = _db_from_client(client)
    listener = None
    try:
        def _reject_commit(_session):
            raise IntegrityError("forced confirmation rollback", {}, RuntimeError("forced"))

        listener = _reject_commit
        event.listen(db, "before_commit", listener)
        try:
            confirm_extraction(material["id"], ExtractionConfirm(tasks=[candidate]), db)
            raise AssertionError("forced transaction failure should raise")
        except HTTPException as error:
            assert error.status_code == 409
            assert error.detail["code"] == "EXTRACTION_ALREADY_CONFIRMED"
        finally:
            event.remove(db, "before_commit", listener)
            listener = None

        assert db.query(Task).filter(Task.material_id == material["id"]).count() == 0
        assert db.query(AgentEvent).filter(
            AgentEvent.event_type == "material_extraction_confirmed",
            AgentEvent.entity_id == material["id"],
        ).count() == 0
        rolled_back_material = db.get(Material, material["id"])
        assert rolled_back_material is not None
        assert rolled_back_material.extraction_status != "confirmed"
    finally:
        if listener is not None:
            event.remove(db, "before_commit", listener)
        generator.close()

    retried = client.post(
        f"/api/materials/{material['id']}/extraction/confirm",
        json={"tasks": [candidate]},
    )
    assert retried.status_code == 200
    generator, db = _db_from_client(client)
    try:
        assert len(_confirmation_events(db, material["id"])) == 1
    finally:
        generator.close()
