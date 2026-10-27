from __future__ import annotations


def create_task(client, **fields):
    response = client.post("/api/tasks", json={"title": "Task result lifecycle", **fields})
    assert response.status_code == 201, response.text
    return response.json()


def test_result_is_separate_from_description_and_survives_read_refresh(client):
    created = create_task(
        client,
        description="Original requirements",
        result="  Completed release\n\nVerified deployment  ",
    )

    listed = client.get("/api/tasks")
    assert listed.status_code == 200
    summary = next(task for task in listed.json() if task["id"] == created["id"])
    assert summary["description"] == "Original requirements"
    assert summary["result"] == "  Completed release\n\nVerified deployment  "

    detail = client.get(f"/api/tasks/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["description"] == "Original requirements"
    assert detail.json()["result"] == "  Completed release\n\nVerified deployment  "
    assert "Completed release" not in detail.json()["description_html"]


def test_result_can_be_empty_cleared_and_updated_without_changing_description(client):
    created = create_task(client, description="Keep this description", result="Initial result")
    task_id = created["id"]

    cleared = client.patch(f"/api/tasks/{task_id}", json={"result": ""})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["result"] == ""
    assert cleared.json()["description"] == "Keep this description"

    updated = client.patch(f"/api/tasks/{task_id}", json={"result": "Final result"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["result"] == "Final result"
    assert updated.json()["description"] == "Keep this description"


def test_result_survives_close_reopen_and_second_close(client):
    created = create_task(client, description="Requirements", result="Implemented and verified")
    task_id = created["id"]

    first_close = client.patch(f"/api/tasks/{task_id}", json={"status": "done"})
    assert first_close.status_code == 200, first_close.text
    first_closed_at = first_close.json()["closed_at"]
    assert first_closed_at
    assert first_close.json()["result"] == "Implemented and verified"

    repeated_close = client.patch(f"/api/tasks/{task_id}", json={"status": "done"})
    assert repeated_close.status_code == 200, repeated_close.text
    assert repeated_close.json()["closed_at"] == first_closed_at
    assert repeated_close.json()["result"] == "Implemented and verified"

    reopened = client.patch(f"/api/tasks/{task_id}", json={"status": "doing"})
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["closed_at"] is None
    assert reopened.json()["result"] == "Implemented and verified"

    second_close = client.patch(f"/api/tasks/{task_id}", json={"status": "done"})
    assert second_close.status_code == 200, second_close.text
    assert second_close.json()["closed_at"]
    assert second_close.json()["result"] == "Implemented and verified"

    refreshed = client.get(f"/api/tasks/{task_id}")
    assert refreshed.status_code == 200
    assert refreshed.json()["status"] == "done"
    assert refreshed.json()["result"] == "Implemented and verified"
    assert refreshed.json()["description"] == "Requirements"


def test_missing_result_remains_optional_when_creating_legacy_style_task(client):
    created = create_task(client, description="Old task without result")
    assert created["result"] == ""

    closed = client.patch(f"/api/tasks/{created['id']}", json={"status": "done"})
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "done"
    assert closed.json()["result"] == ""
