def test_dragdrop_routes_empty_columns_and_keeps_destination_list_autoscroll(client):
    dragdrop = client.get("/static/dragdrop.js").text

    assert "const sortablesByList = new WeakMap();" in dragdrop
    assert "function findColumnAtPoint(board, clientX, clientY)" in dragdrop
    assert 'const list = column.querySelector(".task-list");' in dragdrop
    assert 'board.addEventListener("dragover", onDragOver);' in dragdrop
    assert 'board.addEventListener("drop", onDrop);' in dragdrop
    assert "const destination = findColumnAtPoint(board, event.clientX, event.clientY);" in dragdrop
    assert "if (!destination) return;" in dragdrop
    assert "const pointerWithinList = event.clientY >= listRect.top && event.clientY <= listRect.bottom;" in dragdrop
    assert "const edgeThreshold = Math.min(56, Math.max(24, targetList.clientHeight * 0.12));" in dragdrop
    assert "targetList.scrollTop -= Math.max(4, Math.round(14 * intensity));" in dragdrop
    assert "targetList.scrollTop += Math.max(4, Math.round(14 * intensity));" in dragdrop
    assert 'event.target.closest(".board-column")' not in dragdrop
