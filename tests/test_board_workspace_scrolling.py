def test_board_workspace_grows_with_content_and_keeps_drag_targets(client):
    html = client.get("/").text
    assert '/static/board-workspace.css?v=0.1.3' in html

    css = client.get("/static/board-workspace.css").text
    assert "@media (min-width: 1181px)" in css
    assert "height: max(260px, calc(100dvh - 345px));" in css
    assert "align-items: stretch;" in css
    assert "height: auto;" in css
    assert "flex: 0 0 auto;" in css
    assert ".board-column.is-empty > .task-list" in css

    dragdrop = client.get("/static/dragdrop.js").text
    assert "const edgeThreshold = Math.min(56, Math.max(24, targetList.clientHeight * 0.12));" in dragdrop
    assert "targetList.scrollTop -= Math.max(4, Math.round(14 * intensity));" in dragdrop
    assert "targetList.scrollTop += Math.max(4, Math.round(14 * intensity));" in dragdrop
    # Drag routing must use the pointer's destination column, not event.target,
    # because the dragged card itself is moved in the DOM while dragging.
    assert "const sortablesByList = new WeakMap();" in dragdrop
    assert "function findColumnAtPoint(board, clientX, clientY)" in dragdrop
    assert 'board.addEventListener("dragover", onDragOver);' in dragdrop
    assert 'const list = column.querySelector(".task-list");' in dragdrop
    assert "function findColumnAtPoint(board, clientX, clientY)" in dragdrop
    assert "const destination = findColumnAtPoint(board, event.clientX, event.clientY);" in dragdrop
    assert 'event.target.closest(".board-column")' not in dragdrop



def test_board_empty_states_are_compact_and_do_not_block_dragging(client):
    html = client.get("/").text
    assert html.count("Перетащите задачу сюда") == 2
    assert 'Нет задач в ожидании' in html
    assert 'Пока нет завершённых задач.' in html

    css = client.get("/static/board-workspace.css").text
    assert ".board-column.is-empty > .task-list" in css
    assert "min-height: 8px;" in css
    assert ".board-column.is-empty > .column-empty" in css
    assert "pointer-events: none;" in css
    assert "@media (max-width: 1180px)" in css
    assert css.rstrip().endswith("}")
