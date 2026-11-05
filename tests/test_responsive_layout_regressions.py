from __future__ import annotations


def test_responsive_stylesheets_are_versioned_together(client):
    html = client.get("/").text
    assert 'href="/static/style.css?v=0.5.69"' in html
    assert 'href="/static/board-workspace.css?v=0.5.69"' in html
    assert 'href="/static/task-editor-redesign.css?v=0.5.69"' in html


def test_mobile_board_filters_and_actions_can_shrink_without_clipping(client):
    css = client.get("/static/board-workspace.css").text
    mobile_rules = css.split("/* Responsive guardrails:", 1)[1]

    assert "@media (max-width: 760px)" in mobile_rules
    assert ".project-toolbar-group,\n  .workset-toolbar-group" in mobile_rules
    assert "min-width: 0;" in mobile_rules
    assert ".toolbar-actions-group" in mobile_rules
    assert "flex-wrap: wrap;" in mobile_rules


def test_mobile_task_editor_uses_one_scroll_surface_and_keeps_header_actions(client):
    css = client.get("/static/task-editor-redesign.css").text
    mobile_rules = css.split("/* On phones, keep the editor", 1)[1]

    assert "@media (max-width: 700px)" in mobile_rules
    assert ".task-properties-sidebar" in mobile_rules
    assert "max-height: none;" in mobile_rules
    assert "overflow: visible;" in mobile_rules
    assert "env(safe-area-inset-bottom, 0px)" in mobile_rules
    assert "grid-template-columns: minmax(0, 1fr) repeat(3, 32px);" in mobile_rules


def test_mobile_settings_dialog_stays_within_viewport_and_keeps_tab_navigation(client):
    css = client.get("/static/style.css").text
    mobile_rules = css.split("/* Keep the settings dialog inside", 1)[1]

    assert "max-width: calc(100vw - 16px);" in mobile_rules
    assert "max-height: calc(100dvh - 16px);" in mobile_rules
    assert ".settings-tabs" in mobile_rules
    assert "overflow-x: auto;" in mobile_rules
    assert ".settings-panels" in mobile_rules
    assert "overflow-y: auto;" in mobile_rules
    assert "@media (max-width: 380px)" in mobile_rules
