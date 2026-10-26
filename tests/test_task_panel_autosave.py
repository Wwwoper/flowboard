from __future__ import annotations


def test_task_panel_uses_autosave_without_a_manual_save_button(client):
    html = client.get("/").text
    assert 'id="task-form"' in html
    assert 'id="save-task"' not in html
    assert 'id="focus-task"' in html
    assert 'class="icon-button task-header-action focus-task-action"' in html
    assert 'id="task-more-toggle" class="icon-button task-header-action"' in html
    assert 'id="task-autosave-status"' in html
    assert 'class="panel-actions"' not in html
    assert 'id="export-task"' in html

    style = client.get("/static/style.css").text
    assert ".task-header-action" in style
    assert ".task-autosave-status" in style
    assert ".task-panel { padding-top: 32px; }" in style

    script = client.get("/static/app.js").text
    assert "function scheduleTaskDraftSave(delay = 180)" in script
    assert "async function saveCurrentTaskDraft()" in script
    assert "function updateTaskFocusButton()" in script
    assert "function setTaskAutosaveStatus(status, message)" in script
    assert 'els.taskTitle.addEventListener("blur", () => scheduleTaskDraftSave(180))' in script
    assert 'els.taskStatus.addEventListener("change", () => scheduleTaskDraftSave(180))' in script


def test_task_description_can_be_copied_with_clipboard_api(client):
    html = client.get("/").text
    assert 'id="copy-description"' in html
    assert 'aria-label="Копировать описание"' in html
    assert 'title="Копировать описание"' in html
    assert '<div class="description-actions">' in html
    action_group = html.split('<div class="description-actions">', 1)[1].split(
        "</div>", 1
    )[0]
    assert 'id="copy-description"' in action_group
    assert 'id="toggle-preview"' in action_group

    style = client.get("/static/style.css").text
    assert ".description-actions { display: flex; align-items: center;" in style

    script = client.get("/static/app.js").text
    assert 'copyDescription: $("#copy-description")' in script
    assert "async function copyTaskDescription()" in script
    assert "navigator.clipboard?.writeText" in script
    assert "await navigator.clipboard.writeText(els.taskDescription.value)" in script
    assert (
        'els.copyDescription.addEventListener("click", () => { void copyTaskDescription(); });'
        in script
    )
    assert 'toast("Описание скопировано")' in script
    assert 'toast("Не удалось скопировать описание.' in script


def test_task_description_checklists_toggle_without_entering_edit_mode(client):
    script = client.get("/static/app.js").text
    assert "function toggleDescriptionChecklistItem(input)" in script
    assert 'els.descriptionPreview.addEventListener("change"' in script
    assert 'input[data-task-checkbox], a, button' in script
    assert "scheduleTaskDraftSave(0)" in script
