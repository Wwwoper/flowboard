from __future__ import annotations


def test_project_workspace_controls_are_served(client):
    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    for element_id in (
        "project-filter",
        "add-project",
        "project-dialog",
        "project-command-search",
        "focus-bar",
        "focus-task",
        "density-toggle",
        "shortcuts-dialog",
    ):
        assert f'id="{element_id}"' in html
    assert "/static/app.js?v=0.3.0" in html
    assert "/static/style.css?v=0.3.0" in html


def test_frontend_includes_project_search_undo_focus_and_density_behaviors(client):
    response = client.get("/static/app.js")
    assert response.status_code == 200
    script = response.text

    assert 'projectTag(state.project)' in script
    assert 'writeStorage("flowboard-projects", JSON.stringify(state.projects))' in script
    assert 'function normalizeSearch(value)' in script
    assert '.replace(/ё/g, "е")' in script
    assert 'function restoreDeletedTask(snapshot, files, wasFocused)' in script
    assert 'function handleFocusDone()' in script
    assert 'function applyDensity(density, persist = false)' in script
    assert 'event.key === "/"' in script
    assert 'event.key.toLocaleLowerCase("en") === "p"' in script
    dragdrop = client.get("/static/dragdrop.js")
    assert dragdrop.status_code == 200
    assert (
        'this.options.onStart({ item, from: this.element, oldIndex: this.oldIndex })'
        in dragdrop.text
    )


def test_frontend_styles_support_compact_density_focus_and_image_previews(client):
    response = client.get("/static/style.css")
    assert response.status_code == 200
    css = response.text

    assert ':root[data-density="compact"] .task-card' in css
    assert ".focus-bar" in css
    assert ".attachment-preview" in css
    assert ".project-command-option" in css
    assert '[data-theme="dark"] .focus-bar' in css
