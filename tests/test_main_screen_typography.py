from __future__ import annotations

import re


def test_main_screen_uses_shared_typography_and_spacing_tokens(client):
    html = client.get("/").text
    css = client.get("/static/style.css").text
    workspace_css = client.get("/static/board-workspace.css").text
    tokens_css = client.get("/static/tokens.css").text

    for token, value in (
        ("--type-page-title:", "clamp(1.625rem, 2.4vw, 1.875rem)"),
        ("--type-column-title:", "var(--text-sm)"),
        ("--type-task-title:", "var(--text-base)"),
        ("--type-preview:", "var(--text-xs)"),
        ("--type-meta:", "0.6875rem"),
        ("--type-hint:", "var(--text-xs)"),
    ):
        assert token in css
        assert f"{token} {value};" in css

    for token in ("--line-height-heading:", "--line-height-body:", "--line-height-meta:"):
        assert token in css
    for token in ("--space-1:", "--space-2:", "--space-3:", "--space-4:", "--space-5:", "--space-11:"):
        assert token in tokens_css

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
    assert 'href="/static/tokens.css?v=0.5.77"' in html
    assert 'href="/static/style.css?v=0.5.77"' in html
    assert 'href="/static/board-workspace.css?v=0.5.77"' in html
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


def _contrast_ratio(foreground: str, background: str) -> float:
    def luminance(color: str) -> float:
        channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
            for value in channels
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_secondary_text_token_meets_wcag_aa_on_default_light_surfaces(client):
    css = client.get("/static/style.css").text
    root = css.split(":root {", 1)[1].split("}", 1)[0]
    muted = re.search(r"--muted:\s*(#[0-9a-fA-F]{6})", root)
    page = re.search(r"--page:\s*(#[0-9a-fA-F]{6})", root)
    surface = re.search(r"--surface:\s*(#[0-9a-fA-F]{6})", root)
    assert muted and page and surface
    assert _contrast_ratio(muted.group(1), page.group(1)) >= 4.5
    assert _contrast_ratio(muted.group(1), surface.group(1)) >= 4.5
    dark = css.split(':root[data-theme="dark"] {', 1)[1].split("}", 1)[0]
    dark_muted = re.search(r"--muted:\s*(#[0-9a-fA-F]{6})", dark)
    dark_surface = re.search(r"--surface:\s*(#[0-9a-fA-F]{6})", dark)
    dark_soft_surface = re.search(r"--surface-soft:\s*(#[0-9a-fA-F]{6})", dark)
    assert dark_muted and dark_surface and dark_soft_surface
    assert _contrast_ratio(dark_muted.group(1), dark_surface.group(1)) >= 4.5
    assert _contrast_ratio(dark_muted.group(1), dark_soft_surface.group(1)) >= 4.5
