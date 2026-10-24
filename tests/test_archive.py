from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from app.db import connect, initialize_database
from app.config import settings


def _create_done_task(client, title: str = "Completed task") -> dict:
    task = client.post("/api/tasks", json={"title": title}).json()
    response = client.patch(f"/api/tasks/{task['id']}", json={"status": "done"})
    assert response.status_code == 200, response.text
    return response.json()


def _age_done_task(task_id: int, *, days: int = 45, recent_update: bool = False) -> None:
    finished = (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="seconds").replace("+00:00", "Z")
    updated = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z") if recent_update else finished
    connection = connect(settings.db_path)
    try:
        connection.execute(
            "UPDATE tasks SET closed_at = ?, updated_at = ? WHERE id = ?",
            (finished, updated, task_id),
        )
        connection.commit()
    finally:
        connection.close()


def test_legacy_database_migrates_archived_at_without_losing_tasks(tmp_path):
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE tasks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'todo',
          position REAL NOT NULL DEFAULT 0,
          tags TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          closed_at TEXT NULL
        );
        INSERT INTO tasks (id, title, status, created_at, updated_at)
        VALUES (17, 'Existing task', 'todo', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z');
        """
    )
    connection.commit()
    connection.close()

    initialize_database(db_path)
    connection = connect(db_path)
    try:
        task = connection.execute(
            "SELECT id, title, archived_at FROM tasks WHERE id = 17"
        ).fetchone()
        settings_rows = dict(connection.execute("SELECT key, value FROM app_settings").fetchall())
    finally:
        connection.close()

    assert tuple(task) == (17, "Existing task", None)
    assert settings_rows["archive_enabled"] == "true"
    assert settings_rows["archive_after_days"] == "30"


def test_auto_archive_moves_only_old_completed_tasks_and_preserves_recent_activity(client):
    old = _create_done_task(client, "Old completed task")
    recently_edited = _create_done_task(client, "Recently changed completed task")
    _age_done_task(old["id"], days=45)
    _age_done_task(recently_edited["id"], days=45, recent_update=True)

    board = client.get("/api/tasks").json()
    assert old["id"] not in {task["id"] for task in board}
    assert recently_edited["id"] in {task["id"] for task in board}

    archived = client.get("/api/archive/tasks").json()
    assert [task["id"] for task in archived] == [old["id"]]
    assert archived[0]["archived_at"]
    detail = client.get(f"/api/tasks/{old['id']}").json()
    assert detail["title"] == "Old completed task"


def test_archive_settings_can_disable_auto_archiving_and_validate_period(client):
    old = _create_done_task(client, "Keep on board")
    _age_done_task(old["id"], days=120)
    settings_response = client.patch("/api/archive/settings", json={"archive_enabled": False})
    assert settings_response.status_code == 200
    assert settings_response.json() == {"archive_enabled": False, "archive_after_days": 30}
    assert old["id"] in {task["id"] for task in client.get("/api/tasks").json()}

    invalid = client.patch("/api/archive/settings", json={"archive_after_days": 14})
    assert invalid.status_code == 422
    valid = client.patch("/api/archive/settings", json={"archive_enabled": True, "archive_after_days": 7})
    assert valid.status_code == 200
    assert valid.json() == {"archive_enabled": True, "archive_after_days": 7}
    assert old["id"] not in {task["id"] for task in client.get("/api/tasks").json()}


def test_manual_archive_restore_and_bulk_archive_keep_task_and_attachment_data(client):
    task = _create_done_task(client, "Manual archive task")
    upload = client.post(
        f"/api/tasks/{task['id']}/files",
        files=[("files", ("proof.txt", b"keep attachment", "text/plain"))],
    )
    assert upload.status_code == 201

    active = client.post("/api/tasks", json={"title": "Not completed"}).json()
    assert client.post(f"/api/archive/tasks/{active['id']}").status_code == 409
    archived = client.post(f"/api/archive/tasks/{task['id']}")
    assert archived.status_code == 200
    assert archived.json()["archived_at"]
    assert task["id"] not in {item["id"] for item in client.get("/api/tasks").json()}
    assert client.get(f"/api/tasks/{task['id']}").json()["attachments_count"] == 1

    restored = client.post(f"/api/archive/tasks/{task['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["archived_at"] is None
    assert task["id"] in {item["id"] for item in client.get("/api/tasks").json()}
    file_id = upload.json()[0]["id"]
    assert client.get(f"/api/files/{file_id}").content == b"keep attachment"

    second = _create_done_task(client, "Bulk archive task")
    bulk = client.post("/api/archive/completed")
    assert bulk.status_code == 200
    assert bulk.json()["archived"] == 2
    assert {task["id"] for task in client.get("/api/archive/tasks").json()} == {task["id"], second["id"]}


def test_backup_keeps_archived_tasks_and_restore_preserves_archive_state(client, tmp_path):
    task = _create_done_task(client, "Archived backup task")
    assert client.post(f"/api/archive/tasks/{task['id']}").status_code == 200
    backup = tmp_path / "archived-flowboard.zip"
    backup.write_bytes(client.get("/api/export?format=zip").content)

    target = tmp_path / "restored"
    from app.restore import restore_backup

    assert restore_backup(backup, target) == 1
    connection = sqlite3.connect(target / "tracker.db")
    try:
        archived_at = connection.execute("SELECT archived_at FROM tasks WHERE id = ?", (task["id"],)).fetchone()[0]
    finally:
        connection.close()
    assert archived_at



def test_reopening_an_archived_task_returns_it_to_the_board(client):
    task = _create_done_task(client, "Archived task to reopen")
    assert client.post(f"/api/archive/tasks/{task['id']}").status_code == 200
    reopened = client.patch(f"/api/tasks/{task['id']}", json={"status": "todo"})
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["archived_at"] is None
    assert reopened.json()["closed_at"] is None
    assert task["id"] in {item["id"] for item in client.get("/api/tasks").json()}


def test_archive_dialog_has_a_period_filter(client):
    html = client.get("/").text
    assert 'id="archive-period-filter"' in html
    assert "За 7 дней" in html
    assert "За 30 дней" in html
    assert "За 90 дней" in html
