from __future__ import annotations


def test_task_deletion_uses_themed_confirmation_dialog_instead_of_browser_prompt(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    for fragment in (
        'id="delete-task-dialog"',
        'class="app-modal delete-task-dialog"',
        'aria-labelledby="delete-task-heading"',
        'aria-describedby="delete-task-message"',
        'id="delete-task-message"',
        'id="close-delete-task"',
        'id="cancel-delete-task"',
        'id="confirm-delete-task"',
        "Удалить задачу",
    ):
        assert fragment in html

    script = client.get("/static/app.js").text
    for fragment in (
        'const deleteTaskDialog = $("#delete-task-dialog");',
        "function requestTaskDeleteConfirmation(title)",
        "deleteTaskDialog.showModal();",
        "cancelDeleteTaskButton.focus({ preventScroll: true });",
        'deleteTaskDialog.addEventListener("cancel", (event) => {',
        "if (!(await requestTaskDeleteConfirmation(els.taskTitle.value || task.title))) return;",
        'await api(`/api/tasks/${currentTask.id}`, { method: "DELETE" });',
    ):
        assert fragment in script
    assert 'window.confirm(`Удалить задачу ' not in script

    controls = client.get("/static/themed-controls.css").text
    for selector in (
        ".app-modal::backdrop",
        ".delete-task-dialog",
        ".delete-task-content",
        ".delete-task-message",
        ".delete-task-confirm",
    ):
        assert selector in controls
