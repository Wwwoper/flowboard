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


def test_single_task_export_contains_markdown_and_sibling_attachments(client):
    task = client.post(
        "/api/tasks",
        json={
            "title": "Export just this task",
            "description": "A **Markdown** description.",
            "tags": "project:flowboard, bug, needs-review",
            "result": "Release published and smoke-tested.",
        },
    ).json()
    attached = client.post(
        f"/api/tasks/{task['id']}/files",
        files=[
            ("files", ("notes.txt", b"first file", "text/plain")),
            ("files", ("notes.txt", b"second file", "text/plain")),
            ("files", (f"task-{task['id']}.md", b"name collision", "text/markdown")),
        ],
    )
    assert attached.status_code == 201, attached.text
    other = client.post("/api/tasks", json={"title": "Keep out of archive"}).json()
    client.post(
        f"/api/tasks/{other['id']}/files",
        files=[("files", ("secret.txt", b"different task", "text/plain"))],
    )

    response = client.get(f"/api/tasks/{task['id']}/export")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/zip")
    assert f'filename="task-{task["id"]}.zip"' in response.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        markdown_name = f"task-{task['id']}.md"
        assert markdown_name in names
        assert "notes.txt" in names
        assert "notes (2).txt" in names
        assert f"task-{task['id']} (2).md" in names
        assert "secret.txt" not in names
        assert len(names) == 4
        markdown = archive.read(markdown_name).decode("utf-8")
        from app.frontmatter_compat import loads

        post = loads(markdown)
        assert post.metadata["title"] == "Export just this task"
        assert post.metadata["status"] == "todo"
        assert post.metadata["tags"] == ["project:flowboard", "bug", "needs-review"]
        assert post.metadata["attachments"] == [
            "notes.txt",
            "notes (2).txt",
            f"task-{task['id']} (2).md",
        ]
        assert post.metadata["flowboard_export_format"] == "single-task-v1"
        assert post.metadata["result"] == "Release published and smoke-tested."
        assert post.content.startswith("# Export just this task\n")
        assert "## Описание" in post.content
        assert "A **Markdown** description." in post.content
        assert "<!-- flowboard-result-start -->" in post.content
        assert "Release published and smoke-tested." in post.content
        assert "## Вложения" in post.content
        assert "- [notes.txt](notes.txt)" in post.content
        from app.importer import parse_markdown_file

        imported, skipped = parse_markdown_file(markdown_name, markdown)
        assert not skipped
        assert len(imported) == 1
        assert imported[0].description == "A **Markdown** description."
        assert imported[0].result == "Release published and smoke-tested."
        assert archive.read("notes.txt") == b"first file"
        assert archive.read("notes (2).txt") == b"second file"
        assert archive.read(f"task-{task['id']} (2).md") == b"name collision"


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
