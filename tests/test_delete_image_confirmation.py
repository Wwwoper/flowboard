from __future__ import annotations


def test_image_deletion_uses_themed_dialog_and_app_wide_reminder_preference(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    for fragment in (
        'id="delete-image-dialog"',
        'class="app-modal delete-image-dialog"',
        'id="delete-image-message"',
        'id="skip-image-delete-confirmation"',
        "Больше не спрашивать при удалении изображений",
        'id="cancel-delete-image"',
        'id="confirm-delete-image"',
    ):
        assert fragment in html

    script = client.get("/static/app.js").text
    for fragment in (
        'const IMAGE_DELETE_CONFIRMATION_KEY = "flowboard-skip-image-delete-confirmation";',
        'remove.addEventListener("click", () => removeAttachment(attachment.id, attachment.filename, isImageAttachment));',
        "async function removeAttachment(attachmentId, filename, isImage = false)",
        "? await requestImageDeleteConfirmation(filename)",
        "if (confirmed && skipImageDeleteConfirmation.checked)",
        'writeStorage(IMAGE_DELETE_CONFIRMATION_KEY, "true");',
        'deleteImageDialog.addEventListener("cancel", (event) => {',
    ):
        assert fragment in script
    assert 'window.confirm(' not in script
    assert 'await requestActionConfirmation({' in script
    assert 'title: "Удалить вложение?"' in script

    controls = client.get("/static/themed-controls.css").text
    for selector in (
        ".app-modal::backdrop",
        ".delete-image-dialog",
        ".delete-image-content",
        ".delete-image-message",
        ".delete-image-remember",
        ".delete-image-confirm",
    ):
        assert selector in controls
