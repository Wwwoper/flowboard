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
    assert 'id="task-result"' in html
    assert 'id="task-result-tab"' in html
    assert 'id="task-workspace-title"' not in html

    style = client.get("/static/style.css").text
    assert ".task-header-action" in style
    assert ".task-autosave-status" in style
    assert ".task-panel { padding-top: 32px; }" in style

    script = client.get("/static/app.js").text
    assert "function scheduleTaskDraftSave(delay = 180)" in script
    assert "async function saveCurrentTaskDraft()" in script
    assert "function updateTaskFocusButton()" in script
    assert "function setTaskAutosaveStatus(status, message)" in script
    assert 'els.taskTitle.addEventListener("blur", () => {' in script
    assert 'if (!titleEditorClosePending) scheduleTaskDraftSave(180);' in script
    assert 'els.taskResult.addEventListener("input", () => {' in script
    assert 'updateTaskResultIndicator();' in script
    assert 'scheduleTaskDraftSave(180);' in script
    assert 'els.taskStatus.addEventListener("change", () => {' in script
    assert 'if (state.pendingCloseTaskId && els.taskStatus.value !== "done")' in script


def test_task_description_can_be_copied_with_clipboard_api(client):
    html = client.get("/").text
    assert 'id="copy-description"' in html
    assert 'aria-label="Копировать описание"' in html
    assert 'title="Копировать описание"' in html
    tabs = html.split('class="task-workspace-tabs"', 1)[1].split('</div>', 1)[0]
    assert 'id="copy-description"' in tabs
    assert 'id="toggle-preview"' not in html
    assert 'class="task-workspace-heading"' not in html
    assert 'id="result-preview" class="markdown-preview markdown-preview-editable task-result-preview"' in html

    style = client.get("/static/style.css").text
    redesign_style = client.get("/static/task-editor-redesign.css").text
    assert ".workspace-copy-button" in redesign_style
    assert "padding: 8px 3px;" in redesign_style

    script = client.get("/static/app.js").text
    assert 'copyDescription: $("#copy-description")' in script
    assert "async function copyTaskDescription()" in script
    assert "navigator.clipboard?.writeText" in script
    assert 'await navigator.clipboard.writeText(isResult ? els.taskResult.value : els.taskDescription.value)' in script
    assert 'function updateTaskWorkspaceHeading()' in script
    assert 'els.copyDescription.setAttribute("aria-label", `Копировать ${subject}`)' in script
    assert 'togglePreview' not in script
    assert 'function setResultEditing(editing)' in script
    assert 'function requestResultMarkdownPreview()' in script
    assert (
        'els.copyDescription.addEventListener("click", () => { void copyTaskDescription(); });'
        in script
    )
    assert "function showDescriptionCopiedFeedback()" in script
    assert 'els.copyDescription.classList.add("is-copied")' in script
    assert 'els.copyDescription.title = `${subject} скопирован${subject === "Описание" ? "о" : ""}`' in script
    assert "}, 1200);" in script
    assert 'toast(`Не удалось скопировать ${isResult ? "результат" : "описание"}.' in script


def test_task_description_checklists_toggle_without_entering_edit_mode(client):
    script = client.get("/static/app.js").text
    assert "function toggleMarkdownChecklistItem(input, textarea, isPreviewVisible, refreshPreview)" in script
    assert 'els.descriptionPreview.addEventListener("change"' in script
    assert 'els.resultPreview.addEventListener("change"' in script
    assert 'input[data-task-checkbox], a, button' in script
    assert "scheduleTaskDraftSave(0)" in script


def test_task_checkboxes_use_active_theme_colors(client):
    style = client.get("/static/style.css").text
    assert ".markdown-preview input[data-task-checkbox]" in style
    assert "accent-color: var(--accent);" in style


def test_task_title_editor_closes_on_outside_pointer_after_successful_save(client):
    script = client.get("/static/app.js").text
    assert "let titleEditorClosePending = false;" in script
    assert "async function closeTaskTitleEditorOnOutsidePointerDown()" in script
    assert "if (!(await saveCurrentTaskDraft())) return;" in script
    assert "finishTitleEditing(false);" in script
    assert 'if (!els.taskTitle.hidden && !els.taskTitle.contains(target))' in script
    assert 'if (!titleEditorClosePending) scheduleTaskDraftSave(180);' in script
    assert "function finishTitleEditing(focusDisplay = true)" in script
    assert "/static/app.js?v=0.5.46" in client.get("/").text


def test_task_document_editors_close_when_pointer_moves_outside_the_active_editor(client):
    script = client.get("/static/app.js").text
    assert "function closeTaskDocumentEditorOnOutsidePointerDown(event)" in script
    assert 'state.activeTaskTab === "description" && !state.previewVisible && !els.taskDescription.contains(target)' in script
    assert 'state.activeTaskTab === "result" && !state.resultPreviewVisible && !els.taskResult.contains(target)' in script
    assert 'document.addEventListener("pointerdown", closeTaskDocumentEditorOnOutsidePointerDown)' in script
    assert "void setDescriptionEditing(false);" in script
    assert "void setResultEditing(false);" in script
    assert "/static/app.js?v=0.5.46" in client.get("/").text


def test_project_change_error_is_rendered_next_to_project_field(client):
    html = client.get("/").text
    script = client.get("/static/app.js").text
    assert 'id="task-project-error"' in html
    assert 'aria-describedby="task-project-error"' in html
    assert "Задача входит в рабочий набор этого проекта." in script
    assert "Сначала уберите её из набора, затем измените проект." in script


def test_required_result_prompt_opens_result_editor_and_retries_close_after_input(client):
    html = client.get("/").text
    script = client.get("/static/app.js").text
    assert 'id="task-result-required-hint"' in html
    assert "Перед завершением задачи добавьте результат." in html
    assert 'setTaskWorkspaceTab("result")' in script
    assert 'state.pendingCloseTaskId === task?.id && String(els.taskResult.value || "").trim()' in script
    assert "state.pendingCloseTaskId = null" in script


def test_project_change_in_workset_keeps_saved_project_selected(client):
    script = client.get("/static/app.js").text
    handler = script.split('els.taskProject.addEventListener("change", () => {', 1)[1].split('});', 1)[0]
    assert "if (task?.workset_id)" in handler
    assert "const project = projectForTask(task);" in handler
    assert 'els.taskProject.value = project ? projectTag(project) : "";' in handler
    assert 'els.taskProjectError.hidden = false;' in handler
    assert 'return;' in handler
    assert 'updateReservedTaskTag("project", els.taskProject.value);' in handler
    assert handler.index("if (task?.workset_id)") < handler.index('updateReservedTaskTag("project", els.taskProject.value)')
