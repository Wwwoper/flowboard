from __future__ import annotations


def test_theme_aware_controls_assets_are_loaded(client):
    html = client.get("/").text
    assert '/static/themed-controls.css?v=0.5.66' in html
    assert '/static/themed-selects.js?v=0.1.10' in html

    css_response = client.get("/static/themed-controls.css")
    assert css_response.status_code == 200
    css = css_response.text
    for fragment in (
        '.quick-type-option[data-task-type="bug"]',
        '.quick-type-option[data-task-type="feature"]',
        '.quick-type-option[data-task-type="docs"]',
        '.quick-type-option[data-task-type="refactor"]',
        'color: var(--gh-red-fg, var(--color-error))',
        'color: var(--gh-green-fg, var(--color-success))',
        'color: var(--gh-yellow-fg, var(--color-warning))',
        'color: var(--gh-purple-fg, var(--color-primary-hover))',
        ".theme-select-trigger",
        ".settings-dialog .theme-manager-select-wrapper .theme-select-trigger",
        ".theme-manager-select-wrapper {",
        ".theme-select-menu[hidden]",
        '.theme-select-option[aria-selected="true"]',
        ".toolbar-main-group > .search-box",
        "flex: 1 1 100%;",
        ".board-toolbar .filter-box .theme-select-trigger",
        "border-color: transparent;",
        ".task-title-row .task-header-action",
        ".task-title-row {",
        "align-items: center;",
        ".task-title-row .task-title-reference",
        "height: 36px;",
        "border: 1.5px solid var(--color-border-strong) !important;",
        ".task-title-row #focus-task[aria-pressed=\"true\"]",
        ".task-title-row .task-action-icon",
        "width: 20px !important;",
        ".attachment-heading .attachment-icon-button",
    ):
        assert fragment in css

    script_response = client.get("/static/themed-selects.js")
    assert script_response.status_code == 200
    script = script_response.text
    for fragment in (
        '#project-filter',
        '[data-column-sort]',
        '#task-status',
        '#task-type',
        '#task-project',
        '#saved-themes-select',
        'setAttribute("role", "listbox")',
        'setAttribute("role", "option")',
        'event.key === "ArrowDown"',
        'new Event("change", { bubbles: true })',
        'new MutationObserver',
        'const dialog = select.closest("dialog");',
        '(dialog || document.body).appendChild(menu);',
        'instance.menu.style.position = "absolute";',
        'modal dialog is rendered in the browser',
        'instance.wrapper.classList.remove("task-type-bug", "task-type-feature", "task-type-docs", "task-type-refactor")',
        'item.classList.add(`task-type-${option.value}`)',
    ):
        assert fragment in script
    assert "#tag-filter" not in script
    assert "[data-column-filter]" not in script
    assert 'wrapper.classList.add("theme-manager-select-wrapper")' in script
