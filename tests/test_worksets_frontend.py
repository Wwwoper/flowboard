from __future__ import annotations


def test_workset_controls_and_per_project_context_are_present(client):
    html = client.get("/").text
    script = client.get("/static/app.js").text
    for element_id in (
        "workset-filter",
        "create-workset",
        "rename-workset",
        "workset-history",
        "workset-context",
        "task-workset",
        "workset-history-dialog",
        "workset-editor-dialog",
    ):
        assert f'id="{element_id}"' in html
    assert "flowboard-workset:${state.project}" in script
    assert "task.workset_id !== state.worksetId" in script
    assert "Перенести задачу из набора" in script
    assert "previousDetails.workset_id || updated.workset_id" in script
    assert "doingCount > state.wipLimit" in script
    assert "workset-actions-menu" in html
    assert 'class="workset-actions-popover theme-select-menu"' in html
    assert html.count('class="theme-select-option"') >= 3
    assert "#workset-filter" in client.get("/static/themed-selects.js").text
    assert 'class="toolbar-group project-toolbar-group"' in html
    assert 'class="toolbar-group workset-toolbar-group"' in html
    assert html.index('id="project-filter"') < html.index('id="add-project"')
    assert html.index('id="add-project"') < html.index('id="workset-filter"')
    assert html.index('id="workset-filter"') < html.index('id="tag-filter"')
    assert 'els.taskWorkset.closest(".task-workset-field")' in script
    assert "#task-workset" in client.get("/static/themed-selects.js").text
    assert 'id="wip-warning"' in html.split('data-column="doing"', 1)[1].split('</header>', 1)[0]
    assert "task-workset-chip" in script
    assert "window.prompt(" not in script
    assert "/static/app.js?v=0.5.46" in html
    assert "/static/themed-selects.js?v=0.1.4" in html
    assert "/static/style.css?v=0.5.28" in html
    assert 'aria-modal="true"' in html
    assert 'aria-label="Закрыть"' in html
    assert "Показать ещё" in script
    assert "task_reopened" in script
    assert "Состав" in script
    assert 'membershipLocked = currentWorkset?.status === "completed"' in script
    assert "Состав завершённого рабочего набора нельзя менять" in script
    assert "/static/board-workspace.css?v=0.1.4" in html
