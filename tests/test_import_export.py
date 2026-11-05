from __future__ import annotations

import io
import json
import sqlite3
import zipfile

from app.config import settings


def upload_md(client, files):
    return client.post(
        "/api/import",
        files=[("files", (name, body, "text/markdown")) for name, body in files],
    )


def test_import_frontmatter_checklist_empty_unknown_status_and_duplicates(client):
    frontmatter_file = """---
title: Починить авторизацию
status: strange-status
tags: [backend, bug]
---
Короткое **описание**.
"""
    checklist = """# Work
- [ ] Добавить тесты
- [x] Настроить Ruff
not a task
- [ ] Проверить экспорт
"""
    response = upload_md(
        client,
        [
            ("auth.md", frontmatter_file.encode()),
            ("checklist.md", checklist.encode()),
            ("empty.md", b"\n  \n"),
            ("readme.txt", b"ignored"),
        ],
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["created"] == 4
    assert len(result["skipped"]) == 2
    assert {item["filename"] for item in result["skipped"]} == {"empty.md", "readme.txt"}

    tasks = client.get("/api/tasks").json()
    by_title = {task["title"]: task for task in tasks}
    assert by_title["Починить авторизацию"]["status"] == "todo"
    assert by_title["Починить авторизацию"]["tags"] == "backend"
    assert by_title["Починить авторизацию"]["task_type"] == "bug"
    assert by_title["Добавить тесты"]["status"] == "todo"
    assert by_title["Настроить Ruff"]["status"] == "done"
    assert by_title["Настроить Ruff"]["closed_at"]
    assert by_title["Проверить экспорт"]["status"] == "todo"

    # Duplicate titles are allowed: importing the same file again creates another task.
    duplicate = upload_md(client, [("auth.md", frontmatter_file.encode())])
    assert duplicate.status_code == 200
    assert duplicate.json()["created"] == 1
    duplicate_count = sum(
        task["title"] == "Починить авторизацию" for task in client.get("/api/tasks").json()
    )
    assert duplicate_count == 2


def test_import_export_markdown_round_trip(client):
    files = [
        (
            "one.md",
            b"---\ntitle: First task\nstatus: doing\ntags: [api, backend]\n---\nFirst description.",
        ),
        (
            "two.md",
            b"---\ntitle: Second task\nstatus: done\ntags: [docs]\n---\nSecond description.",
        ),
    ]
    imported = upload_md(client, files)
    assert imported.status_code == 200
    before = client.get("/api/tasks").json()
    expected = {
        (item["title"], item["status"], item["tags"], item["task_type"], item["description"])
        for item in before
    }

    exported = client.get("/api/export?format=md")
    assert exported.status_code == 200
    assert b"kanban_export: true" in exported.content

    for task in before:
        assert client.delete(f"/api/tasks/{task['id']}").status_code == 204

    response = client.post(
        "/api/import",
        files=[("files", ("tasks-export.md", exported.content, "text/markdown"))],
    )
    assert response.status_code == 200, response.text
    assert response.json()["created"] == len(before)
    assert response.json()["skipped"] == []
    after = client.get("/api/tasks").json()
    actual = {
        (item["title"], item["status"], item["tags"], item["task_type"], item["description"])
        for item in after
    }
    assert actual == expected


def test_zip_export_contains_manifest_and_all_attachments(client, tmp_path):
    task = client.post(
        "/api/tasks", json={"title": "Include files", "description": "Backup me"}
    ).json()
    uploaded = client.post(
        f"/api/tasks/{task['id']}/files",
        files=[("files", ("notes.txt", b"attached content", "text/plain"))],
    )
    assert uploaded.status_code == 201, uploaded.text

    response = client.get("/api/export?format=zip")
    assert response.status_code == 200
    archive_path = tmp_path / "backup.zip"
    archive_path.write_bytes(response.content)
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert "tasks.json" in names
        attachment_path = next(
            name for name in names if name.startswith(f"attachments/{task['id']}/")
        )
        assert archive.read(attachment_path) == b"attached content"
        manifest = json.loads(archive.read("tasks.json"))
        assert manifest["format_version"] == 1
        archived_task = next(item for item in manifest["tasks"] if item["id"] == task["id"])
        assert archived_task["attachments"][0]["filename"] == "notes.txt"
        assert archived_task["task_type"] == ""
        assert archived_task["attachments"][0]["archive_path"] == attachment_path


def test_full_zip_export_includes_only_saved_guidelines_override(client):
    client.patch("/api/task-settings", json={"require_result_to_close": True})

    without_override = client.get("/api/export?format=zip")
    assert without_override.status_code == 200
    with zipfile.ZipFile(io.BytesIO(without_override.content)) as archive:
        manifest = json.loads(archive.read("tasks.json"))
    assert manifest["format_version"] == 1
    assert "ai_task_guidelines_override" not in manifest
    assert "app_settings" not in manifest

    content = "# Пользовательский регламент\r\n\r\nТочный текст — 日本語 🧭\n"
    saved = client.put("/api/ai-task-guidelines", json={"text": content})
    assert saved.status_code == 200, saved.text

    exported = client.get("/api/export?format=zip")
    assert exported.status_code == 200
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        manifest = json.loads(archive.read("tasks.json"))

    assert manifest["format_version"] == 1
    assert manifest["ai_task_guidelines_override"] == content
    assert "app_settings" not in manifest

def test_single_task_export_uses_versioned_json_and_imports_attachments(client):
    task = client.post(
        "/api/tasks",
        json={
            "title": "Export just this task",
            "description": "A **Markdown** description.",
            "tags": "project:flowboard, needs-review",
            "task_type": "bug",
            "result": "Release published and smoke-tested.",
        },
    ).json()
    attached = client.post(
        f"/api/tasks/{task['id']}/files",
        files=[
            ("files", ("notes.txt", b"first file", "text/plain")),
            ("files", ("notes.txt", b"second file", "text/plain")),
        ],
    )
    assert attached.status_code == 201, attached.text

    response = client.get(f"/api/tasks/{task['id']}/export")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/zip")
    assert f'filename="task-{task["id"]}.zip"' in response.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {
            "task.json",
            "attachments/0001.txt",
            "attachments/0002.txt",
        }
        manifest = json.loads(archive.read("task.json"))
        assert manifest["format"] == "flowboard-task"
        assert manifest["format_version"] == 1
        assert manifest["task"] == {
            "title": "Export just this task",
            "description": "A **Markdown** description.",
            "result": "Release published and smoke-tested.",
            "status": "todo",
            "tags": ["project:flowboard", "needs-review"],
            "task_type": "bug",
            "created_at": task["created_at"],
            "updated_at": task["updated_at"],
            "closed_at": None,
        }
        assert manifest["attachments"][0]["filename"] == "notes.txt"
        assert manifest["attachments"][0]["size"] == len(b"first file")
        assert archive.read(manifest["attachments"][0]["path"]) == b"first file"

    imported = client.post(
        "/api/import", files=[("files", ("task.zip", response.content, "application/zip"))]
    )
    assert imported.status_code == 200, imported.text
    assert imported.json() == {"created": 1, "skipped": []}
    restored = next(
        item for item in client.get("/api/tasks").json()
        if item["title"] == "Export just this task" and item["id"] != task["id"]
    )
    assert restored["description"] == task["description"]
    assert restored["result"] == task["result"]
    assert restored["tags"] == task["tags"]
    assert restored["task_type"] == task["task_type"]
    detail = client.get(f"/api/tasks/{restored['id']}").json()
    assert [item["filename"] for item in detail["attachments"]] == ["notes.txt", "notes.txt"]
    assert [
        client.get(f"/api/files/{item['id']}").content for item in detail["attachments"]
    ] == [b"first file", b"second file"]


def test_single_task_import_rejects_invalid_manifest_without_creating_task(client):
    invalid_manifests = [
        {"format": "flowboard-task", "format_version": 2, "task": {"title": "Bad"}},
        {"format": "flowboard-task", "format_version": 1, "task": []},
        {
            "format": "flowboard-task",
            "format_version": 1,
            "task": {"title": "Bad", "status": "unknown"},
        },
    ]
    for index, manifest in enumerate(invalid_manifests):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("task.json", json.dumps(manifest))
        response = client.post(
            "/api/import",
            files=[("files", (f"invalid-{index}.zip", output.getvalue(), "application/zip"))],
        )
        assert response.status_code == 200
        assert response.json()["created"] == 0
        assert len(response.json()["skipped"]) == 1
    assert client.get("/api/tasks").json() == []


def test_single_task_import_rejects_unsafe_and_unlisted_archive_paths(client):
    manifest = {
        "format": "flowboard-task",
        "format_version": 1,
        "task": {"title": "Unsafe path"},
        "attachments": [],
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("task.json", json.dumps(manifest))
        archive.writestr("../outside.txt", "not safe")
    response = client.post(
        "/api/import", files=[("files", ("unsafe.zip", output.getvalue(), "application/zip"))]
    )
    assert response.status_code == 200
    assert response.json()["created"] == 0
    assert "небезопасный путь" in response.json()["skipped"][0]["reason"]
    assert client.get("/api/tasks").json() == []


def test_single_task_export_returns_404_for_unknown_task(client):
    response = client.get("/api/tasks/987654/export")
    assert response.status_code == 404


def test_invalid_export_format_returns_400(client):
    response = client.get("/api/export?format=csv")
    assert response.status_code == 400


def test_result_survives_markdown_export_and_import(client):
    created = client.post(
        "/api/tasks",
        json={
            "title": "Outcome",
            "description": "Original requirements",
            "result": "Shipped v1",
        },
    )
    assert created.status_code == 201, created.text
    exported = client.get("/api/export?format=md")
    assert exported.status_code == 200
    assert b"result: Shipped v1" in exported.content

    assert client.delete(f"/api/tasks/{created.json()['id']}").status_code == 204
    imported = upload_md(client, [("outcome.md", exported.content)])
    assert imported.status_code == 200, imported.text
    task = next(item for item in client.get("/api/tasks").json() if item["title"] == "Outcome")
    assert task["description"] == "Original requirements"
    assert task["result"] == "Shipped v1"


def test_import_accepts_description_and_result_up_to_30000_characters(client):
    description = "d" * 30_000
    result = "r" * 30_000
    markdown = (
        "---\ntitle: Long imported task\nresult: |\n  "
        + result
        + "\n---\n"
        + description
    )

    response = upload_md(client, [("long-task.md", markdown.encode("utf-8"))])

    assert response.status_code == 200, response.text
    assert response.json()["created"] == 1
    task = next(
        task for task in client.get("/api/tasks").json()
        if task["title"] == "Long imported task"
    )
    assert task["description"] == description
    assert task["result"] == result


def test_markdown_export_import_round_trip_preserves_long_task_text(client):
    description = "description " * 899 + "description"
    result = "result " * 899 + "result"
    created = client.post(
        "/api/tasks",
        json={"title": "Long Markdown round trip", "description": description, "result": result},
    )
    assert created.status_code == 201, created.text

    exported = client.get("/api/export?format=md")
    assert exported.status_code == 200
    assert client.delete(f"/api/tasks/{created.json()['id']}").status_code == 204

    imported = upload_md(client, [("long-export.md", exported.content)])
    assert imported.status_code == 200, imported.text
    assert imported.json()["created"] == 1
    restored = next(
        task for task in client.get("/api/tasks").json()
        if task["title"] == "Long Markdown round trip"
    )
    assert restored["description"] == description
    assert restored["result"] == result


def test_zip_export_fails_when_registered_attachment_is_missing(client):
    task = client.post("/api/tasks", json={"title": "Missing attachment backup"}).json()
    uploaded = client.post(
        f"/api/tasks/{task['id']}/files",
        files=[("files", ("missing.txt", b"will be removed", "text/plain"))],
    )
    assert uploaded.status_code == 201, uploaded.text

    connection = sqlite3.connect(settings.db_path)
    try:
        stored_name = connection.execute(
            "SELECT stored_name FROM attachments WHERE task_id = ?", (task["id"],)
        ).fetchone()[0]
    finally:
        connection.close()
    (settings.attachments_dir / str(task["id"]) / stored_name).unlink()

    response = client.get("/api/export?format=zip")

    assert response.status_code == 500
    assert f"задачи {task['id']}" in response.json()["detail"]
    assert "missing.txt" in response.json()["detail"]


def test_single_task_import_keeps_legacy_markdown_compatibility(client):
    legacy_markdown = '''---
title: Legacy single task
status: doing
tags:
  - project:flowboard
task_type: docs
flowboard_export_format: single-task-v1
result: Old result
---
# Legacy single task

## Описание

<!-- flowboard-description-start -->
Original description
<!-- flowboard-description-end -->

## Результат выполнения

<!-- flowboard-result-start -->
Old result
<!-- flowboard-result-end -->
'''.encode("utf-8")
    response = upload_md(client, [("legacy-task.md", legacy_markdown)])
    assert response.status_code == 200, response.text
    assert response.json() == {"created": 1, "skipped": []}
    task = client.get("/api/tasks").json()[0]
    assert task["title"] == "Legacy single task"
    assert task["status"] == "doing"
    assert task["description"] == "Original description"
    assert task["result"] == "Old result"
    assert task["task_type"] == "docs"
