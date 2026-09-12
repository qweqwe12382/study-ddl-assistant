import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("backup_data", ROOT / "scripts" / "backup_data.py")
backup_data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup_data)


def run_probe(root, mode, evidence):
    env = dict(os.environ)
    env.update({
        "DATABASE_URL": f"sqlite:///{(root / 'app.db').as_posix()}",
        "AUTH_DATABASE_URL": f"sqlite:///{(root / 'auth.db').as_posix()}",
        "USER_DATABASE_DIR": str(root / "users"), "UPLOAD_DIR": str(root / "uploads"),
        "APP_ENV": "test", "DEMO_MODE": "false", "AUTH_COOKIE_SECURE": "false",
        "LLM_API_KEY": "", "LLM_MODEL": "", "LOG_LEVEL": "ERROR",
        "PYTHONPATH": str(ROOT / "backend"),
    })
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("backup_runtime_probe.py")), mode, str(evidence)], env=env, cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def test_real_two_account_backup_restore_preserves_files_and_identity(tmp_path):
    source, archive, restored = (tmp_path / name for name in ("source", "backup", "restored"))
    evidence = tmp_path / "identities.json"
    run_probe(source, "seed", evidence)
    before = backup_data.inventory(source)
    incomplete = source / "uploads" / ".interrupted.part"
    incomplete.write_bytes(b"partial")
    with pytest.raises(ValueError, match="Incomplete"):
        backup_data.create_backup(system_db=source / "app.db", auth_db=source / "auth.db", user_dir=source / "users", uploads=source / "uploads", output=archive)
    assert not archive.exists()
    incomplete.unlink()
    for unexpected in (source / "users" / "note.bin", source / "users" / "nested"):
        if unexpected.suffix:
            unexpected.write_bytes(b"must not be silently omitted")
        else:
            unexpected.mkdir()
            (unexpected / ("a" * 32 + ".db")).write_bytes(b"nested database")
        with pytest.raises(ValueError, match="Unexpected item in source"):
            backup_data.create_backup(system_db=source / "app.db", auth_db=source / "auth.db", user_dir=source / "users", uploads=source / "uploads", output=archive)
        assert not archive.exists()
        if unexpected.is_dir():
            (unexpected / ("a" * 32 + ".db")).unlink()
            unexpected.rmdir()
        else:
            unexpected.unlink()
    summary = backup_data.create_backup(system_db=source / "app.db", auth_db=source / "auth.db", user_dir=source / "users", uploads=source / "uploads", output=archive)
    assert summary["accounts"] == summary["referenced_uploads"] == 2
    assert summary["uninitialized_workspaces"] == []
    assert backup_data.verify_backup(archive) == summary
    manifest = json.loads((archive / "manifest.json").read_text())
    assert manifest["removed_session_count"] == 2
    for name, metadata in summary["database_metadata"].items():
        original_metadata = backup_data.database_metadata(source / name, {"users", "user_sessions"} if name == "auth.db" else backup_data.BUSINESS_TABLES)
        if name == "auth.db":
            original_metadata["rows"]["user_sessions"] = 0
        assert original_metadata == metadata
    with sqlite3.connect(archive / "auth.db") as db:
        assert db.execute("SELECT count(*) FROM user_sessions").fetchone()[0] == 0
    assert backup_data.restore_backup(archive, restored) == summary
    assert backup_data.verify_backup(restored) == summary
    paths = json.loads((restored / "runtime-paths.json").read_text())
    assert paths["USER_DATABASE_DIR"] == str(restored / "users")
    backup_before = backup_data.inventory(archive)
    run_probe(restored, "verify", evidence)
    assert backup_data.inventory(source) == before
    assert backup_data.inventory(archive) == backup_before
    with pytest.raises(ValueError, match="must be new"):
        backup_data.restore_backup(archive, source)
    upload = next(path for path in (archive / "uploads").rglob("*") if path.is_file())
    original = upload.read_bytes()
    upload.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="modified"):
        backup_data.restore_backup(archive, tmp_path / "corrupt-restore")
    assert not (tmp_path / "corrupt-restore").exists()
    upload.write_bytes(original)
    # Even if a checksum manifest is recomputed, account path ownership is checked.
    user_db = next((archive / "users").glob("*.db"))
    with sqlite3.connect(user_db) as db:
        db.execute("UPDATE materials SET stored_path = 'another-account/notice.txt'")
    manifest_path = archive / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][user_db.relative_to(archive).as_posix()]["sha256"] = backup_data.digest(user_db)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="different account"):
        backup_data.verify_backup(archive)


def test_backup_rejects_modified_files_and_unsafe_manifest(tmp_path):
    # Minimal malformed artifacts must be rejected before any restore write.
    archive = tmp_path / "archive"
    archive.mkdir()
    manifest = {"format": 1, "sessions_removed": True, "model_version": backup_data.model_version(), "files": {"app.db": {"size": 0, "sha256": "bad"}, "auth.db": {"size": 0, "sha256": "bad"}}}
    (archive / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="missing or modified"):
        backup_data.restore_backup(archive, tmp_path / "destination")
    assert not (tmp_path / "destination").exists()
    for value in ("../escape", "C:/escape", "a/../escape", "a\\..\\escape", "/absolute"):
        with pytest.raises(ValueError, match="Unsafe"):
            backup_data.relative_path(value)
