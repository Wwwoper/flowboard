def test_toast_notifications_follow_theme_and_can_be_dismissed(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "/static/app.js?v=0.5.36" in response.text
    assert "/static/style.css?v=0.5.19" in response.text

    script = client.get("/static/app.js").text
    css = client.get("/static/style.css").text

    assert 'make("button", "toast-close", "×")' in script
    assert 'setAttribute("aria-label", "Закрыть уведомление")' in script
    assert 'node.setAttribute("role", type === "error" ? "alert" : "status")' in script
    assert 'background: var(--surface)' in css
    assert 'border-left-color: var(--red)' in css
    assert '.toast-region .toast-close:hover' in css
