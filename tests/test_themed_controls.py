from __future__ import annotations


def test_theme_aware_controls_assets_are_loaded(client):
    html = client.get("/").text
    assert '/static/themed-controls.css?v=0.1.1' in html
    assert '/static/themed-selects.js?v=0.1.0' in html

    css_response = client.get("/static/themed-controls.css")
    assert css_response.status_code == 200
    css = css_response.text
    for fragment in (
        '.quick-type-option[data-task-type="bug"]',
        '.quick-type-option[data-task-type="feature"]',
        '.quick-type-option[data-task-type="docs"]',
        '.quick-type-option[data-task-type="refactor"]',
        'color: var(--gh-red-fg, #a44e58)',
        'color: var(--gh-green-fg, #267c69)',
        'color: var(--gh-yellow-fg, #8b672b)',
        'color: var(--gh-purple-fg, #7654a3)',
        ".theme-select-trigger",
        ".theme-select-menu[hidden]",
        '.theme-select-option[aria-selected="true"]',
        "@media (min-width: 641px) and (max-width: 1000px)",
        ".board-toolbar > .search-box",
        "flex: 1 1 100%;",
        ".board-toolbar .filter-box .theme-select-trigger",
        "border-color: transparent;",
        ".task-title-row .task-header-action",
        "#focus-task::before",
        "#task-more-toggle::before",
        "#close-panel::after",
        ".attachment-heading .attachment-icon-button",
    ):
        assert fragment in css

    script_response = client.get("/static/themed-selects.js")
    assert script_response.status_code == 200
    script = script_response.text
    for fragment in (
        '#project-filter',
        '#tag-filter',
        '[data-column-filter]',
        '[data-column-sort]',
        '#task-status',
        'setAttribute("role", "listbox")',
        'setAttribute("role", "option")',
        'event.key === "ArrowDown"',
        'new Event("change", { bubbles: true })',
        'new MutationObserver',
    ):
        assert fragment in script
