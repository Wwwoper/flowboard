from __future__ import annotations

import sqlite3

import pytest

from app.restore import restore_backup


def test_zip_backup_can_restore_database_and_attachments(client, tmp_path):
    task = client.post(
        "/api/tasks",
        json={"title": "Portable task", "description": "Backup description", "tags": "backup"},
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
        restored_task = connection.execute("SELECT title, description, tags FROM tasks").fetchone()
        attachment = connection.execute(
            "SELECT task_id, filename, stored_name FROM attachments"
        ).fetchone()
    finally:
        connection.close()

    assert restored_task == ("Portable task", "Backup description", "backup")
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
