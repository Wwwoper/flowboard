from __future__ import annotations


def test_ai_guidelines_settings_page_uses_existing_nested_settings_dialog(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    settings_dialog = html.split('<dialog id="settings-dialog"', 1)[1].split("</dialog>", 1)[0]

    for fragment in (
        'id="open-ai-guidelines"',
        'id="ai-guidelines-settings-page" class="settings-subpage ai-guidelines-settings-page"',
        'id="ai-guidelines-edit-tab" class="ai-guidelines-tab" type="button" role="tab" aria-selected="true" aria-controls="ai-guidelines-edit-panel" tabindex="0"',
        'id="ai-guidelines-preview-tab" class="ai-guidelines-tab" type="button" role="tab" aria-selected="false" aria-controls="ai-guidelines-preview-panel" tabindex="-1"',
        'id="ai-guidelines-edit-panel" class="ai-guidelines-tab-panel ai-guidelines-editor-section" role="tabpanel"',
        'id="ai-guidelines-preview-panel" class="ai-guidelines-tab-panel ai-guidelines-preview-panel" role="tabpanel" aria-labelledby="ai-guidelines-preview-tab" hidden',
        'id="ai-guidelines-editor"',
        'aria-describedby="ai-guidelines-help ai-guidelines-status"',
        'id="ai-guidelines-preview"',
        'id="ai-guidelines-source"',
        'id="ai-guidelines-version"',
        'id="ai-guidelines-updated"',
        'id="save-ai-guidelines"',
        'id="copy-ai-guidelines"',
        'id="download-ai-guidelines"',
        'id="reset-ai-guidelines"',
        'id="retry-ai-guidelines"',
    ):
        assert fragment in settings_dialog
    assert 'id="ai-guidelines-settings-page"' in html
    assert 'id="ai-guidelines-dialog"' not in html


def test_ai_guidelines_settings_actions_keep_drafts_and_use_safe_preview(client):
    script = client.get("/static/app.js").text
    for fragment in (
        'api("/api/ai-task-guidelines")',
        'api("/api/ai-task-guidelines", { method: "PUT", body: { text: submittedText } })',
        'api("/api/ai-task-guidelines", { method: "DELETE" })',
        'api("/api/preview-markdown", { method: "POST", body: { text } })',
        'function aiGuidelinesHasUnsavedChanges()',
        'Текст в редакторе сохранён — можно повторить.',
        'Есть несохранённые изменения регламента.',
        'navigator.clipboard?.writeText',
        'document.execCommand("copy")',
        'new Blob([els.aiGuidelinesEditor.value], { type: "text/markdown;charset=utf-8" })',
        'link.download = "ai-task-guidelines.md"',
        'requestActionConfirmation({',
        'restoreSettingsParent({ focus: false })',
        'setTimeout(() => {',
        'function setAiGuidelinesTab(tab, focus = false)',
        'function handleAiGuidelinesTabKeydown(event)',
        'els.aiGuidelinesEditTab.addEventListener("click"',
        'els.aiGuidelinesPreviewTab.addEventListener("click"',
        'els.settingsDialog.classList.toggle("is-ai-guidelines", name === "ai-guidelines")',
    ):
        assert fragment in script
    input_handler = script.split('els.aiGuidelinesEditor.addEventListener("input", () => {', 1)[1].split("});", 1)[0]
    assert "saveAiGuidelines" not in input_handler
    assert 'api("/api/ai-task-guidelines", { method: "PUT"' not in input_handler
    assert "window.confirm(" not in script

    css = client.get("/static/style.css").text
    for fragment in (
        ".settings-dialog.is-ai-guidelines .settings-panels",
        ".ai-guidelines-workspace",
        ".ai-guidelines-tabs",
        ".ai-guidelines-editor",
        ".ai-guidelines-preview",
        ".ai-guidelines-actions",
        "overflow: hidden",
        "var(--color-surface)",
        "var(--color-border)",
        "@media (max-width: 640px)",
    ):
        assert fragment in css


def test_ai_guidelines_preview_endpoint_escapes_html_and_rejects_dangerous_links(client):
    response = client.post(
        "/api/preview-markdown",
        json={"text": '<script>alert(1)</script>\n\n[опасно](javascript:alert(1))'},
    )
    assert response.status_code == 200
    html = response.json()["html"]
    assert "<script>" not in html
    assert 'href="javascript:' not in html
    assert "<a " not in html
    assert "&lt;script&gt;" in html
