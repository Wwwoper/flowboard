def test_done_column_collapses_only_on_narrow_layouts_and_keeps_titles_readable(client):
    html = client.get("/").text
    script = client.get("/static/app.js").text
    css = client.get("/static/board-workspace.css").text

    assert 'const doneColumnCollapseQuery = window.matchMedia("(max-width: 1180px)");' in script
    assert 'status === "done" && doneColumnCollapseQuery.matches && !state.doneExpanded' in script
    assert 'const canCollapseDone = doneColumnCollapseQuery.matches && statusTasks.length > 5;' in script
    assert 'doneColumnCollapseQuery.addEventListener("change", () => renderBoard());' in script

    assert '.board-column-done .done-card {' in css
    assert 'opacity: 1;' in css
    assert '.board-column-done .done-card .task-card-title' in css
    assert 'color: var(--ink);' in css
    assert '.board-column-done .done-card .task-card-footer' in css
    assert 'id="toggle-done" class="done-toggle"' in html
    assert 'aria-label="Показать остальные завершённые задачи"' in html
