from __future__ import annotations



def test_board_workspace_fills_available_desktop_height_with_internal_scrolling(client):
    html = client.get("/").text
    assert '/static/board-workspace.css?v=0.1.14' in html

    css = client.get("/static/board-workspace.css").text
    assert "@media (min-width: 1181px)" in css
    assert "height: 100dvh;" in css
    assert "min-height: 100dvh;" not in css
    assert ".app-shell > main" in css
    assert "flex: 1 1 auto;" in css
    assert "height: auto;" in css
    assert "min-height: 260px;" in css
    assert ".page-footer" in css
    assert "margin-top: auto;" in css
    assert "height: max(260px, calc(100dvh - 300px));" not in css
    assert "min-height: 0;" in css
    assert "align-items: stretch;" in css
    assert "display: flex;" in css
    assert "flex-direction: column;" in css
    assert ".board-column > .task-list" in css
    assert "overflow-y: auto;" in css
    assert "overscroll-behavior-y: contain;" in css
    # The header stays visible while the task list scrolls inside the column.
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
    assert ".toolbar-main-group > .search-box" in css
    assert "flex: 1 1 100%;" in css
    assert ".project-filter-box {" in css
    assert 'id="task-filter-menu"' in html
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
    assert "width: 40px;" in board_css
    assert "height: 40px;" in board_css
    assert ".done-toggle {" in board_css
    assert "min-height: 40px;" in board_css
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


def test_board_toolbar_uses_two_groups_with_actions_aligned_to_the_end(client):
    html = client.get("/").text
    css = client.get("/static/board-workspace.css").text

    assert 'class="toolbar-main-group"' in html
    assert 'class="toolbar-filters-group" aria-label="Фильтры доски"' in html
    assert 'class="toolbar-actions-group"' in html
    assert html.index('class="toolbar-main-group"') < html.index('class="toolbar-actions-group"')
    assert ".toolbar-main-group {" in css
    assert "margin-left: auto;" in css
    assert ".project-toolbar-group { flex: 0 0 220px; min-width: 0; }" in css
    assert ".project-filter-box .theme-select { flex: 1 1 auto; width: 100%; max-width: none; min-width: 0; }" in css
    assert ".workset-toolbar-group:has(> .workset-filter-box[hidden])" in css


def test_toolbar_search_expands_and_filters_wrap_as_a_single_group(client):
    html = client.get("/").text
    board_css = client.get("/static/board-workspace.css").text
    themed_css = client.get("/static/themed-controls.css").text

    assert "/static/board-workspace.css?v=0.1.14" in html
    assert ".toolbar-main-group {" in board_css
    assert "flex: 1 1 640px;" in board_css
    assert "flex-wrap: nowrap;" in board_css
    assert "max-width: none;" in board_css
    assert ".toolbar-filters-group {" in board_css
    assert "max-width: none;" in themed_css
    assert "@media (min-width: 641px) and (max-width: 1000px)" not in themed_css
    assert ".board-toolbar > .search-box" not in themed_css


def test_selected_workset_checkmark_is_on_the_right_of_its_existing_icon(client):
    css = client.get("/static/board-workspace.css").text
    selected_selector = ".workset-filter-menu .theme-select-option[aria-selected=\"true\"]"
    selected_rule = css.split(f"{selected_selector} {{", 1)[1]
    checkmark_rule = selected_rule.split(f"{selected_selector}::before {{", 1)[1]

    assert "padding-right: 28px;" in selected_rule.split("}", 1)[0]
    assert "padding-left: 28px;" not in selected_rule.split("}", 1)[0]
    assert "right: 10px;" in checkmark_rule.split("}", 1)[0]
    assert "left: 10px;" not in checkmark_rule.split("}", 1)[0]
