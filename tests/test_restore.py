from __future__ import annotations

import json
import sqlite3
import zipfile

import pytest

from app.restore import restore_backup


def test_zip_backup_can_restore_database_and_attachments(client, tmp_path):
    task = client.post(
        "/api/tasks",
        json={
            "title": "Portable task",
            "description": "Backup description",
            "result": "Verified outcome",
            "tags": "backup",
        },
    ).json()
    upload = client.post(
        f"/api/tasks/{task['id']}/files",
        files=[("files", ("proof.txt", b"restore this", "text/plain"))],
    )
    assert upload.status_code == 201

    archive_path = tmp_path / "flowboard.zip"
    archive_path.write_bytes(client.get("/api/export?format=zip").content)
    target = tmp_path / "recovered-data"
    assert restore_backup(archive_path, target) == 1

    connection = sqlite3.connect(target / "tracker.db")
    try:
        restored_task = connection.execute(
            "SELECT title, description, result, tags FROM tasks"
        ).fetchone()
        attachment = connection.execute(
            "SELECT task_id, filename, stored_name FROM attachments"
        ).fetchone()
    finally:
        connection.close()

    assert restored_task == ("Portable task", "Backup description", "Verified outcome", "backup")
    assert attachment[:2] == (task["id"], "proof.txt")
    restored_file = target / "attachments" / str(task["id"]) / attachment[2]
    assert restored_file.read_bytes() == b"restore this"


def test_restore_refuses_to_overwrite_nonempty_directory(client, tmp_path):
    archive_path = tmp_path / "backup.zip"
    archive_path.write_bytes(client.get("/api/export?format=zip").content)
    target = tmp_path / "existing"
    target.mkdir()
    (target / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        restore_backup(archive_path, target)
    assert (target / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_restore_accepts_legacy_manifest_without_result(client, tmp_path):
    exported = client.post(
        "/api/tasks", json={"title": "Legacy backup task", "description": "Old data"}
    ).json()
    source = tmp_path / "source.zip"
    source.write_bytes(client.get("/api/export?format=zip").content)
    legacy = tmp_path / "legacy.zip"
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(legacy, "w") as backup:
        manifest = json.loads(original.read("tasks.json"))
        for item in manifest["tasks"]:
            item.pop("result", None)
        backup.writestr("tasks.json", json.dumps(manifest))
        for name in original.namelist():
            if name != "tasks.json":
                backup.writestr(name, original.read(name))

    target = tmp_path / "legacy-restored"
    assert restore_backup(legacy, target) == 1
    connection = sqlite3.connect(target / "tracker.db")
    try:
        result = connection.execute(
            "SELECT result FROM tasks WHERE id = ?", (exported["id"],)
        ).fetchone()
    finally:
        connection.close()
    assert result == ("",)
