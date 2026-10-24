from __future__ import annotations


def test_task_panel_uses_autosave_without_a_manual_save_button(client):
    html = client.get("/").text
    assert 'id="task-form"' in html
    assert 'id="save-task"' not in html
    assert 'id="focus-task"' in html
    assert 'id="export-task"' in html

    script = client.get("/static/app.js").text
    assert "function scheduleTaskDraftSave(delay = 180)" in script
    assert "async function saveCurrentTaskDraft()" in script
    assert 'els.taskTitle.addEventListener("blur", () => scheduleTaskDraftSave(180))' in script
    assert 'els.taskStatus.addEventListener("change", () => scheduleTaskDraftSave(180))' in script
