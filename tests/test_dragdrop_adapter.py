from pathlib import Path


def test_native_drag_adapter_preserves_source_column_until_drop_callback():
    source = (Path(__file__).parents[1] / "app" / "static" / "dragdrop.js").read_text(encoding="utf-8")

    assert "window.__flowboardDragOrigin = this.element;" in source
    assert "const from = window.__flowboardDragOrigin || activeSortable?.element || this.origin;" in source
    assert "window.__flowboardDragOrigin = null;" in source

    drop_start = source.index("    onDrop(event, targetColumn, targetList) {")
    source_index = source.index("const from = window.__flowboardDragOrigin || activeSortable?.element || this.origin;", drop_start)
    clear_index = source.index("this.clearDragState();", drop_start)
    assert source_index < clear_index
