from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import connect
from app.main import app


@pytest.fixture
def workflow_client(tmp_path, monkeypatch):
    """Run a workflow against a dedicated SQLite database and attachment directory."""
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "workflow-data")
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_MB", 1)
    monkeypatch.setattr(settings, "WIP_LIMIT", 3)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_task_lifecycle_create_edit_move_complete_and_reopen(workflow_client):
    client = workflow_client

    created_response = client.post(
        "/api/tasks",
        json={
            "title": "  Prepare release  ",
            "description": "Initial scope",
            "tags": "project:flowboard, release",
            "task_type": "feature",
        },
    )
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()
    task_id = created["id"]
    assert created["title"] == "Prepare release"
    assert created["status"] == "todo"

    edited_response = client.patch(
        f"/api/tasks/{task_id}",
        json={
            "title": "Prepare Flowboard release",
            "description": "Updated acceptance criteria",
            "result": "Release notes and smoke tests are ready",
        },
    )
    assert edited_response.status_code == 200, edited_response.text
    assert edited_response.json()["title"] == "Prepare Flowboard release"

    for status in ("doing", "waiting", "doing"):
        moved = client.patch(f"/api/tasks/{task_id}", json={"status": status})
        assert moved.status_code == 200, moved.text
        assert moved.json()["status"] == status
        assert moved.json()["closed_at"] is None

    completed = client.patch(f"/api/tasks/{task_id}", json={"status": "done"})
    assert completed.status_code == 200, completed.text
    assert completed.json()["closed_at"]

    persisted = client.get(f"/api/tasks/{task_id}")
    assert persisted.status_code == 200
    assert persisted.json()["description"] == "Updated acceptance criteria"
    assert persisted.json()["result"] == "Release notes and smoke tests are ready"
    assert persisted.json()["status"] == "done"
    assert persisted.json()["closed_at"] == completed.json()["closed_at"]

    reopened = client.patch(f"/api/tasks/{task_id}", json={"status": "doing"})
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["closed_at"] is None
    assert client.get("/api/tasks").json()[0]["status"] == "doing"


def test_import_edit_export_and_reimport_preserves_user_visible_task_data(workflow_client):
    client = workflow_client
    markdown = (
        "---\n"
        "title: Imported release task\n"
        "status: doing\n"
        "tags: [project:flowboard, release]\n"
        "task_type: feature\n"
        "---\n"
        "Initial imported description.\n"
    ).encode()
    imported = client.post(
        "/api/import",
        files=[
            ("files", ("release.md", markdown, "text/markdown")),
            ("files", ("notes.txt", b"not an importable task", "text/plain")),
        ],
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["created"] == 1
    assert [item["filename"] for item in imported.json()["skipped"]] == ["notes.txt"]

    task = client.get("/api/tasks").json()[0]
    updated = client.patch(
        f"/api/tasks/{task['id']}",
        json={
            "description": "Edited before export",
            "result": "Validated end-to-end",
            "status": "done",
        },
    )
    assert updated.status_code == 200, updated.text

    export = client.get("/api/export?format=md")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/markdown")
    assert b"kanban_export: true" in export.content

    deleted = client.delete(f"/api/tasks/{task['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/tasks").json() == []

    restored = client.post(
        "/api/import",
        files=[("files", ("flowboard-export.md", export.content, "text/markdown"))],
    )
    assert restored.status_code == 200, restored.text
    assert restored.json() == {"created": 1, "skipped": []}

    round_tripped = client.get("/api/tasks").json()
    assert len(round_tripped) == 1
    restored_task = round_tripped[0]
    assert restored_task["title"] == "Imported release task"
    assert restored_task["description"] == "Edited before export"
    assert restored_task["result"] == "Validated end-to-end"
    assert restored_task["status"] == "done"
    assert restored_task["tags"] == "project:flowboard, release"
    assert restored_task["task_type"] == "feature"
    assert restored_task["closed_at"]


def test_markdown_export_round_trips_multiple_tasks_with_empty_descriptions(workflow_client):
    client = workflow_client
    created = [
        client.post("/api/tasks", json={"title": title}).json()
        for title in ("First empty task", "Second empty task")
    ]
    exported = client.get("/api/export?format=md")
    assert exported.status_code == 200

    for task in created:
        assert client.delete(f"/api/tasks/{task['id']}").status_code == 204

    imported = client.post(
        "/api/import",
        files=[("files", ("empty-descriptions.md", exported.content, "text/markdown"))],
    )
    assert imported.status_code == 200, imported.text
    assert imported.json() == {"created": 2, "skipped": []}
    assert {task["title"] for task in client.get("/api/tasks").json()} == {
        "First empty task",
        "Second empty task",
    }
    assert all(task["description"] == "" for task in client.get("/api/tasks").json())


def test_failed_task_save_returns_error_and_keeps_previous_data(workflow_client):
    client = workflow_client
    created = client.post("/api/tasks", json={"title": "Keep original"})
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    with connect(settings.db_path) as connection:
        connection.execute(
            """CREATE TRIGGER reject_task_update BEFORE UPDATE ON tasks
               BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END"""
        )

    failed = client.patch(f"/api/tasks/{task_id}", json={"title": "Must not persist"})
    assert failed.status_code == 500

    persisted = client.get(f"/api/tasks/{task_id}")
    assert persisted.status_code == 200
    assert persisted.json()["title"] == "Keep original"
    assert persisted.json()["status"] == "todo"


def test_failed_import_rolls_back_tasks_created_earlier_in_the_batch(workflow_client):
    client = workflow_client
    first = client.post("/api/tasks", json={"title": "First task"}).json()
    second = client.post("/api/tasks", json={"title": "Second task"}).json()
    exported = client.get("/api/export?format=md")
    assert exported.status_code == 200
    for task_id in (first["id"], second["id"]):
        assert client.delete(f"/api/tasks/{task_id}").status_code == 204

    with connect(settings.db_path) as connection:
        connection.execute(
            """CREATE TRIGGER reject_second_task_insert BEFORE INSERT ON tasks
               WHEN NEW.title = 'Second task'
               BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END"""
        )

    failed = client.post(
        "/api/import",
        files=[("files", ("batch.md", exported.content, "text/markdown"))],
    )
    assert failed.status_code == 500
    assert client.get("/api/tasks").json() == []
