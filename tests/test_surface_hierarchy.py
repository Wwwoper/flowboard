from __future__ import annotations
import re


def test_board_surface_hierarchy_uses_theme_tokens_for_surfaces_and_states(client):
    response = client.get("/static/board-workspace.css")
    assert response.status_code == 200
    css = response.text
    marker = "/* Surface hierarchy: quiet columns"
    assert marker in css
    surface_rules = css[css.index(marker):]

    for fragment in (
        ":root .board-column {",
        "var(--gh-column, var(--surface-soft))",
        "border-color: color-mix(in srgb, var(--line) 42%,",
        ":root .board-column.is-drop-target",
        "background: color-mix(in srgb, var(--accent-pale) 64%,",
        ".wip-warning { display: inline-flex; align-items: center; flex: 0 0 auto;",
        "var(--gh-yellow-bg)",
        ":root .task-card:hover",
        "var(--line-strong)",
        ":root .task-card.dragging",
        "opacity: .4;",
        ":root .task-card.is-focused",
        "var(--gh-focus",
        ":root .board-column-done .task-card",
    ):
        assert fragment in surface_rules

    # New hierarchy rules should remain palette-driven rather than hard-coding colors.
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\s*\(", surface_rules)
