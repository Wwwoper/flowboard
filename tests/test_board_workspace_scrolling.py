def test_board_workspace_uses_desktop_list_scrolling_and_drag_autoscroll(client):
    html = client.get("/").text
    assert '/static/board-workspace.css?v=0.1.0' in html

    css = client.get("/static/board-workspace.css").text
    assert "@media (min-width: 1181px)" in css
    assert "height: max(260px, calc(100dvh - 345px));" in css
    assert "align-items: stretch;" in css
    assert "overflow-y: auto;" in css
    assert "overscroll-behavior-y: contain;" in css
    assert ".board-column.is-empty > .task-list" in css

    dragdrop = client.get("/static/dragdrop.js").text
    assert "const edgeThreshold = Math.min(56, Math.max(24, targetList.clientHeight * 0.12));" in dragdrop
    assert "targetList.scrollTop -= Math.max(4, Math.round(14 * intensity));" in dragdrop
    assert "targetList.scrollTop += Math.max(4, Math.round(14 * intensity));" in dragdrop
