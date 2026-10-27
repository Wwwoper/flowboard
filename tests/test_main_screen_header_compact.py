def test_main_screen_header_compacts_vertical_rhythm_without_shrinking_controls(client):
    html = client.get("/").text
    assert "/static/board-workspace.css" in html

    css = client.get("/static/board-workspace.css").text
    for fragment in (
        ".topbar { height: 64px; }",
        "padding: 17px 0 11px;",
        "font-size: clamp(25px, 2.3vw, 29px);",
        "min-height: 52px;",
        "height: 36px;",
        "padding: 12px 0 8px;",
        "@media (max-width: 1000px)",
        "flex-wrap: wrap;",
        ".search-box { flex: 1 1 100%; min-width: 0; }",
    ):
        assert fragment in css

    # The change is purely presentational; the quick-add and keyboard hooks remain.
    assert 'id="quick-add-form"' in html
    assert 'id="quick-task-type"' in html
    assert 'class="quick-add-hint"' in html
