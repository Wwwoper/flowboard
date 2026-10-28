from __future__ import annotations


def test_primary_actions_follow_the_active_theme_accent(client):
    html = client.get("/").text
    assert '/static/github-theme.css?v=0.2.3' in html
    assert '/static/themed-controls.css?v=0.1.11' in html

    css = client.get("/static/github-theme.css").text
    assert ".button-primary {" in css
    assert "color: var(--accent-ink);" in css
    assert "background: var(--accent);" in css
    assert "background: var(--accent-dark);" in css
    assert "background: var(--gh-primary);" not in css


def test_task_type_colors_use_the_same_semantic_tokens_in_picker_cards_and_archive(client):
    picker_css = client.get("/static/themed-controls.css").text
    theme_css = client.get("/static/github-theme.css").text

    pairs = {
        "bug": ("gh-red-fg", "gh-red-bg"),
        "feature": ("gh-green-fg", "gh-green-bg"),
        "docs": ("gh-yellow-fg", "gh-yellow-bg"),
        "refactor": ("gh-purple-fg", "gh-purple-bg"),
    }
    for task_type, (foreground, background) in pairs.items():
        assert f'.quick-type-option[data-task-type="{task_type}"]' in picker_css
        assert f"color: var(--{foreground}" in picker_css
        assert f"background: var(--{background}" in picker_css
        assert f".task-type-{task_type} {{ color: var(--{foreground})" in theme_css
        assert f".archive-chip.task-type-{task_type} {{ color: var(--{foreground})" in theme_css


def test_status_and_project_colors_are_theme_tokens(client):
    theme_css = client.get("/static/github-theme.css").text
    manager = client.get("/static/theme-manager.js").text
    script = client.get("/static/app.js").text

    for status in ("todo", "doing", "waiting", "done"):
        assert f"--gh-marker-{status}:" in theme_css
        assert f".marker-{status} {{ background: var(--gh-marker-{status})" in theme_css

    for index in range(1, 7):
        key = f"project-accent-{index}"
        assert f"--{key}:" in theme_css
        assert f'"{key}"' in manager
    assert 'getComputedStyle(document.documentElement).getPropertyValue(key)' in script
    assert "const PROJECT_ACCENTS = [" not in script


def test_custom_theme_schema_accepts_paired_accent_and_project_tokens(client):
    manager = client.get("/static/theme-manager.js").text
    for token in (
        '"accent-ink"',
        '"project-accent-1"',
        '"project-accent-6"',
        '"overlay"',
        '"gh-red-fg"',
        '"gh-red-bg"',
        '"gh-marker-todo"',
        '"gh-marker-done"',
    ):
        assert token in manager


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


def test_builtin_task_type_color_pairs_keep_text_contrast_in_light_and_dark_themes(client):
    import re

    css = client.get("/static/github-theme.css").text
    palettes = {
        "light": css.split(":root[data-theme=\"dark\"]", 1)[0],
        "dark": css.split(":root[data-theme=\"dark\"]", 1)[1].split("/* Global surfaces", 1)[0],
    }
    pairs = {
        "bug": ("gh-red-fg", "gh-red-bg"),
        "feature": ("gh-green-fg", "gh-green-bg"),
        "docs": ("gh-yellow-fg", "gh-yellow-bg"),
        "refactor": ("gh-purple-fg", "gh-purple-bg"),
        "default": ("gh-blue-fg", "gh-blue-bg"),
    }
    for palette in palettes.values():
        for foreground_token, background_token in pairs.values():
            foreground = re.search(rf"--{foreground_token}:\s*(#[0-9a-fA-F]{{6}})", palette)
            background = re.search(rf"--{background_token}:\s*(#[0-9a-fA-F]{{6}})", palette)
            assert foreground and background
            assert _contrast_ratio(foreground.group(1), background.group(1)) >= 4.5

        accent_ink = re.search(r"--accent-ink:\s*(#[0-9a-fA-F]{6})", palette)
        assert accent_ink
        for accent_token in ("accent", "accent-dark"):
            accent = re.search(rf"--{accent_token}:\s*(#[0-9a-fA-F]{{6}})", palette)
            assert accent
            assert _contrast_ratio(accent_ink.group(1), accent.group(1)) >= 4.5
