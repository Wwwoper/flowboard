from __future__ import annotations


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

    assert client.delete(f"/api/files/{attachments[0]['id']}").status_code == 204
    assert client.get(f"/api/files/{attachments[0]['id']}").status_code == 404
    assert client.get(f"/api/tasks/{task['id']}").json()["attachments_count"] == 1


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
