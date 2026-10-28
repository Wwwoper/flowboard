from __future__ import annotations


def test_remaining_browser_confirmations_use_the_shared_themed_dialog(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    for fragment in (
        'id="confirm-action-dialog"',
        'class="app-modal confirm-action-dialog"',
        'aria-labelledby="confirm-action-heading"',
        'aria-describedby="confirm-action-message"',
        'id="confirm-action-heading"',
        'id="confirm-action-message"',
        'id="close-confirm-action"',
        'id="cancel-confirm-action"',
        'id="accept-confirm-action"',
    ):
        assert fragment in html

    script = client.get("/static/app.js").text
    assert "window.confirm(" not in script
    assert "window.alert(" not in script
    assert "window.prompt(" not in script
    for fragment in (
        "function requestActionConfirmation({ title, message, confirmLabel = \"Подтвердить\", danger = false })",
        'title: "Архивировать все завершённые задачи?"',
        'message: `Удалить вложение «${filename}»?`',
        'message: `Удалить тему «${name}» из библиотеки? Это действие нельзя отменить.`',
        'confirmActionDialog.addEventListener("cancel", (event) => {',
        'acceptConfirmActionButton.classList.toggle("confirm-action-danger", danger);',
    ):
        assert fragment in script

    controls = client.get("/static/themed-controls.css").text
    for selector in (
        ".confirm-action-dialog",
        ".confirm-action-content",
        ".confirm-action-message",
        ".confirm-action-danger",
    ):
        assert selector in controls
