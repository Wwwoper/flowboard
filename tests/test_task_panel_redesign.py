from __future__ import annotations


def test_task_panel_redesign_uses_theme_tokens_and_searchable_tag_popover(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "/static/app.js?v=0.5.38" in html
    assert "/static/github-theme.css?v=0.2.3" in html
    assert "/static/task-editor-redesign.css?v=0.2.5" in html
    for element_id in (
        "task-title-display",
        "panel-task-reference",
        "focus-task",
        "task-tag-list",
        "task-tag-input",
        "description-preview",
        "attachment-list",
        "task-autosave-status",
    ):
        assert f'id="{element_id}"' in html

    script = client.get("/static/app.js").text
    for fragment in (
        "task-form-content",
        "task-panel-footer",
        "function renderTaskTagEditor()",
        "function setTaskTagPopoverOpen(open, restoreFocus = false)",
        "function availableTaskTagChoicesForPopover()",
        "function moveActiveTaskTagOption(step)",
        'event.key === "ArrowDown" || event.key === "ArrowUp"',
        'event.key === "Enter"',
        'event.key === "Escape"',
        'normalizeSearch(choice.value) === normalizeSearch(tag)',
        'choices.sort((a, b) => {',
        'setTaskTagError("Введите название тега.")',
        'taskTagError.hidden = !taskTagError.textContent',
        'emptyState.textContent = "Нет вложений. Нажмите «Добавить», чтобы прикрепить файл.";',
        'els.taskTitleReference.setAttribute("aria-label", `Номер задачи ${actualId}`)',
    ):
        assert fragment in script

    styles = client.get("/static/task-editor-redesign.css").text
    for selector in (
        ".task-form-content",
        ".task-panel-footer",
        ".task-tag-chips",
        ".task-tag-popover",
        ".task-tag-options",
        ".task-tag-option.is-selected",
        ".task-tag-chip-remove",
        ".task-tag-error",
        ".task-title-reference",
        ".markdown-preview li:has(input[data-task-checkbox])",
    ):
        assert selector in styles
    assert "var(--accent)" in styles
    assert "var(--surface-soft)" in styles
    assert '.theme-select.task-type-bug .theme-select-trigger' in styles
    assert '.theme-select.task-type-feature .theme-select-trigger' in styles
    assert '.theme-select-menu .theme-select-option.task-type-docs' in styles
    assert '.attachment-list-toggle[aria-expanded="true"] svg' in styles
    assert 'width: 34px;' in styles


def test_task_editor_uses_one_tabbed_workspace_and_a_properties_sidebar(client):
    html = client.get("/").text
    assert 'id="task-description-tab"' in html
    assert 'id="task-result-tab"' in html
    assert 'role="tablist" aria-label="Рабочая область задачи"' in html
    assert 'aria-selected="true" aria-controls="task-description-panel" tabindex="0"' in html
    assert 'aria-selected="false" aria-controls="task-result-panel" tabindex="-1"' in html
    assert 'id="task-result-panel" class="task-workspace-panel task-result-panel" role="tabpanel" aria-labelledby="task-result-tab" hidden' in html
    assert 'id="task-result-indicator" class="task-result-indicator" aria-hidden="true" hidden' in html
    assert 'id="task-result" class="text-field result-field" maxlength="5000" rows="8" placeholder=' in html
    assert 'id="result-preview" class="markdown-preview markdown-preview-editable task-result-preview"' in html
    assert html.count('class="task-workspace-heading"') == 0
    tabs = html.split('class="task-workspace-tabs"', 1)[1].split('</div>', 1)[0]
    assert 'id="copy-description" class="icon-button workspace-copy-button"' in tabs
    assert 'id="toggle-preview"' not in html
    assert 'class="result-heading"' not in html
    assert '<span class="field-label">Теги</span>' in html
    assert 'id="task-tag-popover" class="task-tag-popover" hidden' in html

    script = client.get("/static/app.js").text
    for fragment in (
        'activeTaskTab: "description"',
        'function updateTaskResultIndicator()',
        'function updateTaskWorkspaceHeading()',
        'function setResultEditing(editing)',
        'function requestResultMarkdownPreview()',
        'function setTaskWorkspaceTab(tab, focus = false)',
        'function handleTaskWorkspaceTabKeydown(event)',
        'else tab = state.activeTaskTab === "description" ? "result" : "description"',
        'els.taskResultTab.addEventListener("click", () => setTaskWorkspaceTab("result"))',
        'updateTaskResultIndicator();',
        'make("aside", "task-properties-sidebar")',
        'make("div", "task-panel-header")',
    ):
        assert fragment in script

    css = client.get("/static/task-editor-redesign.css").text
    for fragment in (
        "height: 100dvh",
        ".task-workspace-tabs",
        ".workspace-copy-button",
        ".task-result-preview:empty::before",
        '.task-workspace-tab[aria-selected="true"]',
        ".task-editor-workspace",
        ".task-workspace-panel .result-field[hidden]",
        ".task-properties-sidebar",
        "grid-template-columns: minmax(0, 1fr) auto",
        "overflow-y: auto",
        "@media (max-width: 700px)",
        "@media (max-width: 420px)",
    ):
        assert fragment in css


def test_task_properties_use_compact_selects_collapsible_tags_and_attachments(client):
    html = client.get("/").text
    assert "/static/task-editor-redesign.css?v=0.2.5" in html
    assert "/static/app.js?v=0.5.38" in html

    script = client.get("/static/app.js").text
    for fragment in (
        'function updateReservedTaskTag(kind, value)',
        'function renderReservedTaskSelect(select, kind, placeholderText)',
        'renderReservedTaskSelect(els.taskType, "type", "Без типа")',
        'renderReservedTaskSelect(els.taskProject, "project", "Без проекта")',
        'function renderTaskTagEditor()',
        'function setTaskTagPopoverOpen(open, restoreFocus = false)',
        'document.addEventListener("pointerdown", (event) => {',
        'document.addEventListener("keydown", (event) => {',
        'make("button", "icon-button attachment-list-toggle")',
        'attachmentListToggle.setAttribute("aria-expanded", String(state.attachmentsExpanded))',
        'Показать все вложения',
        'function updateAttachmentDisclosure(attachments)',
        'els.attachmentList.hidden = count > 0 && !state.attachmentsExpanded',
    ):
        assert fragment in script

    html = client.get("/").text
    for fragment in (
        'id="task-type"',
        'id="task-project"',
        'id="task-tag-popover"',
        'id="task-tag-options" class="task-tag-options" role="listbox"',
        'id="task-tag-custom-toggle"',
    ):
        assert fragment in html

    css = client.get("/static/task-editor-redesign.css").text
    for fragment in (
        ".task-tag-chip-row",
        ".task-tag-popover[hidden]",
        ".task-tag-options",
        "max-height: 350px",
        "@media (max-width: 700px)",
        "position: fixed",
        ".attachment-list[hidden]",
        ".attachment-list-toggle",
    ):
        assert fragment in css
