def test_toast_notifications_follow_theme_and_can_be_dismissed(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "/static/app.js?v=0.5.41" in response.text
    assert "/static/style.css?v=0.5.23" in response.text

    script = client.get("/static/app.js").text
    css = client.get("/static/style.css").text

    assert 'make("button", "toast-close", "×")' in script
    assert 'setAttribute("aria-label", "Закрыть уведомление")' in script
    assert 'node.setAttribute("role", type === "error" ? "alert" : "status")' in script
    assert 'background: var(--surface)' in css
    assert 'border-left-color: var(--red)' in css
    assert '.toast-region .toast-close:hover' in css


def test_toast_position_can_be_selected_and_persisted_in_appearance_settings(client):
    html = client.get("/").text
    script = client.get("/static/app.js").text
    css = client.get("/static/style.css").text

    assert "/static/app.js?v=0.5.41" in html
    assert "/static/style.css?v=0.5.23" in html
    assert '<div class="settings-section toast-position-settings">' in html
    assert 'id="toast-position-options" class="toast-position-options"' in html
    for position, label in (
        ("top-left", "Сверху слева"),
        ("top-center", "Сверху по центру"),
        ("top-right", "Сверху справа"),
        ("bottom-left", "Снизу слева"),
        ("bottom-center", "Снизу по центру"),
        ("bottom-right", "Снизу справа"),
    ):
        assert f'name="toast-position" value="{position}"' in html
        assert label in html
        assert f'.toast-region[data-position="{position}"]' in css

    assert 'const DEFAULT_TOAST_POSITION = "top-right"' in script
    assert 'const TOAST_POSITION_STORAGE_KEY = "flowboard-toast-position"' in script
    assert 'applyToastPosition(readStorage(TOAST_POSITION_STORAGE_KEY, DEFAULT_TOAST_POSITION))' in script
    assert 'writeStorage(TOAST_POSITION_STORAGE_KEY, position)' in script
    assert 'if (selected) selected.checked = true' in script
    assert 'toast-region[data-position^="bottom"] .toast' in css
