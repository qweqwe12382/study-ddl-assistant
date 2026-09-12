"""Offline, local SQLite/upload backup. Never imports the application or its .env.

Backups are private directories, not submission artifacts. Stop the application
before backup; restore always creates a new directory and never edits a source.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3


FORMAT = 1
WORKSPACE = re.compile(r"^[0-9a-f]{32}$")
BUSINESS_TABLES = {
    "materials", "tasks", "courses", "study_preferences", "study_plans",
    "course_calibration_states", "class_sessions", "exams", "academic_calendar_sync_links",
    "agent_runs", "agent_suggestions", "action_receipts", "agent_events", "agent_reminders",
    "weekly_review_snapshots", "agent_reminder_preferences",
}


def model_version() -> str:
    app = Path(__file__).resolve().parents[1] / "backend" / "app"
    paths = sorted((app / "models").glob("*.py")) + [app / "database.py", app / "auth_database.py"]
    return hashlib.sha256("".join(digest(path) for path in paths).encode()).hexdigest()


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def plain_path(path: Path) -> Path:
    path = path.absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError("Symbolic links and junctions are not supported")
    return path.resolve()


def relative_path(value: str) -> Path:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or any(
        part in (".", "..") or ":" in part for part in normalized.split("/")
    ) or "" in normalized.split("/"):
        raise ValueError("Unsafe relative file path")
    return Path(*path.parts)


def read_db(path: Path):
    return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)


def check_db(path: Path) -> None:
    with closing(read_db(path)) as db:
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("SQLite integrity check failed")
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("SQLite foreign key check failed")


def database_metadata(path: Path, required_tables: set[str]) -> dict:
    with closing(read_db(path)) as db:
        schema = db.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        if not required_tables.issubset({name for name, _ in schema}):
            raise ValueError("Required application tables missing; cross-version recovery is unsupported")
        counts = {}
        for name, _ in schema:
            quoted = '"' + name.replace('"', '""') + '"'
            counts[name] = db.execute(f"SELECT count(*) FROM {quoted}").fetchone()[0]
            columns = db.execute(f"PRAGMA table_info({quoted})").fetchall()
            for _, column, kind, *_ in columns:
                column_sql = '"' + column.replace('"', '""') + '"'
                if kind.upper() == "JSON":
                    for (value,) in db.execute(f"SELECT {column_sql} FROM {quoted} WHERE {column_sql} IS NOT NULL"):
                        json.loads(value)
                if column == "navigation_key":
                    keys = [value for (value,) in db.execute(f"SELECT {column_sql} FROM {quoted}")]
                    if any(not isinstance(value, str) or not WORKSPACE.fullmatch(value) for value in keys) or len(keys) != len(set(keys)):
                        raise ValueError("Invalid or duplicate source navigation identity")
        return {"rows": counts, "schema_sha256": hashlib.sha256(json.dumps(schema).encode()).hexdigest()}


def snapshot(source: Path, target: Path, *, clear_sessions: bool = False) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    removed = 0
    with closing(read_db(source)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
        if clear_sessions:
            removed = dst.execute("SELECT count(*) FROM user_sessions").fetchone()[0]
            dst.execute("DELETE FROM user_sessions")
            dst.commit()
    check_db(target)
    return removed


def inventory(root: Path) -> dict[str, dict]:
    return {
        path.relative_to(root).as_posix(): {"size": path.stat().st_size, "sha256": digest(path)}
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def source_fingerprint(system_db: Path, auth_db: Path, user_dir: Path, uploads: Path) -> dict[str, str]:
    files = [system_db, auth_db]
    if user_dir.exists():
        files.extend(path for path in user_dir.rglob("*") if path.is_file())
    files.extend(path for path in uploads.rglob("*") if path.is_file())
    for database in (system_db, auth_db):
        files.extend(sidecar for suffix in ("-wal", "-shm", "-journal") if (sidecar := Path(str(database) + suffix)).exists())
    return {str(plain_path(path)): digest(path) for path in files}


def validate_data(root: Path) -> dict:
    """Validate account mapping and actual upload bytes, without exposing records."""
    auth = root / "auth.db"
    check_db(auth)
    with closing(read_db(auth)) as db:
        keys = [row[0] for row in db.execute("SELECT workspace_key FROM users")]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate account workspace mapping")
        if any(key != "legacy" and not WORKSPACE.fullmatch(key) for key in keys):
            raise ValueError("Invalid account workspace mapping")
        if db.execute("SELECT count(*) FROM user_sessions").fetchone()[0]:
            raise ValueError("Backup must not retain login sessions")

    workspaces = [("legacy", root / "app.db")]
    user_root = root / "users"
    for path in user_root.iterdir():
        if not path.is_file() or path.suffix != ".db" or not WORKSPACE.fullmatch(path.stem):
            raise ValueError("Unexpected item in user database directory")
    for path in sorted(user_root.glob("*.db")):
        if not WORKSPACE.fullmatch(path.stem):
            raise ValueError("Invalid user database filename")
        workspaces.append((path.stem, path))
    material_files = 0
    metadata_missing = 0
    referenced = set()
    databases = {"auth.db": database_metadata(auth, {"users", "user_sessions"})}
    for key, path in workspaces:
        check_db(path)
        databases[path.relative_to(root).as_posix()] = database_metadata(path, BUSINESS_TABLES)
        with closing(read_db(path)) as db:
            for stored, content_hash, file_size in db.execute("SELECT stored_path, content_hash, file_size FROM materials WHERE stored_path IS NOT NULL"):
                relative = relative_path(stored)
                if key != "legacy" and relative.parts[0] != key:
                    raise ValueError("Upload belongs to a different account workspace")
                if key == "legacy" and len(relative.parts) != 1:
                    raise ValueError("Legacy upload must be directly in upload root")
                upload = plain_path(root / "uploads" / relative)
                if not upload.is_file():
                    raise ValueError("Referenced upload is missing")
                if file_size is not None and upload.stat().st_size != file_size:
                    raise ValueError("Referenced upload size differs")
                if content_hash and digest(upload) != content_hash:
                    raise ValueError("Referenced upload content hash differs")
                metadata_missing += int(content_hash is None or file_size is None)
                referenced.add(relative.as_posix())
                material_files += 1
    return {
        "accounts": len(keys), "databases": len(workspaces) + 1,
        "referenced_uploads": material_files,
        "database_metadata": databases,
        "uploads_without_complete_metadata": metadata_missing,
        "orphan_uploads": sorted(path.relative_to(root / "uploads").as_posix() for path in (root / "uploads").rglob("*") if path.is_file() and path.relative_to(root / "uploads").as_posix() not in referenced),
        "orphan_workspace_databases": [key for key, _ in workspaces if key != "legacy" and key not in keys],
        # An account can exist before its first request opens its lazy database.
        "uninitialized_workspaces": [key for key in keys if key != "legacy" and not (user_root / f"{key}.db").exists()],
    }


def create_backup(*, system_db: Path, auth_db: Path, user_dir: Path, uploads: Path, output: Path) -> dict:
    sources = [plain_path(path) for path in (system_db, auth_db, user_dir, uploads)]
    system_db, auth_db, user_dir, uploads = sources
    output = plain_path(output)
    if system_db == auth_db or user_dir == uploads or user_dir in uploads.parents or uploads in user_dir.parents:
        raise ValueError("Source database and directory roles must be distinct")
    if any(directory == database or directory in database.parents for directory in (user_dir, uploads) for database in (system_db, auth_db)):
        raise ValueError("System/auth databases must be outside user and upload directories")
    if output.exists() or any(output == source or source in output.parents for source in sources):
        raise ValueError("Backup destination must be new and outside source directories")
    if not system_db.is_file() or not auth_db.is_file() or not uploads.is_dir():
        raise ValueError("System/auth database and uploads directory must exist")
    if user_dir.exists() and not user_dir.is_dir():
        raise ValueError("User database directory is not a directory")
    if user_dir.exists():
        for path in user_dir.iterdir():
            # SQLite sidecars are absorbed by backup(), not copied as separate
            # databases. Everything else must be explicitly rejected, not lost.
            match = re.fullmatch(r"([0-9a-f]{32})\.db(?:-(wal|shm|journal))?", path.name)
            if not path.is_file() or not match or not (user_dir / f"{match[1]}.db").is_file():
                raise ValueError("Unexpected item in source user database directory")
    for directory in (user_dir, uploads):
        for path in directory.rglob("*"):
            plain_path(path)
            if path.name.endswith(".part"):
                raise ValueError("Incomplete .part file found; finish or inspect the interrupted write first")
    source_files = [system_db, auth_db]
    if user_dir.exists():
        source_files += sorted(user_dir.glob("*.db"))
    source_files += sorted(path for path in uploads.rglob("*") if path.is_file())
    for path in source_files:
        plain_path(path)
    # Detect ordinary accidental writes; this does not replace stopping services.
    before = source_fingerprint(system_db, auth_db, user_dir, uploads)
    output.mkdir(parents=True, exist_ok=False)
    (output / "users").mkdir()
    (output / "uploads").mkdir()
    snapshot(system_db, output / "app.db")
    removed_sessions = snapshot(auth_db, output / "auth.db", clear_sessions=True)
    for path in source_files[2:]:
        if path.parent == user_dir:
            if not WORKSPACE.fullmatch(path.stem):
                raise ValueError("Unexpected user database filename")
            snapshot(path, output / "users" / path.name)
        else:
            target = output / "uploads" / path.relative_to(uploads)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    if source_fingerprint(system_db, auth_db, user_dir, uploads) != before:
        raise ValueError("Source changed during backup; stop services and retry to a new directory")
    summary = validate_data(output)
    manifest = {
        "format": FORMAT, "created_at": datetime.now(timezone.utc).isoformat(),
        "sessions_removed": True, "removed_session_count": removed_sessions,
        "model_version": model_version(), "summary": summary, "files": inventory(output),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def verify_backup(root: Path) -> dict:
    root = plain_path(root)
    for path in root.rglob("*"):
        plain_path(path)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != FORMAT or manifest.get("sessions_removed") is not True:
        raise ValueError("Unsupported or incomplete backup")
    if manifest.get("model_version") != model_version():
        raise ValueError("Backup model version differs; use the matching application version")
    files = manifest["files"]
    if not isinstance(files, dict) or not {"app.db", "auth.db"}.issubset(files):
        raise ValueError("Missing required backup databases")
    if len({name.casefold() for name in files}) != len(files):
        raise ValueError("Ambiguous duplicate paths")
    for name, metadata in files.items():
        relative = relative_path(name)
        if name not in ("app.db", "auth.db", "runtime-paths.json") and relative.parts[0] not in ("users", "uploads"):
            raise ValueError("Unexpected backup file")
        path = root / relative
        if not path.is_file() or path.stat().st_size != metadata["size"] or digest(path) != metadata["sha256"]:
            raise ValueError("Backup file is missing or modified")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != set(files) | {"manifest.json"}:
        raise ValueError("Unlisted files in backup")
    summary = validate_data(root)
    if summary != manifest["summary"]:
        raise ValueError("Backup database metadata differs from manifest")
    return summary


def restore_backup(backup: Path, destination: Path) -> dict:
    backup, destination = plain_path(backup), plain_path(destination)
    summary = verify_backup(backup)
    if destination.exists() or backup in destination.parents:
        raise ValueError("Restore destination must be new and outside backup")
    shutil.copytree(backup, destination)
    verify_backup(destination)
    # No credentials/model keys are exported. These are portable runtime paths.
    environment = {
        "DATABASE_URL": f"sqlite:///{(destination / 'app.db').as_posix()}",
        "AUTH_DATABASE_URL": f"sqlite:///{(destination / 'auth.db').as_posix()}",
        "USER_DATABASE_DIR": str(destination / "users"),
        "UPLOAD_DIR": str(destination / "uploads"),
        "DEMO_MODE": "false",
    }
    (destination / "runtime-paths.json").write_text(json.dumps(environment, indent=2), encoding="utf-8")
    manifest_path = destination / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths_file = destination / "runtime-paths.json"
    manifest["files"]["runtime-paths.json"] = {"size": paths_file.stat().st_size, "sha256": digest(paths_file)}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    verify_backup(destination)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup")
    for name in ("system-db", "auth-db", "user-dir", "uploads", "output"):
        backup.add_argument(f"--{name}", type=Path, required=True)
    backup.add_argument("--services-stopped", action="store_true", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("backup", type=Path)
    restore = commands.add_parser("restore")
    restore.add_argument("backup", type=Path)
    restore.add_argument("destination", type=Path)
    args = vars(parser.parse_args())
    command = args.pop("command")
    if command == "backup":
        args.pop("services_stopped")
        result = create_backup(**args)
    elif command == "verify":
        result = verify_backup(args["backup"])
    else:
        result = restore_backup(**args)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
