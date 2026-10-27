from __future__ import annotations


def test_task_panel_redesign_uses_theme_tokens_and_grouped_tag_editor(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "/static/app.js?v=0.5.27" in html
    assert "/static/github-theme.css?v=0.2.3" in html
    assert "/static/task-editor-redesign.css?v=0.1.0" in html
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
