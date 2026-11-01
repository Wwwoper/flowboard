def test_done_column_can_collapse_at_every_viewport_width_and_keeps_titles_readable(client):
    html = client.get("/").text
    script = client.get("/static/app.js").text
    css = client.get("/static/board-workspace.css").text

    assert 'const canCollapseDone = statusTasks.length > 5;' in script
    assert 'if (!state.doneExpanded) tasksToRender = statusTasks.slice(0, 5);' in script
    assert 'doneColumnCollapseQuery' not in script
    assert 'els.toggleDone.hidden = !canCollapseDone;' in script

    assert '.board-column-done .done-card {' in css
    assert 'opacity: 1;' in css
    assert '.board-column-done .done-card .task-card-title' in css
    assert 'color: var(--ink);' in css
    assert '.board-column-done .done-card .task-card-footer' in css
    assert 'id="toggle-done" class="done-toggle"' in html
    assert '<span>Ещё</span>' not in html
    assert 'data-tooltip="Показать остальные завершённые задачи"' in html
    assert '$("span", els.toggleDone)' not in script
    assert 'els.toggleDone.dataset.tooltip = label;' in script
    assert 'column.classList.toggle("has-done-overflow", canCollapseDone);' in script
    assert 'aria-label="Показать остальные завершённые задачи"' in html
