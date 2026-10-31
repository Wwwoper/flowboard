from __future__ import annotations


def create_task(client, **fields):
    response = client.post("/api/tasks", json={"title": "Result requirement", **fields})
    assert response.status_code == 201, response.text
    return response.json()


def set_result_required(client, required: bool):
    response = client.patch("/api/task-settings", json={"require_result_to_close": required})
    assert response.status_code == 200, response.text
    return response.json()


def test_result_requirement_setting_defaults_off_and_can_be_toggled(client):
    assert client.get("/api/task-settings").json() == {"require_result_to_close": False}

    assert set_result_required(client, True) == {"require_result_to_close": True}
    assert client.get("/api/task-settings").json() == {"require_result_to_close": True}
    assert set_result_required(client, False) == {"require_result_to_close": False}

    null_setting = client.patch("/api/task-settings", json={"require_result_to_close": None})
    assert null_setting.status_code == 400
    assert client.patch("/api/task-settings", json={"unknown": True}).status_code == 422


def test_closing_without_result_is_allowed_when_requirement_is_disabled(client):
    task = create_task(client)

    closed = client.patch(f"/api/tasks/{task['id']}", json={"status": "done"})

    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "done"
    assert closed.json()["result"] == ""


def test_required_result_blocks_missing_empty_and_whitespace_without_changing_status(client):
    task = create_task(client)
    set_result_required(client, True)

    missing = client.patch(f"/api/tasks/{task['id']}", json={"status": "done"})
    assert missing.status_code == 409
    assert "Результат выполнения" in missing.json()["detail"]
    unchanged = client.get(f"/api/tasks/{task['id']}").json()
    assert unchanged["status"] == "todo"
    assert unchanged["result"] == ""
    assert unchanged["closed_at"] is None

    for result in ("", "   \t\n  "):
        response = client.patch(
            f"/api/tasks/{task['id']}", json={"status": "done", "result": result}
        )
        assert response.status_code == 409
        assert "Результат выполнения" in response.json()["detail"]
        current = client.get(f"/api/tasks/{task['id']}").json()
        assert current["status"] == "todo"
        assert current["result"] == ""
        assert current["closed_at"] is None


def test_rejected_close_does_not_partially_save_other_task_edits(client):
    task = create_task(client, description="Old description")
    set_result_required(client, True)

    response = client.patch(
        f"/api/tasks/{task['id']}",
        json={"status": "done", "result": "  \t ", "description": "Edited description"},
    )

    assert response.status_code == 409
    current = client.get(f"/api/tasks/{task['id']}").json()
    assert current["status"] == "todo"
    assert current["result"] == ""
    assert current["description"] == "Old description"
    assert current["closed_at"] is None


def test_nonempty_result_allows_close_in_same_status_update(client):
    task = create_task(client)
    set_result_required(client, True)

    closed = client.patch(
        f"/api/tasks/{task['id']}",
        json={"status": "done", "result": "  Verified release  "},
    )

    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "done"
    assert closed.json()["result"] == "  Verified release  "
    assert closed.json()["closed_at"]


def test_enabling_requirement_does_not_change_legacy_done_tasks_but_reclose_checks_current_result(
    client,
):
    task = create_task(client)
    originally_closed = client.patch(f"/api/tasks/{task['id']}", json={"status": "done"})
    assert originally_closed.status_code == 200
    original_closed_at = originally_closed.json()["closed_at"]

    set_result_required(client, True)
    unchanged = client.get(f"/api/tasks/{task['id']}").json()
    assert unchanged["status"] == "done"
    assert unchanged["closed_at"] == original_closed_at
    assert unchanged["result"] == ""

    reopened = client.patch(f"/api/tasks/{task['id']}", json={"status": "doing"})
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "doing"
    assert reopened.json()["result"] == ""

    blocked = client.patch(f"/api/tasks/{task['id']}", json={"status": "done"})
    assert blocked.status_code == 409
    assert client.get(f"/api/tasks/{task['id']}").json()["status"] == "doing"

    updated = client.patch(
        f"/api/tasks/{task['id']}", json={"result": "Completed after reopening"}
    )
    assert updated.status_code == 200
    reclosed = client.patch(f"/api/tasks/{task['id']}", json={"status": "done"})
    assert reclosed.status_code == 200, reclosed.text
    assert reclosed.json()["result"] == "Completed after reopening"


def test_setting_is_persisted_in_app_settings_and_ui_exposes_control(client):
    from app.config import settings
    from app.db import connect

    set_result_required(client, True)
    connection = connect(settings.db_path)
    try:
        stored = connection.execute(
            "SELECT value FROM app_settings WHERE key = 'require_result_to_close'"
        ).fetchone()[0]
    finally:
        connection.close()
    assert stored == "true"

    html = client.get("/").text
    script = client.get("/static/app.js").text
    assert 'id="require-result-to-close"' in html
    assert '"/api/task-settings"' in script
    assert "focusResultField" in script
