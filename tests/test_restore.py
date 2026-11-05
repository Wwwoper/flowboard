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
            item.pop("task_type", None)
            item["tags"] = "bug, legacy-tag"
        manifest.pop("worksets", None)
        manifest.pop("workset_memberships", None)
        manifest.pop("workset_events", None)
        backup.writestr("tasks.json", json.dumps(manifest))
        for name in original.namelist():
            if name != "tasks.json":
                backup.writestr(name, original.read(name))

    target = tmp_path / "legacy-restored"
    assert restore_backup(legacy, target) == 1
    connection = sqlite3.connect(target / "tracker.db")
    try:
        result = connection.execute(
            "SELECT result, tags, task_type FROM tasks WHERE id = ?", (exported["id"],)
        ).fetchone()
    finally:
        connection.close()
    assert result == ("", "legacy-tag", "bug")


def test_zip_backup_preserves_history_for_a_deleted_empty_workset(client, tmp_path):
    task = client.post(
        "/api/tasks", json={"title": "Removed member", "tags": "project:history"}
    ).json()
    workset = client.post(
        "/api/worksets", json={"project_slug": "history", "name": "Temporary"}
    ).json()
    client.post(f"/api/worksets/{workset['id']}/tasks", json={"task_id": task["id"]})
    client.delete(f"/api/worksets/{workset['id']}/tasks/{task['id']}")

    archive_path = tmp_path / "deleted-workset.zip"
    archive_path.write_bytes(client.get("/api/export?format=zip").content)
    target = tmp_path / "deleted-workset-restored"
    restore_backup(archive_path, target)

    connection = sqlite3.connect(target / "tracker.db")
    try:
        worksets = connection.execute("SELECT COUNT(*) FROM worksets").fetchone()[0]
        events = connection.execute(
            "SELECT workset_id, workset_name, event_type FROM workset_events ORDER BY id"
        ).fetchall()
    finally:
        connection.close()

    assert worksets == 0
    assert events == [
        (workset["id"], "Temporary", "created"),
        (workset["id"], "Temporary", "task_added"),
        (workset["id"], "Temporary", "task_removed"),
        (workset["id"], "Temporary", "deleted_empty"),
    ]


def test_zip_backup_restores_worksets_memberships_and_history(client, tmp_path):
    task = client.post(
        "/api/tasks", json={"title": "Workset backup", "tags": "project:release"}
    ).json()
    workset = client.post(
        "/api/worksets", json={"project_slug": "release", "name": "Release prep"}
    ).json()
    added = client.post(
        f"/api/worksets/{workset['id']}/tasks", json={"task_id": task["id"]}
    )
    assert added.status_code == 200

    archive_path = tmp_path / "worksets.zip"
    archive_path.write_bytes(client.get("/api/export?format=zip").content)
    target = tmp_path / "worksets-restored"
    assert restore_backup(archive_path, target) == 1

    connection = sqlite3.connect(target / "tracker.db")
    try:
        restored_workset = connection.execute(
            "SELECT project_slug, name, status FROM worksets WHERE id = ?", (workset["id"],)
        ).fetchone()
        membership = connection.execute(
            "SELECT workset_id, task_id FROM workset_memberships"
        ).fetchone()
        events = connection.execute(
            "SELECT event_type, task_title FROM workset_events ORDER BY id"
        ).fetchall()
    finally:
        connection.close()

    assert restored_workset == ("release", "Release prep", "active")
    assert membership == (workset["id"], task["id"])
    assert events == [("created", ""), ("task_added", "Workset backup")]


def test_zip_restore_keeps_historical_ids_for_deleted_tasks_and_sets(client, tmp_path):
    deleted_task = client.post(
        "/api/tasks", json={"title": "Removed later", "tags": "project:history"}
    ).json()
    remaining_task = client.post(
        "/api/tasks", json={"title": "Still present", "tags": "project:history"}
    ).json()
    workset = client.post(
        "/api/worksets", json={"project_slug": "history", "name": "History"}
    ).json()
    for task in (deleted_task, remaining_task):
        client.post(f"/api/worksets/{workset['id']}/tasks", json={"task_id": task["id"]})
    for task in (deleted_task, remaining_task):
        client.patch(f"/api/tasks/{task['id']}", json={"status": "done"})
    client.delete(f"/api/tasks/{deleted_task['id']}")

    archive_path = tmp_path / "historical-ids.zip"
    archive_path.write_bytes(client.get("/api/export?format=zip").content)
    target = tmp_path / "historical-ids-restored"
    restore_backup(archive_path, target)

    connection = sqlite3.connect(target / "tracker.db")
    try:
        event = connection.execute(
            """
            SELECT workset_id, task_id, task_title, task_status
            FROM workset_events
            WHERE event_type = 'task_deleted'
            """
        ).fetchone()
        foreign_keys = connection.execute("PRAGMA foreign_key_list(workset_events)").fetchall()
    finally:
        connection.close()

    assert event == (workset["id"], deleted_task["id"], "Removed later", "done")
    assert foreign_keys == []


def test_restore_accepts_legacy_workset_events_without_new_snapshot_fields(client, tmp_path):
    task = client.post(
        "/api/tasks", json={"title": "Legacy event", "tags": "project:legacy"}
    ).json()
    workset = client.post(
        "/api/worksets", json={"project_slug": "legacy", "name": "Legacy set"}
    ).json()
    client.post(f"/api/worksets/{workset['id']}/tasks", json={"task_id": task["id"]})

    source = tmp_path / "current.zip"
    source.write_bytes(client.get("/api/export?format=zip").content)
    legacy = tmp_path / "legacy-events.zip"
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(legacy, "w") as backup:
        manifest = json.loads(original.read("tasks.json"))
        for event in manifest["workset_events"]:
            for field in ("task_status", "task_closed_at", "task_count", "done_count"):
                event.pop(field, None)
        backup.writestr("tasks.json", json.dumps(manifest))
        for name in original.namelist():
            if name != "tasks.json":
                backup.writestr(name, original.read(name))

    target = tmp_path / "legacy-events-restored"
    restore_backup(legacy, target)
    connection = sqlite3.connect(target / "tracker.db")
    try:
        snapshots = connection.execute(
            """
            SELECT task_status, task_closed_at, task_count, done_count
            FROM workset_events ORDER BY id
            """
        ).fetchall()
    finally:
        connection.close()
    assert snapshots == [(None, None, None, None), (None, None, None, None)]


def test_zip_backup_restores_long_description_and_result(client, tmp_path):
    description = "description " * 1_500
    result = "result " * 1_500
    created = client.post(
        "/api/tasks",
        json={"title": "Long backup task", "description": description, "result": result},
    )
    assert created.status_code == 201, created.text

    archive_path = tmp_path / "long-backup.zip"
    archive_path.write_bytes(client.get("/api/export?format=zip").content)
    target = tmp_path / "long-restored"
    assert restore_backup(archive_path, target) == 1

    connection = sqlite3.connect(target / "tracker.db")
    try:
        restored = connection.execute("SELECT description, result FROM tasks").fetchone()
    finally:
        connection.close()

    assert restored == (description, result)


@pytest.mark.parametrize("field", ["description", "result"])
def test_restore_rejects_task_text_over_30000_characters(client, tmp_path, field):
    created = client.post("/api/tasks", json={"title": "Restore validation"})
    assert created.status_code == 201, created.text
    source = tmp_path / "valid.zip"
    source.write_bytes(client.get("/api/export?format=zip").content)
    invalid = tmp_path / f"invalid-{field}.zip"
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(invalid, "w") as backup:
        manifest = json.loads(original.read("tasks.json"))
        manifest["tasks"][0][field] = "x" * 30_001
        backup.writestr("tasks.json", json.dumps(manifest))
        for name in original.namelist():
            if name != "tasks.json":
                backup.writestr(name, original.read(name))

    with pytest.raises(ValueError, match="Некорректное описание|Некорректный результат"):
        restore_backup(invalid, tmp_path / f"restored-{field}")


@pytest.mark.parametrize(
    ("manifest", "message"),
    [
        ([], "Корневой объект"),
        (None, "Корневой объект"),
        (True, "Корневой объект"),
        ({"format_version": True, "tasks": []}, "версия формата"),
        ({"format_version": 1, "tasks": [[]]}, "Запись задачи"),
        (
            {"format_version": 1, "tasks": [{"id": 1, "attachments": [[]]}]},
            "список вложений",
        ),
        ({"format_version": 1, "tasks": [], "worksets": [[]]}, "worksets"),
        (
            {"format_version": 1, "tasks": [], "workset_memberships": [[]]},
            "workset_memberships",
        ),
        (
            {"format_version": 1, "tasks": [], "workset_events": [[]]},
            "workset_events",
        ),
    ],
)
def test_restore_rejects_invalid_manifest_structure(tmp_path, manifest, message):
    archive_path = tmp_path / "invalid-manifest.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("tasks.json", json.dumps(manifest))

    with pytest.raises(ValueError, match=message):
        restore_backup(archive_path, tmp_path / "restored")


def test_restore_rejects_boolean_task_id(client, tmp_path):
    client.post("/api/tasks", json={"title": "Boolean ID validation"})
    source = tmp_path / "valid.zip"
    source.write_bytes(client.get("/api/export?format=zip").content)
    invalid = tmp_path / "boolean-id.zip"
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(invalid, "w") as backup:
        manifest = json.loads(original.read("tasks.json"))
        manifest["tasks"][0]["id"] = True
        backup.writestr("tasks.json", json.dumps(manifest))

    with pytest.raises(ValueError, match="некорректный или повторяющийся ID задачи"):
        restore_backup(invalid, tmp_path / "boolean-id-restored")


def test_restore_rejects_non_string_workset_status(tmp_path):
    archive_path = tmp_path / "invalid-workset-status.zip"
    manifest = {
        "format_version": 1,
        "tasks": [],
        "worksets": [
            {
                "id": 1,
                "project_slug": "release",
                "name": "Release",
                "status": [],
            }
        ],
    }
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("tasks.json", json.dumps(manifest))

    with pytest.raises(ValueError, match="некорректный рабочий набор"):
        restore_backup(archive_path, tmp_path / "restored")
