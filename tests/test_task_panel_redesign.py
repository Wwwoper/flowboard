from __future__ import annotations


def test_task_panel_redesign_uses_theme_tokens_and_grouped_tag_editor(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "/static/app.js?v=0.5.29" in html
    assert "/static/github-theme.css?v=0.2.3" in html
    assert "/static/task-editor-redesign.css?v=0.2.0" in html
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
        "function renderGroupedTaskTagEditor()",
        "function addTaskTagsWithValidation(",
        'setTaskTagError("Введите название тега.")',
        'setTaskTagError(`Тег «${duplicate}» уже добавлен.`)',
        "Проект выбирается в группе «Проект»",
        "Нажмите «Добавить» или перетащите файлы сюда.",
        'els.taskTitleReference.setAttribute("aria-label", `Номер задачи ${actualId}`)',
    ):
        assert fragment in script

    styles = client.get("/static/task-editor-redesign.css").text
    for selector in (
        ".task-form-content",
        ".task-panel-footer",
        ".tag-choice-groups",
        ".tag-choice-group-heading",
        '.tag-choice[aria-pressed="true"]::before',
        ".task-tag-error",
        ".task-title-reference",
        ".markdown-preview li:has(input[data-task-checkbox])",
    ):
        assert selector in styles
    assert "var(--accent)" in styles
    assert "var(--surface-soft)" in styles


def test_task_editor_uses_one_tabbed_workspace_and_a_properties_sidebar(client):
    html = client.get("/").text
    assert 'id="task-description-tab"' in html
    assert 'id="task-result-tab"' in html
    assert 'role="tablist" aria-label="Рабочая область задачи"' in html
    assert 'aria-selected="true" aria-controls="task-description-panel" tabindex="0"' in html
    assert 'aria-selected="false" aria-controls="task-result-panel" tabindex="-1"' in html
    assert 'id="task-result-panel" class="task-workspace-panel task-result-panel" role="tabpanel" aria-labelledby="task-result-tab" hidden' in html
    assert 'id="task-result-indicator" class="task-result-indicator" aria-hidden="true" hidden' in html
    assert 'id="task-result" class="text-field result-field" maxlength="5000" rows="8"' in html

    script = client.get("/static/app.js").text
    for fragment in (
        'activeTaskTab: "description"',
        'function updateTaskResultIndicator()',
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
        '.task-workspace-tab[aria-selected="true"]',
        ".task-editor-workspace",
        ".task-properties-sidebar",
        "grid-template-columns: minmax(0, 1fr) auto",
        "overflow-y: auto",
        "@media (max-width: 700px)",
        "@media (max-width: 420px)",
    ):
        assert fragment in css
