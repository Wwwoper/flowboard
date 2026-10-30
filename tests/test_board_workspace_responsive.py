from __future__ import annotations


def test_board_workspace_uses_content_driven_desktop_columns(client):
    html = client.get("/").text
    assert '/static/board-workspace.css?v=0.1.3' in html

    css = client.get("/static/board-workspace.css").text
    assert "@media (min-width: 1181px)" in css
    assert "min-height: max(260px, calc(100dvh - 345px));" in css
    assert "height: auto;" in css
    assert "align-items: stretch;" in css
    assert "display: flex;" in css
    assert "flex-direction: column;" in css
    assert ".board-column > .task-list" in css
    assert "overflow: visible;" in css
    # The header remains separate while the list grows naturally with its cards.
    html_board = html.split('<section id="board" class="board"', 1)[1].split("</section>", 1)[0]
    assert html_board.index('class="column-header"') < html_board.index('class="task-list"')


def test_narrow_layout_uses_page_scrolling_and_wraps_toolbar_controls(client):
    html = client.get("/").text
    css = client.get("/static/board-workspace.css").text
    base_css = client.get("/static/style.css").text
    themed_css = client.get("/static/themed-controls.css").text

    assert "@media (max-width: 1180px)" in css
    assert "height: auto;" in css
    assert "max-height: none;" in css
    assert "overflow: visible;" in css
    assert "@media (max-width: 760px)" in css
    assert ".board { grid-template-columns: minmax(0, 1fr);" in base_css
    assert ".task-list, .task-list:empty { min-height: 20px; }" in base_css
    assert ".board-toolbar { flex-wrap: wrap; }" in css
    assert ".search-box { flex: 1 1 100%; min-width: 0; }" in css
    assert ".project-filter-box," in css
    assert ".tag-filter-box" in css
    assert "min-width: 0;" in themed_css
    assert "overflow-wrap: anywhere;" in base_css
    assert 'id="quick-add-form"' in html
    assert 'id="quick-task-type"' in html


def test_theme_surfaces_focus_states_and_header_hit_areas_use_shared_tokens(client):
    html = client.get("/").text
    base_css = client.get("/static/style.css").text
    board_css = client.get("/static/board-workspace.css").text
    theme_css = client.get("/static/github-theme.css").text
    manager_js = client.get("/static/theme-manager.js").text

    assert ':root[data-theme="dark"]' in base_css
    assert ':root[data-theme="dark"]' in theme_css
    assert "color-mix(in srgb, var(--gh-column, var(--surface-soft))" in board_css
    assert "border-color: color-mix(in srgb, var(--line) 42%," in board_css
    assert ".column-add:focus-visible" in base_css
    assert ".column-options-toggle:focus-visible" in base_css
    assert ".done-toggle:focus-visible" in base_css
    assert "width: 32px; height: 32px;" in base_css
    assert 'id="toggle-done" class="done-toggle"' in html
    assert 'aria-label="Показать остальные завершённые задачи"' in html
    assert "function validateTheme(value)" in manager_js
    assert '"surface-soft"' in manager_js
    assert '"gh-control-hover"' in manager_js
    assert '"gh-focus"' in theme_css or "--gh-focus:" in theme_css


def test_board_and_task_panel_keep_long_content_wrappable_at_small_viewports(client):
    css = client.get("/static/style.css").text
    board_css = client.get("/static/board-workspace.css").text
    themed_css = client.get("/static/themed-controls.css").text

    assert "overflow-wrap: anywhere;" in css
    assert "min-width: 0;" in css
    assert "min-width: 0;" in board_css
    assert "min-width: 0;" in themed_css
    assert "@media (max-width: 640px)" in css
    assert "grid-template-columns: minmax(0, 1fr);" in css
    assert ".task-panel { padding: 14px; overflow-y: auto; display: block; }" in css
    assert ".attachment-list { flex: 0 0 auto; max-height: 180px; min-height: 0; }" in css
