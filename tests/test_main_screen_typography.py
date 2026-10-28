from __future__ import annotations

import re


def test_main_screen_uses_shared_typography_and_spacing_tokens(client):
    html = client.get("/").text
    css = client.get("/static/style.css").text
    workspace_css = client.get("/static/board-workspace.css").text

    for token, value in (
        ("--type-page-title:", "clamp(1.625rem, 2.4vw, 1.875rem)"),
        ("--type-column-title:", "0.8125rem"),
        ("--type-task-title:", "0.875rem"),
        ("--type-preview:", "0.75rem"),
        ("--type-meta:", "0.6875rem"),
        ("--type-hint:", "0.75rem"),
    ):
        assert token in css
        assert f"{token} {value};" in css

    for token in (
        "--line-height-heading:",
        "--line-height-body:",
        "--line-height-meta:",
        "--space-1:",
        "--space-2:",
        "--space-3:",
        "--space-4:",
        "--space-5:",
    ):
        assert token in css

    for rule in (
        ".page-heading h1 {\n  font-size: var(--type-page-title);",
        ".column-header h2 {\n  font-size: var(--type-column-title);",
        ".task-card-title,\n:root[data-density=\"compact\"] .task-card-title {\n  font-size: var(--type-task-title);",
        ".task-card-excerpt {\n  margin-top: var(--space-3);\n  font-size: var(--type-preview);",
        ".task-project-chip,\n.task-type-chip,\n.tag-pill,\n.task-card-footer,\n.board-stats,\n.filter-summary {\n  font-size: var(--type-meta);",
        ".task-card-meta { margin-top: var(--space-4);",
    ):
        assert rule in workspace_css

    # Completed cards no longer receive smaller type or tighter line spacing.
    assert "font-size: 9px;" not in workspace_css
    assert ".board-column-done .done-card .task-card-excerpt {\n  margin-top: 5px;" not in workspace_css

    # Font sizes scale with the root font size; long words and titles can wrap.
    assert "clamp(1.625rem, 2.4vw, 1.875rem)" in css
    assert "overflow-wrap: anywhere;" in css
    assert 'href="/static/style.css?v=0.5.24"' in html
    assert 'href="/static/board-workspace.css?v=0.1.2"' in html
    assert ".toolbar-menu-trigger" in css
    assert ".settings-open-button::after,\n.topbar-import-button::after { display: none; }" in css


def test_main_screen_typography_tokens_are_not_overridden_by_small_viewport_rules(client):
    workspace_css = client.get("/static/board-workspace.css").text
    compact_title_rules = re.findall(
        r"(?:^|\n)\s*(?:[^{}]*\s)?\.task-card-title\s*\{([^{}]*)\}",
        workspace_css,
    )
    assert any("font-size: var(--type-task-title);" in rule for rule in compact_title_rules)
    compact_rule = workspace_css.rsplit(
        ':root[data-density="compact"] .task-card-title {', 1
    )[1].split('}', 1)[0]
    assert "font-size: var(--type-task-title);" in compact_rule
