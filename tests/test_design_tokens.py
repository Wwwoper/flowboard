from __future__ import annotations

import re


def test_design_tokens_load_before_the_existing_stylesheet_cascade(client):
    html = client.get("/").text
    stylesheet_links = re.findall(r'<link rel="stylesheet" href="([^"]+)"', html)

    assert stylesheet_links[:6] == [
        "/static/tokens.css?v=0.5.75",
        "/static/style.css?v=0.5.75",
        "/static/github-theme.css?v=0.5.75",
        "/static/themed-controls.css?v=0.5.75",
        "/static/task-editor-redesign.css?v=0.5.75",
        "/static/board-workspace.css?v=0.5.75",
    ]
    assert client.get("/static/tokens.css").status_code == 200


def test_design_tokens_cover_existing_typography_spacing_and_geometry(client):
    css = client.get("/static/tokens.css").text

    for token in (
        "--font-body:",
        "--font-mono:",
        "--text-xs:",
        "--text-sm:",
        "--text-base:",
        "--text-input:",
        "--text-lg:",
        "--text-xl:",
        "--text-task-title:",
        "--weight-button:",
        "--line-heading:",
        "--line-body:",
        "--line-reading:",
        "--icon-sm:",
        "--icon-md:",
        "--icon-lg:",
        *(f"--space-{index}:" for index in range(1, 12)),
        "--radius-sm:",
        "--radius-control:",
        "--radius-card:",
        "--radius-dialog:",
        "--radius-pill:",
        "--border-width:",
        "--focus-width:",
        "--focus-offset:",
        "--opacity-disabled:",
        "--duration-fast:",
        "--shadow-card:",
        "--shadow-overlay:",
    ):
        assert token in css


def test_semantic_color_tokens_preserve_builtin_and_custom_theme_variables(client):
    tokens = client.get("/static/tokens.css").text
    theme_manager = client.get("/static/theme-manager.js").text
    styles = "\n".join(
        client.get(f"/static/{name}").text
        for name in (
            "style.css",
            "github-theme.css",
            "themed-controls.css",
            "task-editor-redesign.css",
            "board-workspace.css",
        )
    )

    assert "--color-background: var(--page);" in tokens
    assert "--color-primary: var(--accent);" in tokens
    assert "--color-error: var(--red);" in tokens
    assert "--color-success: var(--green);" in tokens
    assert "--color-warning: var(--orange);" in tokens
    assert "root.style.setProperty(`--${key}`, color);" in theme_manager
    assert "var(--color-background)" in styles
    assert "var(--color-primary)" in styles
    assert "var(--color-border)" in styles


def test_migrated_component_styles_use_tokens_for_repeated_values(client):
    style = client.get("/static/style.css").text
    task_editor = client.get("/static/task-editor-redesign.css").text
    workspace = client.get("/static/board-workspace.css").text

    assert "font-size: var(--text-base);" in style
    assert "border-radius: var(--radius-control);" in style
    assert "border: var(--border-width) solid var(--color-border);" in style
    assert "padding: var(--space-4) var(--space-3);" in workspace
    assert "font-size: var(--text-task-title);" in task_editor
    assert "box-shadow: var(--shadow-overlay);" in style
