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
    assert "/static/app.js?v=0.5.2" in html
    assert "/static/style.css?v=0.5.2" in html


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


def test_frontend_offers_undo_for_task_edits_and_attachment_changes(client):
    script = client.get("/static/app.js").text
    assert "function restoreTaskDetails(taskId, snapshot)" in script
    assert 'toast("Изменения сохранены", "success", "Отменить"' in script
    assert "function undoAttachmentUpload(attachments)" in script
    assert "function undoAttachmentRemoval(taskId, file)" in script
    assert 'toast("Вложение удалено", "success", "Восстановить"' in script
    assert '"Загрузка вложений отменена"' in script
    assert '"Вложение восстановлено"' in script


def test_task_cards_have_scan_friendly_project_type_description_and_tag_hierarchy(client):
    script = client.get("/static/app.js").text
    assert "function taskDescriptionExcerpt(description, limit = 112)" in script
    assert "const project = projectForTask(task);" in script
    assert "TASK_TYPE_LABELS = {" in script
    assert "hiddenTags.slice(0, 2)" in script
    assert "task.attachments_count" in script

    css = client.get("/static/style.css").text
    for selector in (
        ".task-card-meta",
        ".task-project-chip",
        ".task-type-chip",
        ".task-card-excerpt",
        ".tag-pill-more",
        ':root[data-density="compact"] .task-card-excerpt',
        '[data-theme="dark"] .task-card-excerpt',
    ):
        assert selector in css


def test_quick_add_can_assign_optional_task_type(client):
    html = client.get("/").text
    assert 'id="quick-task-type"' in html
    assert 'data-task-type="" aria-pressed="true"' in html
    for task_type in ("bug", "feature", "docs", "refactor"):
        assert f'data-task-type="{task_type}"' in html

    script = client.get("/static/app.js").text
    assert 'quickTaskType: ""' in script
    assert "function setQuickTaskType(type)" in script
    assert "createTask(title, status, taskType)" in script
    assert 'setQuickTaskType("")' in script
    assert (
        'const inheritedTag = state.tag && !Object.hasOwn(TASK_TYPE_LABELS, state.tag.toLowerCase())'
        in script
    )

    css = client.get("/static/style.css").text
    assert ".quick-task-type" in css
    assert '.quick-type-option[aria-pressed="true"]' in css
    assert "@media (max-width: 640px)" in css


def test_task_panel_can_upload_images_pasted_from_clipboard(client):
    html = client.get("/").text
    assert "Можно также вставить изображение: ⌘/Ctrl+V" in html

    script = client.get("/static/app.js").text
    assert "function clipboardImageExtension(mimeType)" in script
    assert "function pastedImageFiles(clipboardData)" in script
    assert 'mimeType.startsWith("image/")' in script
    assert "function handleTaskPanelPaste(event)" in script
    assert 'els.panel.addEventListener("paste", handleTaskPanelPaste)' in script
    assert "event.preventDefault();" in script

    css = client.get("/static/style.css").text
    assert ".attachment-paste-hint" in css


def test_task_panel_has_compact_layout_mouse_tag_editor_and_single_task_export(client):
    html = client.get("/").text
    for element_id in (
        "task-tag-list",
        "task-tag-input",
        "add-task-tag",
        "export-task",
        "task-description-section",
    ):
        assert f'id="{element_id}"' in html
    assert "/static/app.js?v=0.5.2" in html
    assert "/static/style.css?v=0.5.2" in html

    script = client.get("/static/app.js").text
    assert "function renderTaskTagEditor()" in script
    assert 'remove.setAttribute("aria-label", `Удалить тег ${tag}`)' in script
    assert 'els.addTaskTag.addEventListener("click", () => addTaskTags())' in script
    assert 'els.exportTask.addEventListener("click", handleTaskExport)' in script
    assert 'window.location.href = `/api/tasks/${task.id}/export`' in script
    assert "async function handleTaskExport()" in script

    css = client.get("/static/style.css").text
    assert "grid-template-columns: minmax(0, 1.08fr) minmax(245px, .92fr)" in css
    assert ".tag-chip-remove:hover" in css
    assert "overflow-y: auto" in css
    assert "@media (max-height: 720px) and (min-width: 721px)" in css
