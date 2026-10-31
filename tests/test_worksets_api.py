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
    events = client.get("/api/worksets/history?project=flowboard").json()["events"]
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
    events = client.get("/api/worksets/history?project=flowboard").json()["events"]
    event_types = [event["event_type"] for event in events]
    assert event_types.count("completed") == 2
    latest_completed = next(event for event in events if event["event_type"] == "completed")
    assert latest_completed["task_count"] == latest_completed["done_count"] == 2
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
    events = client.get("/api/worksets/history?project=flowboard").json()["events"]
    assert [event["event_type"] for event in events[:2]] == ["deleted_empty", "task_removed"]
    assert all(event["workset_id"] == workset["id"] for event in events)


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
    events = client.get("/api/worksets/history?project=flowboard").json()["events"]
    assert [event["event_type"] for event in events[:2]] == ["deleted_empty", "task_deleted"]
    assert events[1]["task_title"] == "Delete from project"
    assert events[1]["task_id"] == task["id"]
    assert events[1]["task_exists"] is False


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
    events = client.get("/api/worksets/history?project=flowboard").json()["events"]
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
    events = client.get("/api/worksets/history?project=flowboard").json()["events"]
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

def test_history_reconstructs_membership_and_preserves_removed_task(client):
    task = create_task(client, "First membership")
    other = create_task(client, "Keep set alive")
    workset = create_workset(client, "History")
    client.post(f"/api/worksets/{workset['id']}/tasks", json={"task_id": task["id"]})
    client.post(f"/api/worksets/{workset['id']}/tasks", json={"task_id": other["id"]})
    client.delete(f"/api/worksets/{workset['id']}/tasks/{task['id']}")
    client.post(f"/api/worksets/{workset['id']}/tasks", json={"task_id": task["id"]})

    history = client.get("/api/worksets/history?project=flowboard").json()
    item = next(item for item in history["worksets"] if item["id"] == workset["id"])
    assert item["status"] == "active"
    assert item["added_count"] == 3
    assert item["removed_count"] == 1
    assert {member["task_id"] for member in item["members"]} == {task["id"], other["id"]}
    assert len(item["removed_tasks"]) == 1
    assert item["removed_tasks"][0]["task_title"] == "First membership"
    assert item["removed_tasks"][0]["exists"] is True


def test_completed_workset_rejects_membership_removal_without_event(client):
    task = create_task(client, "Completed member", status="done")
    workset = create_workset(client, "Locked")
    client.post(f"/api/worksets/{workset['id']}/tasks", json={"task_id": task["id"]})
    before = client.get("/api/worksets/history?project=flowboard").json()["events"]

    response = client.delete(f"/api/worksets/{workset['id']}/tasks/{task['id']}")

    assert response.status_code == 409
    after = client.get("/api/worksets/history?project=flowboard").json()["events"]
    assert after == before
    assert client.get(f"/api/tasks/{task['id']}").json()["workset_id"] == workset["id"]


def test_completed_workset_rejects_transfer_without_event(client):
    task = create_task(client, "Completed member", status="done")
    target_task = create_task(client, "Target member")
    workset = create_workset(client, "Locked")
    target = create_workset(client, "Target")
    client.post(f"/api/worksets/{workset['id']}/tasks", json={"task_id": task["id"]})
    client.post(f"/api/worksets/{target['id']}/tasks", json={"task_id": target_task["id"]})
    before = client.get("/api/worksets/history?project=flowboard").json()["events"]

    response = client.patch(f"/api/tasks/{task['id']}", json={"workset_id": target["id"]})

    assert response.status_code == 409
    after = client.get("/api/worksets/history?project=flowboard").json()["events"]
    assert after == before
    assert client.get(f"/api/tasks/{task['id']}").json()["workset_id"] == workset["id"]


def test_reopening_task_records_task_and_workset_events_with_unchanged_membership(client):
    first = create_task(client, "First")
    second = create_task(client, "Second")
    workset = create_workset(client, "Release")
    for task in (first, second):
        client.post(f"/api/worksets/{workset['id']}/tasks", json={"task_id": task["id"]})
    for task in (first, second):
        client.patch(f"/api/tasks/{task['id']}", json={"status": "done"})

    reopened = client.patch(f"/api/tasks/{first['id']}", json={"status": "doing"})
    assert reopened.status_code == 200
    history = client.get("/api/worksets/history?project=flowboard").json()
    types = [event["event_type"] for event in history["events"]]
    assert types[:2] == ["reactivated", "task_reopened"]
    reopen_event = history["events"][1]
    assert reopen_event["task_id"] == first["id"]
    assert reopen_event["task_status"] == "doing"
    item = next(item for item in history["worksets"] if item["id"] == workset["id"])
    assert item["status"] == "active"
    assert {member["task_id"] for member in item["members"]} == {first["id"], second["id"]}
    completed_event = next(
        event for event in history["events"] if event["event_type"] == "task_completed"
    )
    assert completed_event["task_status"] == "done"
    assert completed_event["task_closed_at"]


def test_completed_history_keeps_deleted_task_id_and_completion_snapshot(client):
    task = create_task(client, "Deleted after completion")
    other = create_task(client, "Still in completed set")
    workset = create_workset(client, "Snapshot")
    for member in (task, other):
        client.post(f"/api/worksets/{workset['id']}/tasks", json={"task_id": member["id"]})
    for member in (task, other):
        client.patch(f"/api/tasks/{member['id']}", json={"status": "done"})
    client.delete(f"/api/tasks/{task['id']}")

    history = client.get("/api/worksets/history?project=flowboard").json()
    item = next(item for item in history["worksets"] if item["id"] == workset["id"])
    assert item["status"] == "completed"
    assert item["task_count"] == item["done_count"] == 2
    assert item["deleted_count"] == 1
    deleted_member = next(member for member in item["members"] if member["task_id"] == task["id"])
    assert deleted_member["exists"] is False
    deleted_event = next(
        event for event in history["events"] if event["event_type"] == "task_deleted"
    )
    assert deleted_event["task_id"] == task["id"]
    assert deleted_event["task_exists"] is False


def test_history_paginates_events_in_stable_order(client):
    workset = create_workset(client, "Paged")
    for index in range(3):
        client.patch(f"/api/worksets/{workset['id']}", json={"name": f"Paged {index}"})

    first = client.get("/api/worksets/history?project=flowboard&limit=2&offset=0").json()
    second = client.get("/api/worksets/history?project=flowboard&limit=2&offset=2").json()
    assert len(first["events"]) == 2
    assert first["has_more"] is True
    assert first["next_offset"] == 2
    assert len(second["events"]) == 2
    assert second["has_more"] is False
    assert [event["id"] for event in first["events"] + second["events"]] == [4, 3, 2, 1]


def test_history_distinguishes_project_deletion_from_membership_removal(client):
    deleted = create_task(client, "Removed from project")
    first = create_task(client, "First remaining")
    second = create_task(client, "Second remaining")
    workset = create_workset(client, "Deletion reasons")
    for task in (deleted, first, second):
        client.post(f"/api/worksets/{workset['id']}/tasks", json={"task_id": task["id"]})
    client.delete(f"/api/tasks/{deleted['id']}")
    for task in (first, second):
        client.patch(f"/api/tasks/{task['id']}", json={"status": "done"})

    history = client.get("/api/worksets/history?project=flowboard").json()
    item = next(item for item in history["worksets"] if item["id"] == workset["id"])
    assert item["status"] == "completed"
    assert item["task_count"] == 2
    assert item["removed_count"] == 0
    assert item["deleted_count"] == 1
    assert item["deleted_tasks"][0]["task_id"] == deleted["id"]
    assert item["deleted_tasks"][0]["removal_reason"] == "deleted"


def test_legacy_completed_events_show_done_status_when_snapshots_are_missing(client):
    from app.config import settings
    from app.db import connect

    task = create_task(client, "Legacy completed", status="done")
    workset = create_workset(client, "Legacy snapshot")
    client.post(f"/api/worksets/{workset['id']}/tasks", json={"task_id": task["id"]})

    connection = connect(settings.db_path)
    try:
        connection.execute(
            """
            UPDATE workset_events
            SET task_status = NULL, task_closed_at = NULL,
                task_count = NULL, done_count = NULL
            WHERE workset_id = ?
            """,
            (workset["id"],),
        )
        connection.commit()
    finally:
        connection.close()

    history = client.get("/api/worksets/history?project=flowboard").json()
    item = next(item for item in history["worksets"] if item["id"] == workset["id"])
    assert item["status"] == "completed"
    assert item["task_count"] == item["done_count"] == 1
    assert item["members"][0]["status"] == "done"



def test_history_returns_explicit_empty_collections_for_new_project(client):
    response = client.get("/api/worksets/history?project=empty-project")

    assert response.status_code == 200
    assert response.json() == {
        "worksets": [],
        "events": [],
        "has_more": False,
        "next_offset": None,
    }
