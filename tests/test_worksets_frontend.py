from __future__ import annotations


def test_workset_controls_and_per_project_context_are_present(client):
    html = client.get("/").text
    script = client.get("/static/app.js").text
    for element_id in (
        "workset-filter",
        "create-workset",
        "rename-workset",
        "workset-history",
        "task-workset",
        "workset-history-dialog",
        "workset-editor-dialog",
    ):
        assert f'id="{element_id}"' in html
    assert "flowboard-workset:${state.project}" in script
    assert "task.workset_id !== state.worksetId" in script
    assert "window.prompt(" not in script
    assert "/static/app.js?v=0.5.42" in html
    assert "/static/style.css?v=0.5.25" in html
