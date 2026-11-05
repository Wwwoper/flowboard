from __future__ import annotations

from pathlib import Path


def create_task(client, title: str):
    response = client.post("/api/tasks", json={"title": title})
    assert response.status_code == 201, response.text
    return response.json()


def test_dragged_task_move_is_persisted(client):
    first = create_task(client, "First")
    second = create_task(client, "Second")

    response = client.patch(
        f"/api/tasks/{second['id']}",
        json={"status": "doing", "position": 0},
    )

    assert response.status_code == 200, response.text
    moved = response.json()
    assert (moved["status"], moved["position"]) == ("doing", 0)
    tasks = client.get("/api/tasks").json()
    assert [task["id"] for task in tasks if task["status"] == "todo"] == [first["id"]]
    assert [task["id"] for task in tasks if task["status"] == "doing"] == [second["id"]]


def test_failed_dragged_task_move_keeps_the_last_saved_position(client):
    task = create_task(client, "Keep position")

    response = client.patch(f"/api/tasks/{task['id']}", json={"status": "unknown"})

    assert response.status_code == 422
    saved = client.get(f"/api/tasks/{task['id']}").json()
    assert (saved["status"], saved["position"]) == ("todo", 0)


def test_sequential_dragged_task_moves_leave_one_final_card(client):
    task = create_task(client, "Move more than once")
    other = create_task(client, "Other task")

    first_move = client.patch(
        f"/api/tasks/{task['id']}", json={"status": "doing", "position": 0}
    )
    second_move = client.patch(
        f"/api/tasks/{task['id']}", json={"status": "waiting", "position": 1}
    )

    assert first_move.status_code == 200
    assert second_move.status_code == 200
    tasks = client.get("/api/tasks").json()
    moved = [item for item in tasks if item["id"] == task["id"]]
    assert len(moved) == 1
    assert (moved[0]["status"], moved[0]["position"]) == ("waiting", 1)
    assert {item["id"] for item in tasks} == {task["id"], other["id"]}


def test_dragdrop_saves_moves_serially_and_rolls_back_on_failure(client):
    script = (Path(__file__).parents[1] / "app" / "static" / "app.js").read_text(
        encoding="utf-8"
    )
    queue_function = script.split("async function flushTaskMoveQueue()", 1)[1].split(
        "function queueTaskMove(move)", 1
    )[0]
    load_function = script.split("async function loadTasks()", 1)[1].split(
        "function populateArchiveFilters()", 1
    )[0]

    assert "while (state.dragSaveQueue.length)" in queue_function
    assert 'await api(`/api/tasks/${move.taskId}`' in queue_function
    assert "state.tasks = state.tasks.map(" in queue_function
    assert "state.dragSaveQueue.length = 0;" in queue_function
    assert "await loadWorksets();" in queue_function
    assert "renderBoard();" in queue_function
    assert "Не удалось сохранить перемещение" in queue_function
    assert "state.dragSaveQueue.push(move);" in script
    assert "await state.dragSavePromise" in load_function
    assert "dragRevision !== state.dragRevision" in load_function
    assert "Promise.all" not in queue_function
