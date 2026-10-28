from __future__ import annotations


def test_image_attachments_open_preview_with_a_separate_download_action(client):
    html = client.get("/").text
    for element_id in (
        "attachment-preview-dialog",
        "attachment-preview-title",
        "attachment-preview-image",
        "attachment-preview-loading",
        "attachment-preview-error",
        "attachment-preview-download",
        "attachment-preview-close",
    ):
        assert f'id="{element_id}"' in html
    assert "/static/app.js?v=0.5.39" in html
    assert "/static/style.css?v=0.5.21" in html

    script = client.get("/static/app.js").text
    assert "function openAttachmentPreview(attachment)" in script
    assert "function closeAttachmentPreview()" in script
    assert "saveCurrentTaskDraft()" in script
    assert 'els.attachmentPreviewDialog.addEventListener("cancel"' in script
    assert 'els.attachmentPreviewDialog.addEventListener("click"' in script
    assert 'download.href = `/api/files/${attachment.id}`' in script
    assert 'download.download = attachment.filename' in script

    css = client.get("/static/style.css").text
    assert ".attachment-preview-trigger" in css
    assert ".attachment-download" in css
    assert ".attachment-preview-dialog::backdrop" in css
    assert ".attachment-preview-image" in css


def test_unsaved_task_description_is_saved_before_upload_and_when_leaving_editor(client):
    script = client.get("/static/app.js").text
    assert "async function saveCurrentTaskDraft()" in script
    assert 'els.taskDescription.addEventListener("blur", () => scheduleTaskDraftSave(180))' in script
    assert "async function setDescriptionEditing(editing)" in script
    assert "if (!editing && !(await saveCurrentTaskDraft())) return;" in script

    upload_start = script.index("async function uploadFiles(fileList)")
    upload_end = script.index("function clipboardImageExtension", upload_start)
    upload_handler = script[upload_start:upload_end]
    assert "await saveCurrentTaskDraft()" in upload_handler
    assert upload_handler.index("await saveCurrentTaskDraft()") < upload_handler.index(
        'await api(`/api/tasks/${taskId}/files`'
    )

    assert "async function dismissTaskPanel()" in script
