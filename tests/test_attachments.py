from __future__ import annotations

from pathlib import Path

import pytest


def create_task(client, title="Attachment task"):
    return client.post("/api/tasks", json={"title": title}).json()


def test_upload_download_delete_and_path_traversal_filename(client):
    task = create_task(client)
    response = client.post(
        f"/api/tasks/{task['id']}/files",
        files=[
            ("files", ("../secret.txt", b"secret bytes", "text/plain")),
            ("files", ("image.PNG", b"image bytes", "image/png")),
        ],
    )
    assert response.status_code == 201, response.text
    attachments = response.json()
    assert len(attachments) == 2
    assert attachments[0]["filename"] == "secret.txt"
    assert ".." not in attachments[0]["filename"]

    detail = client.get(f"/api/tasks/{task['id']}").json()
    assert detail["attachments_count"] == 2
    assert len(detail["attachments"]) == 2

    download = client.get(f"/api/files/{attachments[0]['id']}")
    assert download.status_code == 200
    assert download.content == b"secret bytes"
    assert "secret.txt" in download.headers.get("content-disposition", "")

    from app.config import settings

    attachment_dir = settings.attachments_dir / str(task["id"])
    assert attachment_dir.is_dir()
    assert client.delete(f"/api/files/{attachments[0]['id']}").status_code == 204
    assert client.get(f"/api/files/{attachments[0]['id']}").status_code == 404
    assert client.get(f"/api/tasks/{task['id']}").json()["attachments_count"] == 1
    assert attachment_dir.is_dir()
    assert len(list(attachment_dir.iterdir())) == 1

    assert client.delete(f"/api/files/{attachments[1]['id']}").status_code == 204
    assert client.get(f"/api/tasks/{task['id']}").json()["attachments_count"] == 0
    assert not attachment_dir.exists()


def test_oversized_attachment_returns_413_and_task_remains(client):
    task = create_task(client)
    oversized = b"a" * (1024 * 1024 + 1)
    response = client.post(
        f"/api/tasks/{task['id']}/files",
        files=[("files", ("large.bin", oversized, "application/octet-stream"))],
    )
    assert response.status_code == 413
    assert client.get(f"/api/tasks/{task['id']}").json()["attachments_count"] == 0


def test_delete_task_removes_attachment_directory(client):
    task = create_task(client)
    response = client.post(
        f"/api/tasks/{task['id']}/files",
        files=[("files", ("remove-me.txt", b"x", "text/plain"))],
    )
    assert response.status_code == 201
    from app.config import settings

    attachment_dir = settings.attachments_dir / str(task["id"])
    assert attachment_dir.is_dir()
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 204
    assert not attachment_dir.exists()


def test_delete_attachment_ignores_empty_directory_cleanup_errors(client, monkeypatch):
    task = create_task(client)
    uploaded = client.post(
        f"/api/tasks/{task['id']}/files",
        files=[("files", ("keep-empty-dir.txt", b"x", "text/plain"))],
    )
    assert uploaded.status_code == 201
    from app.config import settings

    attachment_dir = settings.attachments_dir / str(task["id"])
    original_rmdir = Path.rmdir

    def fail_rmdir(path):
        if path == attachment_dir:
            raise PermissionError("simulated directory cleanup failure")
        return original_rmdir(path)

    monkeypatch.setattr(Path, "rmdir", fail_rmdir)

    assert client.delete(f"/api/files/{uploaded.json()[0]['id']}").status_code == 204
    assert attachment_dir.is_dir()
    assert list(attachment_dir.iterdir()) == []


def test_failed_attachment_upload_removes_partial_file_and_empty_directory(client, monkeypatch):
    task = create_task(client)
    from app.config import settings

    attachment_dir = settings.attachments_dir / str(task["id"])
    original_write_bytes = Path.write_bytes

    def write_partial_then_fail(path, data):
        if path.parent == attachment_dir:
            original_write_bytes(path, data[:1])
            raise OSError("simulated write failure")
        return original_write_bytes(path, data)

    monkeypatch.setattr(Path, "write_bytes", write_partial_then_fail)

    with pytest.raises(OSError, match="simulated write failure"):
        client.post(
            f"/api/tasks/{task['id']}/files",
            files=[("files", ("partial.txt", b"partial payload", "text/plain"))],
        )

    assert client.get(f"/api/tasks/{task['id']}").json()["attachments_count"] == 0
    assert not attachment_dir.exists()
