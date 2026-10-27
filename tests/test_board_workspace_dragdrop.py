def test_dragdrop_accepts_drops_over_empty_column_area_and_keeps_list_autoscroll(client):
    dragdrop = client.get("/static/dragdrop.js").text

    assert 'this.dropSurface = element.closest(".board-column") || element;' in dragdrop
    assert 'this.dropSurface.addEventListener("dragover", this.onDragOver);' in dragdrop
    assert 'this.dropSurface.addEventListener("drop", this.onDrop);' in dragdrop
    assert 'event.target.closest(".task-list") || this.element' in dragdrop
    assert 'targetColumn !== this.dropSurface' in dragdrop
    assert "const pointerWithinList = event.clientY >= listRect.top && event.clientY <= listRect.bottom;" in dragdrop
    assert "const edgeThreshold = Math.min(56, Math.max(24, targetList.clientHeight * 0.12));" in dragdrop
    assert "targetList.scrollTop -= Math.max(4, Math.round(14 * intensity));" in dragdrop
    assert "targetList.scrollTop += Math.max(4, Math.round(14 * intensity));" in dragdrop
    assert 'this.dropSurface.removeEventListener("dragover", this.onDragOver);' in dragdrop
    assert 'this.dropSurface.removeEventListener("drop", this.onDrop);' in dragdrop

-- 
