from __future__ import annotations

import re


def test_modal_dialogs_have_accessible_names_and_modal_semantics(client):
    html = client.get("/").text
    dialogs = re.findall(r"<dialog\b([^>]*)>", html)

    assert dialogs
    for attributes in dialogs:
        assert re.search(r'\baria-labelledby="[^"]+"', attributes) or re.search(
            r'\baria-label="[^"]+"', attributes
        ), attributes
        assert 'aria-modal="true"' in attributes, attributes


def test_task_panel_uses_modal_dialog_semantics_and_restores_focus(client):
    html = client.get("/").text
    assert (
        '<aside id="task-panel" class="task-panel" role="dialog" '
        'aria-labelledby="task-title-display-text" aria-hidden="true" tabindex="-1">'
    ) in html

    script = client.get("/static/app.js").text
    assert 'els.panel.setAttribute("aria-modal", "true")' in script
    assert 'document.querySelector(".app-shell")?.setAttribute("inert", "")' in script
    assert 'document.querySelector(".app-shell")?.removeAttribute("inert")' in script
    assert "function restoreTaskPanelFocus()" in script
    assert "taskPanelReturnFocus = document.activeElement" in script
    assert 'els.panel.addEventListener("keydown", handleTaskPanelKeydown)' in script
    assert "event.shiftKey" in script
    assert "event.key !== \"Tab\"" in script
    assert 'if (event.key === "Escape")' in script
    assert 'else if (!els.overlay.hidden) void dismissTaskPanel();' in script
    assert 'if (event.key === "Escape" && !els.taskMoreMenu.hidden)' in script
    assert 'closeTaskMoreMenu(true);' in script
    assert 'panel.hidden = true;' in script
    assert 'toggle?.focus({ preventScroll: true });' in script


def test_settings_tabs_follow_vertical_and_task_tabs_horizontal_keyboard_models(client):
    html = client.get("/").text
    assert 'role="tablist" aria-label="Разделы настроек" aria-orientation="vertical"' in html
    assert 'role="tablist" aria-label="Рабочая область задачи" aria-orientation="horizontal"' in html

    script = client.get("/static/app.js").text
    settings_handler = script.split("$$('[data-settings-tab]').forEach", 1)[1].split(
        "els.themeToggle.addEventListener", 1
    )[0]
    assert 'window.matchMedia?.("(max-width: 640px)")' in script
    assert 'settingsTabsUseHorizontalLayout?.matches ?? window.innerWidth <= 640' in script
    assert 'orientation === "horizontal" ? "ArrowRight" : "ArrowDown"' in settings_handler
    assert 'orientation === "horizontal" ? "ArrowLeft" : "ArrowUp"' in settings_handler

    task_handler = script.split("function handleTaskWorkspaceTabKeydown(event)", 1)[1].split(
        "async function setDescriptionEditing", 1
    )[0]
    assert '["ArrowLeft", "ArrowRight", "Home", "End"]' in task_handler
    assert 'tabIndex = descriptionSelected ? 0 : -1' in script
    assert 'tabIndex = descriptionSelected ? -1 : 0' in script


def test_keyboard_focus_indicators_remain_visible_on_interactive_surfaces(client):
    css = client.get("/static/style.css").text
    redesign_css = client.get("/static/task-editor-redesign.css").text
    assert "button:focus-visible, [tabindex]:focus-visible" in css
    assert ".task-panel button:focus-visible" in redesign_css
    assert ".task-panel .task-workspace-tab:focus-visible" in redesign_css
    assert ".settings-tab:focus-visible" in css


def test_column_popovers_have_control_relationships_and_escape_returns_focus(client):
    html = client.get("/").text
    script = client.get("/static/app.js").text
    for status, label in (
        ("todo", "К выполнению"),
        ("doing", "В работе"),
        ("waiting", "Ожидает"),
        ("done", "Готово"),
    ):
        assert f'aria-controls="column-options-{status}"' in html
        assert (
            f'id="column-options-{status}" class="column-options-popover" '
            f'data-column-options-panel="{status}" role="group" '
            f'aria-label="Настройки сортировки: {label}" hidden'
        ) in html
    assert 'document.addEventListener("keydown", (event) =>' in script
    assert 'if (event.key !== "Escape") return;' in script
    assert 'toggle?.focus({ preventScroll: true });' in script
