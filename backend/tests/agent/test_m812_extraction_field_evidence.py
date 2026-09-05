"""M8.12 server-derived provenance for reviewed extraction fields."""


def _configure_external_provider(monkeypatch, result):
    from app.services import extraction

    class ExternalProvider:
        name = "openai-compatible"

        @staticmethod
        def extract(_text, _filename):
            return result

    monkeypatch.setattr(extraction, "get_provider", lambda _provider_name=None: ExternalProvider())


def _evidence_by_value(result):
    return {item["value"]: item for item in result["field_evidence"]["tags"]}


def test_m812_server_marks_filename_text_and_both_from_material_only(client, monkeypatch):
    _configure_external_provider(
        monkeypatch,
        {
            "course_name": "数据结构",
            "material_type": "讲义",
            "tags": ["重点", "实验"],
            "tasks": [],
        },
    )
    material = client.post(
        "/api/materials",
        json={
            "original_filename": "数据结构-讲义.txt",
            "extracted_text": "课程：数据结构\n重点：完成实验。",
        },
    ).json()

    response = client.post(
        f"/api/materials/{material['id']}/extract",
        json={"provider": "openai-compatible"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["field_evidence"]["course_name"]["source"] == "both"
    assert result["field_evidence"]["material_type"] == {
        "value": "讲义",
        "source": "filename",
        "snippets": ["数据结构-讲义.txt"],
    }
    tags = _evidence_by_value(result)
    assert tags["重点"]["source"] == "text"
    assert tags["实验"]["source"] == "text"
    assert all(len(snippet) <= 180 for item in tags.values() for snippet in item["snippets"])


def test_m812_local_rules_and_unmatched_external_values_degrade_honestly(client, monkeypatch):
    local_material = client.post(
        "/api/materials",
        json={
            "original_filename": "算法-作业通知.txt",
            "extracted_text": "2026年10月15日 23:59",
        },
    ).json()
    local = client.post(f"/api/materials/{local_material['id']}/extract", json={"provider": "local-rules"})

    assert local.status_code == 200
    assert local.json()["field_evidence"]["material_type"] == {
        "value": "作业要求",
        "source": "rule_inference",
        "snippets": [],
    }

    _configure_external_provider(
        monkeypatch,
        {
            "course_name": "不存在的课程",
            "material_type": "外部分类",
            "tags": ["虚构标签"],
            "tasks": [],
        },
    )
    external_material = client.post(
        "/api/materials",
        json={"original_filename": "普通通知.txt", "extracted_text": "本周学习安排。"},
    ).json()
    external = client.post(
        f"/api/materials/{external_material['id']}/extract",
        json={"provider": "openai-compatible"},
    )

    assert external.status_code == 200
    evidence = external.json()["field_evidence"]
    assert evidence["course_name"]["source"] == "unconfirmed"
    assert evidence["material_type"]["source"] == "unconfirmed"
    assert evidence["tags"] == [{"value": "虚构标签", "source": "unconfirmed", "snippets": []}]


def test_m812_ignores_provider_claimed_evidence_and_bounds_material_excerpts(client, monkeypatch):
    provider_marker = "PROVIDER_SECRET_SHOULD_NOT_ESCAPE"
    _configure_external_provider(
        monkeypatch,
        {
            "course_name": "课程",
            "material_type": "讲义",
            "tags": ["重点"],
            "tasks": [],
            "field_evidence": {
                "course_name": {
                    "source": "https://attacker.invalid/claim",
                    "snippets": [provider_marker * 50, "C:\\provider\\secret"],
                }
            },
        },
    )
    material = client.post(
        "/api/materials",
        json={
            "original_filename": "C:\\private\\课程-讲义.txt",
            "extracted_text": "重点：" + ("安全内容" * 100) + " https://example.invalid/private C:\\hidden\\token",
        },
    ).json()

    response = client.post(
        f"/api/materials/{material['id']}/extract",
        json={"provider": "openai-compatible"},
    )

    assert response.status_code == 200
    rendered = str(response.json()["field_evidence"])
    assert provider_marker not in rendered
    assert "attacker.invalid" not in rendered
    assert "C:\\provider\\secret" not in rendered
    assert "C:\\private" not in rendered
    assert "https://example.invalid" not in rendered
    assert all(
        len(snippet) <= 180
        for entry in [
            response.json()["field_evidence"]["course_name"],
            response.json()["field_evidence"]["material_type"],
            *response.json()["field_evidence"]["tags"],
        ]
        if entry
        for snippet in entry["snippets"]
    )


def test_m812_rejects_provider_tag_count_beyond_bounded_evidence_contract(client, monkeypatch):
    _configure_external_provider(
        monkeypatch,
        {
            "course_name": "课程",
            "material_type": "讲义",
            "tags": [f"标签{index}" for index in range(31)],
            "tasks": [],
        },
    )
    material = client.post(
        "/api/materials",
        json={"original_filename": "课程讲义.txt", "extracted_text": "课程正文"},
    ).json()

    response = client.post(
        f"/api/materials/{material['id']}/extract",
        json={"provider": "openai-compatible"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_PROVIDER_JSON"
    saved = client.get(f"/api/materials/{material['id']}").json()
    assert saved["extraction_status"] == "failed"
    assert saved["extraction_result"] is None


def test_m812_confirmation_keeps_evidence_snapshot_and_old_result_still_reads(client):
    material = client.post(
        "/api/materials",
        json={
            "original_filename": "算法-作业通知.txt",
            "extracted_text": "2026年10月15日 23:59",
        },
    ).json()
    extracted = client.post(f"/api/materials/{material['id']}/extract").json()
    candidate = extracted["tasks"][0]
    snapshot = extracted["field_evidence"]

    confirmed = client.post(
        f"/api/materials/{material['id']}/extraction/confirm",
        json={"tasks": [candidate], "material_type": "用户修订类型", "tags": ["用户修订标签"]},
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["field_evidence"] == snapshot
    reread = client.get(f"/api/materials/{material['id']}/extraction")
    assert reread.status_code == 200
    assert reread.json()["field_evidence"] == snapshot

    from app.database import get_db
    from app.models.material import Material

    generator = client.app.dependency_overrides[get_db]()
    db = next(generator)
    try:
        old_material = Material(
            original_filename="旧抽取结果.txt",
            extracted_text="历史资料正文",
            processing_status="processed",
            extraction_status="ready",
            extraction_result={
                "course_name": "历史课程",
                "material_type": "历史类型",
                "tags": ["历史标签"],
                "tasks": [],
                "warnings": [],
                "needs_review": False,
            },
        )
        db.add(old_material)
        db.commit()
        old_id = old_material.id
    finally:
        generator.close()

    old_read = client.get(f"/api/materials/{old_id}/extraction")
    assert old_read.status_code == 200
    assert old_read.json()["field_evidence"] == {
        "course_name": None,
        "material_type": None,
        "tags": [],
    }
