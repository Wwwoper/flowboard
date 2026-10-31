from __future__ import annotations


def create_task(client, title="Test task"):
    response = client.post("/api/tasks", json={"title": title})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_list_patch_and_delete_task(client):
    created = create_task(client, "  Write tests  ")
    assert created["title"] == "Write tests"
    assert created["status"] == "todo"
    assert created["position"] == 0
    assert created["closed_at"] is None

    response = client.get("/api/tasks")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [created["id"]]

    response = client.patch(
        f"/api/tasks/{created['id']}",
        json={"status": "done", "description": "**Finished**", "tags": "python, tests"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "done"
    assert response.json()["closed_at"]
    assert response.json()["tags"] == "python, tests"

    detail = client.get(f"/api/tasks/{created['id']}").json()
    assert "<strong>Finished</strong>" in detail["description_html"]

    response = client.patch(f"/api/tasks/{created['id']}", json={"status": "doing"})
    assert response.status_code == 200
    assert response.json()["closed_at"] is None

    response = client.delete(f"/api/tasks/{created['id']}")
    assert response.status_code == 204
    assert client.get(f"/api/tasks/{created['id']}").status_code == 404


def test_task_validation_and_unknown_status(client):
    assert client.post("/api/tasks", json={"title": "  "}).status_code == 422
    assert client.post("/api/tasks", json={"title": "x" * 201}).status_code == 422
    created = create_task(client)
    assert (
        client.patch(f"/api/tasks/{created['id']}", json={"status": "blocked"}).status_code == 422
    )
    assert client.patch(f"/api/tasks/{created['id']}", json={"status": None}).status_code == 400
    assert client.patch(f"/api/tasks/{created['id']}", json={"unknown": "field"}).status_code == 422


def test_task_order_and_status_are_persisted(client):
    first = create_task(client, "first")
    second = create_task(client, "second")
    response = client.patch(f"/api/tasks/{second['id']}", json={"status": "doing", "position": 0})
    assert response.status_code == 200
    third = create_task(client, "third")
    response = client.patch(f"/api/tasks/{third['id']}", json={"position": -1})
    assert response.status_code == 200

    tasks = client.get("/api/tasks").json()
    todo_ids = [task["id"] for task in tasks if task["status"] == "todo"]
    assert todo_ids == [third["id"], first["id"]]
    doing = next(task for task in tasks if task["id"] == second["id"])
    assert doing["status"] == "doing"
    assert doing["position"] == 0


def test_safe_markdown_preview_escapes_html(client):
    response = client.post(
        "/api/preview-markdown",
        json={"text": "Hello **world**\n\n<script>alert('xss')</script>"},
    )
    assert response.status_code == 200
    html = response.json()["html"]
    assert "<strong>world</strong>" in html
    assert "<script>" not in html
    assert "alert('xss')" not in html or "&lt;script&gt;" in html


def test_safe_markdown_preview_renders_interactive_checklists_safely(client):
    response = client.post(
        "/api/preview-markdown",
        json={
            "text": (
                "## Checklist\n- [x] Complete **first**\n- [ ] Pending\n"
                "  - [ ] Nested\n\n```markdown\n- [ ] code example\n```\n\n"
                '<input type="checkbox" checked>\n<script>alert(\'xss\')</script>'
            )
        },
    )
    assert response.status_code == 200
    html = response.json()["html"]
    assert html.count("<input") == 3
    assert 'data-task-checkbox="1"' in html
    assert 'data-task-checkbox="2"' in html
    assert 'data-task-checkbox="3"' in html
    assert "checked" in html
    assert "<strong>first</strong>" in html
    assert '<input type="checkbox" checked>' not in html
    assert "<script>" not in html


def test_duplicate_checklist_labels_keep_distinct_source_line_indexes(client):
    response = client.post(
        "/api/preview-markdown",
        json={"text": "- [ ] Same label\n\n## Another list\n- [ ] Same label"},
    )
    assert response.status_code == 200
    html = response.json()["html"]
    assert 'data-task-checkbox="0"' in html
    assert 'data-task-checkbox="3"' in html
    assert html.count("Same label") == 2


def test_task_api_responses_disable_browser_caching(client):
    created = create_task(client, "Fresh task")

    list_response = client.get("/api/tasks")
    detail_response = client.get(f"/api/tasks/{created['id']}")

    assert list_response.headers["cache-control"] == "no-store"
    assert detail_response.headers["cache-control"] == "no-store"


def test_index_revalidates_html_and_references_versioned_assets(client):
    response = client.get("/")

    assert response.headers["cache-control"] == "no-cache"
    assert "/static/app.js?v=0.5.45" in response.text


def test_index_exposes_accessible_theme_toggle(client):
    response = client.get("/")

    assert 'id="theme-toggle"' in response.text
    assert 'aria-pressed="false"' in response.text
    assert 'id="theme-toggle-icon"' in response.text


def test_dark_theme_styles_and_theme_persistence_hook(client):
    css_response = client.get("/static/style.css")
    js_response = client.get("/static/app.js")
    html_response = client.get("/")

    assert css_response.status_code == 200
    assert ':root[data-theme="dark"]' in css_response.text
    assert '--page: #0c101a' in css_response.text
    assert js_response.status_code == 200
    assert 'localStorage.setItem("flowboard-theme", normalizedTheme)' in js_response.text
    assert 'localStorage.getItem("flowboard-theme")' in html_response.text


def test_task_result_is_separate_persisted_and_optional(client):
    created_response = client.post(
        "/api/tasks",
        json={"title": "Result task", "description": "Requirements", "result": ""},
    )
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()
    assert created["result"] == ""

    updated = client.patch(
        f"/api/tasks/{created['id']}",
        json={"result": "Implemented independently", "description": "Updated requirements"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["result"] == "Implemented independently"
    assert updated.json()["description"] == "Updated requirements"

    closed = client.patch(f"/api/tasks/{created['id']}", json={"status": "done"})
    assert closed.status_code == 200
    assert closed.json()["result"] == "Implemented independently"

    detail = client.get(f"/api/tasks/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["result"] == "Implemented independently"
    assert detail.json()["description"] == "Updated requirements"

    cleared = client.patch(f"/api/tasks/{created['id']}", json={"result": None})
    assert cleared.status_code == 200
    assert cleared.json()["result"] == ""


def test_task_result_validation_and_old_records_default_to_empty(client):
    created = create_task(client, "Legacy-compatible task")
    assert created["result"] == ""
    assert client.patch(
        f"/api/tasks/{created['id']}", json={"result": "x" * 5001}
    ).status_code == 422
