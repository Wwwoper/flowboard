from __future__ import annotations


def create_task(client, title: str, project: str = "flowboard", status: str = "todo"):
    response = client.post(
        "/api/tasks",
        json={"title": title, "tags": f"project:{project}"},
    )
    assert response.status_code == 201, response.text
    task = response.json()
    if status != "todo":
        response = client.patch(f"/api/tasks/{task['id']}", json={"status": status})
        assert response.status_code == 200, response.text
        task = response.json()
    return task


def create_workset(client, name: str = "Release", project: str = "flowboard"):
    response = client.post(
        "/api/worksets", json={"project_slug": project, "name": name}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_workset_create_rename_and_empty_set_stays_active(client):
    workset = create_workset(client)

    assert workset["status"] == "active"
    assert workset["task_count"] == 0
    assert client.get("/api/worksets?project=flowboard").json()[0]["id"] == workset["id"]

    renamed = client.patch(
        f"/api/worksets/{workset['id']}", json={"name": "Release 1.0"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Release 1.0"
    events = client.get("/api/worksets/history?project=flowboard").json()
    assert [event["event_type"] for event in events[:2]] == ["renamed", "created"]


def test_workset_membership_is_unique_and_project_scoped(client):
    task = create_task(client, "Existing task")
    first = create_workset(client, "First")
    second = create_workset(client, "Second")
    other_project = create_workset(client, "Other", project="other")

    added = client.post(
        f"/api/worksets/{first['id']}/tasks", json={"task_id": task["id"]}
    )
    assert added.status_code == 200, added.text
    assert added.json()["task_count"] == 1
    assert client.get(f"/api/tasks/{task['id']}").json()["workset_id"] == first["id"]

    duplicate = client.post(
        f"/api/worksets/{second['id']}/tasks", json={"task_id": task["id"]}
    )
    assert duplicate.status_code == 409

    wrong_project_task = create_task(client, "Other project task", project="other")
    wrong_project = client.post(
        f"/api/worksets/{first['id']}/tasks", json={"task_id": wrong_project_task["id"]}
    )
    assert wrong_project.status_code == 409

    valid_other = client.post(
        f"/api/worksets/{other_project['id']}/tasks",
        json={"task_id": wrong_project_task["id"]},
    )
    assert valid_other.status_code == 200


def test_workset_completes_reactivates_and_completes_again(client):
    first = create_task(client, "First")
    second = create_task(client, "Second")
    workset = create_workset(client)
    for task in (first, second):
        response = client.post(
            f"/api/worksets/{workset['id']}/tasks", json={"task_id": task["id"]}
        )
        assert response.status_code == 200

    for task in (first, second):
        response = client.patch(f"/api/tasks/{task['id']}", json={"status": "done"})
        assert response.status_code == 200

    completed = client.get("/api/worksets?project=flowboard").json()[0]
    assert completed["status"] == "completed"
    assert completed["task_count"] == completed["done_count"] == 2
    assert completed["completed_at"]

    reopened = client.patch(f"/api/tasks/{first['id']}", json={"status": "doing"})
    assert reopened.status_code == 200
    active = client.get("/api/worksets?project=flowboard").json()[0]
    assert active["status"] == "active"
    assert active["completed_at"] is None
    assert reopened.json()["status"] == "doing"
    assert client.get(f"/api/tasks/{second['id']}").json()["status"] == "done"

    client.patch(f"/api/tasks/{first['id']}", json={"status": "done"})
    completed_again = client.get("/api/worksets?project=flowboard").json()[0]
    assert completed_again["status"] == "completed"
    events = client.get("/api/worksets/history?project=flowboard").json()
    event_types = [event["event_type"] for event in events]
    assert event_types.count("completed") == 2
    assert "reactivated" in event_types


def test_removing_last_task_deletes_workset_but_preserves_history(client):
    task = create_task(client, "Remove me")
    workset = create_workset(client)
    client.post(f"/api/worksets/{workset['id']}/tasks", json={"task_id": task["id"]})

    removed = client.delete(f"/api/worksets/{workset['id']}/tasks/{task['id']}")
    assert removed.status_code == 200
    assert removed.json() == {"deleted": True}
    assert client.get("/api/worksets?project=flowboard").json() == []
    assert client.get(f"/api/tasks/{task['id']}").status_code == 200
    events = client.get("/api/worksets/history?project=flowboard").json()
    assert [event["event_type"] for event in events[:2]] == ["deleted_empty", "task_removed"]
    assert all(event["workset_id"] is None for event in events)


def test_removing_one_of_many_tasks_keeps_set_and_task(client):
    first = create_task(client, "First")
    second = create_task(client, "Second")
    workset = create_workset(client)
    for task in (first, second):
        client.post(f"/api/worksets/{workset['id']}/tasks", json={"task_id": task["id"]})

    response = client.delete(f"/api/worksets/{workset['id']}/tasks/{first['id']}")
    assert response.status_code == 200
    assert response.json() == {"deleted": False}
    assert client.get(f"/api/tasks/{first['id']}").json()["workset_id"] is None
    remaining = client.get("/api/worksets?project=flowboard").json()[0]
    assert remaining["id"] == workset["id"]
    assert remaining["task_count"] == 1


def test_task_creation_inside_workset_and_project_change_guard(client):
    workset = create_workset(client)
    created = client.post(
        "/api/tasks",
        json={"title": "New in set", "tags": "project:flowboard", "workset_id": workset["id"]},
    )
    assert created.status_code == 201, created.text
    assert created.json()["workset_id"] == workset["id"]

    changed = client.patch(
        f"/api/tasks/{created.json()['id']}", json={"tags": "project:another"}
    )
    assert changed.status_code == 409
    assert client.get(f"/api/tasks/{created.json()['id']}").json()["workset_id"] == workset["id"]


def test_completed_workset_cannot_accept_new_tasks(client):
    task = create_task(client, "Done", status="done")
    workset = create_workset(client)
    client.post(f"/api/worksets/{workset['id']}/tasks", json={"task_id": task["id"]})
    completed = client.get("/api/worksets?project=flowboard").json()[0]
    assert completed["status"] == "completed"

    another = create_task(client, "Another")
    response = client.post(
        f"/api/worksets/{workset['id']}/tasks", json={"task_id": another["id"]}
    )
    assert response.status_code == 409


def test_deleting_task_records_history_and_removes_empty_workset(client):
    task = create_task(client, "Delete from project")
    workset = create_workset(client)
    client.post(f"/api/worksets/{workset['id']}/tasks", json={"task_id": task["id"]})

    response = client.delete(f"/api/tasks/{task['id']}")
    assert response.status_code == 204
    events = client.get("/api/worksets/history?project=flowboard").json()
    assert [event["event_type"] for event in events[:2]] == ["deleted_empty", "task_deleted"]
    assert events[1]["task_title"] == "Delete from project"
    assert events[1]["task_id"] is None


def test_deleting_one_task_from_project_keeps_other_workset_members(client):
    deleted = create_task(client, "Deleted member")
    remaining = create_task(client, "Remaining member")
    workset = create_workset(client)
    for task in (deleted, remaining):
        client.post(
            f"/api/worksets/{workset['id']}/tasks", json={"task_id": task["id"]}
        )

    response = client.delete(f"/api/tasks/{deleted['id']}")
    assert response.status_code == 204
    listed = client.get("/api/worksets?project=flowboard").json()
    assert len(listed) == 1
    assert listed[0]["id"] == workset["id"]
    assert listed[0]["task_count"] == 1
    assert client.get(f"/api/tasks/{remaining['id']}").json()["workset_id"] == workset["id"]
    events = client.get("/api/worksets/history?project=flowboard").json()
    deleted_event = next(event for event in events if event["event_type"] == "task_deleted")
    assert deleted_event["task_title"] == "Deleted member"


def test_task_can_be_transferred_directly_between_worksets(client):
    task = create_task(client, "Move between sets")
    first = create_workset(client, "First")
    second = create_workset(client, "Second")
    client.post(f"/api/worksets/{first['id']}/tasks", json={"task_id": task["id"]})

    direct_move = client.patch(
        f"/api/tasks/{task['id']}", json={"workset_id": second["id"]}
    )
    assert direct_move.status_code == 200, direct_move.text
    assert direct_move.json()["workset_id"] == second["id"]
    assert client.get(f"/api/tasks/{task['id']}").json()["workset_id"] == second["id"]

    listed = client.get("/api/worksets?project=flowboard").json()
    assert len(listed) == 1
    assert listed[0]["id"] == second["id"]
    assert listed[0]["task_count"] == 1
    events = client.get("/api/worksets/history?project=flowboard").json()
    assert any(
        event["event_type"] == "task_removed" and event["workset_name"] == "First"
        for event in events
    )
    assert any(
        event["event_type"] == "task_added" and event["workset_name"] == "Second"
        for event in events
    )


def test_failed_move_keeps_original_workset_membership(client):
    task = create_task(client, "Keep current membership")
    original = create_workset(client, "Original")
    client.post(
        f"/api/worksets/{original['id']}/tasks", json={"task_id": task["id"]}
    )
    completed_task = create_task(client, "Already done", status="done")
    completed = create_workset(client, "Completed")
    client.post(
        f"/api/worksets/{completed['id']}/tasks",
        json={"task_id": completed_task["id"]},
    )

    response = client.patch(
        f"/api/tasks/{task['id']}", json={"workset_id": completed["id"]}
    )
    assert response.status_code == 409
    assert client.get(f"/api/tasks/{task['id']}").json()["workset_id"] == original["id"]
    worksets = client.get("/api/worksets?project=flowboard").json()
    assert {item["id"] for item in worksets} == {original["id"], completed["id"]}


def test_removing_unfinished_member_can_complete_remaining_set(client):
    done_task = create_task(client, "Already done", status="done")
    open_task = create_task(client, "Still open")
    workset = create_workset(client)
    for task in (open_task, done_task):
        client.post(
            f"/api/worksets/{workset['id']}/tasks", json={"task_id": task["id"]}
        )

    active = client.get("/api/worksets?project=flowboard").json()[0]
    assert active["status"] == "active"
    removed = client.delete(
        f"/api/worksets/{workset['id']}/tasks/{open_task['id']}"
    )
    assert removed.status_code == 200
    completed = client.get("/api/worksets?project=flowboard").json()[0]
    assert completed["status"] == "completed"
    assert completed["task_count"] == completed["done_count"] == 1
    assert client.get(f"/api/tasks/{open_task['id']}").status_code == 200
