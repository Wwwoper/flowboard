from __future__ import annotations

import io
import json
import zipfile


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
    assert by_title["Починить авторизацию"]["tags"] == "backend, bug"
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
        (item["title"], item["status"], item["tags"], item["description"]) for item in before
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
    actual = {(item["title"], item["status"], item["tags"], item["description"]) for item in after}
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
        assert archived_task["attachments"][0]["archive_path"] == attachment_path


def test_invalid_export_format_returns_400(client):
    response = client.get("/api/export?format=csv")
    assert response.status_code == 400
