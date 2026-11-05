from __future__ import annotations


def test_interactive_controls_share_visible_hover_and_keyboard_focus_states(client):
    html = client.get("/").text
    assert '/static/board-workspace.css?v=0.5.77' in html

    tokens = client.get("/static/tokens.css").text
    workspace = client.get("/static/board-workspace.css").text

    assert "--color-control-border: color-mix(in srgb, var(--color-text-muted) 75%, var(--color-border));" in tokens
    for selector in (
        ".button.button-quiet,",
        ".icon-button,",
        ".text-field,",
        ".theme-select-trigger,",
        ".task-card,",
        ".board-column {",
        ".button.button-quiet:hover:not(:disabled),",
        ".task-card:hover {",
        '.board-column.is-drop-target {',
    ):
        assert selector in workspace

    assert ':root[data-focus-modality="keyboard"] *:focus-visible' in workspace
    assert "outline: var(--focus-width) solid var(--color-primary) !important;" in workspace
    assert "outline-offset: var(--focus-offset) !important;" in workspace
    assert 'focusRoot.dataset.focusModality = "keyboard"' in client.get("/static/app.js").text


def test_disabled_and_invalid_controls_have_distinct_semantic_states(client):
    workspace = client.get("/static/board-workspace.css").text

    assert ":where(button, input, select, textarea, [role=\"button\"]):disabled" in workspace
    assert "opacity: var(--opacity-disabled) !important;" in workspace
    assert "cursor: not-allowed !important;" in workspace
    assert ':where(input, select, textarea, .text-field)[aria-invalid="true"]' in workspace
    assert "border-color: var(--color-error) !important;" in workspace
    assert "background-color: var(--color-error-soft) !important;" in workspace


def test_reduced_motion_and_task_card_hover_avoid_decorative_lift(client):
    workspace = client.get("/static/board-workspace.css").text

    assert ".task-card:hover {\n  background: var(--color-surface-soft);\n  box-shadow: none;\n  transform: none;" in workspace
    assert "@media (prefers-reduced-motion: reduce)" in workspace
    assert "transition-duration: 0.01ms !important;" in workspace


def test_task_project_error_is_exposed_to_assistive_technology(client):
    script = client.get("/static/app.js").text

    assert 'els.taskProject.setAttribute("aria-invalid", "false");' in script
    assert 'els.taskProject.setAttribute("aria-invalid", "true");' in script
