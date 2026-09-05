"""Regression coverage using representative files from the local learning dataset."""

from pathlib import Path

import pytest


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "learning_materials"
DATASET_CASES = (
    {
        "fixture": "data-structure-2022-exam.pdf",
        "filename": "2022数据结构A.pdf",
        "content_type": "application/pdf",
        "marker": "数据结构",
    },
    {
        "fixture": "data-structure-lab-2.docx",
        "filename": "第二次上机题.docx",
        "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "marker": "二叉树",
    },
)


@pytest.mark.parametrize("case", DATASET_CASES, ids=lambda case: case["fixture"])
def test_representative_learning_dataset_materials_upload_and_parse(client, isolated_upload_dir, case):
    fixture_path = FIXTURE_DIR / case["fixture"]

    response = client.post(
        "/api/materials/upload",
        data={"material_type": "学习资料"},
        files={"files": (case["filename"], fixture_path.read_bytes(), case["content_type"])},
    )

    assert response.status_code == 201, response.text
    material = response.json()[0]
    stored_path = isolated_upload_dir / material["stored_path"]

    assert material["original_filename"] == case["filename"]
    assert material["file_type"] == fixture_path.suffix.lstrip(".")
    assert material["processing_status"] == "processed"
    assert material["processing_error"] is None
    assert case["marker"] in material["extracted_text"]
    assert len(material["content_hash"]) == 64
    assert material["extraction_provider"] == "local-rules"
    assert material["extraction_status"] in {"ready", "needs_review"}
    assert stored_path.is_file()
