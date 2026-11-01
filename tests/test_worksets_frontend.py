from __future__ import annotations


def test_workset_controls_are_available_without_a_separate_context_row(client):
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
    assert "Перенести задачу из набора" in script
    assert "previousDetails.workset_id || updated.workset_id" in script
    assert (
        'count.textContent = status === "doing" ? `${statusTasks.length}/${state.wipLimit}`'
        in script
    )
    assert "workset-actions-menu" in html
    assert 'class="button button-small button-quiet workset-actions-trigger"' in html
    assert '>Действия</summary>' in html
    assert 'class="workset-actions-popover theme-select-menu"' in html
    assert 'document.addEventListener("pointerdown", (event) =>' in script
    assert 'worksetActionsMenu.contains(event.target)' in script
    assert '  }, true);' in script
    assert 'worksetActionsMenu.removeAttribute("open")' in script
    assert 'event.key !== "Escape" || !worksetActionsMenu?.open' in script
    assert '$("summary", worksetActionsMenu)?.focus();' in script
    assert html.count('class="theme-select-option"') >= 3
    assert "#workset-filter" in client.get("/static/themed-selects.js").text
    assert 'class="toolbar-group project-toolbar-group"' in html
    assert 'class="toolbar-group workset-toolbar-group"' in html
    assert 'class="filter-box workset-filter-box"' in html
    assert 'class="toolbar-filters-group" aria-label="Фильтры доски"' in html
    assert 'class="toolbar-actions-group"' in html
    assert html.index('id="task-filter-menu"') < html.index('class="toolbar-actions-group"')
    assert html.index('id="project-filter"') < html.index('id="workset-filter"')
    assert 'value="__create_project__">＋ Создать проект…</option>' in html
    assert html.index('id="workset-filter"') < html.index('id="task-filter-menu"')
    assert 'els.taskWorkset.closest(".task-workset-field")' in script
    assert "#task-workset" in client.get("/static/themed-selects.js").text
    assert 'id="count-doing"' in html.split('data-column="doing"', 1)[1].split('</header>', 1)[0]
    assert '0/3' in html.split('data-column="doing"', 1)[1].split('</header>', 1)[0]
    assert 'id="wip-warning"' not in html
    assert "task-workset-chip" in script
    assert "window.prompt(" not in script
    assert "/static/app.js?v=0.5.57" in html
    assert "/static/themed-selects.js?v=0.1.8" in html
    assert "/static/style.css?v=0.5.33" in html
    assert "/static/board-workspace.css?v=0.1.17" in html
    toolbar_css = client.get("/static/board-workspace.css").text
    assert ".board-toolbar .filter-box {" in toolbar_css
    assert "background: var(--gh-control, var(--surface));" in toolbar_css
    assert ".board-toolbar .filter-box:has(.theme-select.is-open)" in toolbar_css
    assert ".workset-filter-box .theme-select-value" in toolbar_css
    select_script = client.get("/static/themed-selects.js").text
    assert 'instance.select.id === "workset-filter"' in select_script
    assert 'instance.trigger.title = instance.select.title || valueLabel' in select_script
    assert 'if (instance.select.disabled && openInstance === instance) close(instance);' in select_script
    assert 'menu.classList.add("workset-filter-menu")' in select_script
    assert 'document.addEventListener("focusin", (event) =>' in select_script
    assert 'openInstance.wrapper.contains(event.target) || openInstance.menu.contains(event.target)' in select_script
    assert 'attributeFilter: ["disabled", "hidden", "label", "title", "value"]' in select_script
    assert 'const activeWorksets = state.worksets.filter((workset) => workset.status === "active");' in script
    assert 'const hasSelectableWorksets = activeWorksets.length > 0 || selectedWorkset?.status === "completed";' in script
    assert 'els.worksetFilter.disabled = !hasSelectableWorksets;' in script
    assert 'Создайте первый набор задач' in script
    assert 'new Option("Задачи", "")' in script
    assert 'option.dataset.kind = "workset"' in script
    assert 'option.dataset.triggerLabel = `Набор: ${workset.name}`' in script
    assert 'historyOption.dataset.triggerLabel = `Набор: ${selectedWorkset.name} · история`' in script
    assert '<option value="" data-kind="tasks">Задачи</option>' in html
    assert 'instance.select.id === "workset-filter"' in select_script
    assert 'createWorksetIcon("tasks")' in select_script
    assert 'createWorksetIcon(kind)' in select_script
    assert 'filterBox.hidden = !hasSelectableWorksets;' in script
    assert 'filterBox.classList.toggle("is-empty", !hasSelectableWorksets);' in script
    assert 'id="workset-context"' not in html
    assert "renderWorksetContext" not in script
    assert "workset-context" not in script
    assert '.workset-filter-box.is-empty .theme-select-chevron { display: none; }' in toolbar_css
    assert '.toolbar-main-group > .search-box' in toolbar_css
    assert 'min-width: min(100%, 280px);' in toolbar_css
    assert 'max-width: none;' in toolbar_css
    assert 'max-width: 260px;' in toolbar_css
    assert '.task-filter-count[hidden] { display: none !important; }' in toolbar_css
    assert '@container (max-width: 300px)' in toolbar_css
    assert '.workset-filter-menu .theme-select-option[aria-selected="true"]::before' in toolbar_css
    assert '.workset-select-icon' in toolbar_css
    assert '.workset-filter-menu .theme-select-option { display: flex; align-items: center; gap: 9px; }' in toolbar_css
    assert '.workset-toolbar-group { flex: 0 1 260px; min-width: 220px; }' in toolbar_css
    assert '.workset-filter-menu .theme-select-option[aria-selected="true"]:hover' in toolbar_css
    assert '.board-toolbar .filter-box:has(.theme-select-trigger:focus-visible)' in toolbar_css
    assert '.board-toolbar .filter-box:focus-within' not in toolbar_css
    assert 'aria-modal="true"' in html
    assert 'aria-label="Закрыть"' in html
    assert "Показать ещё" in script
    assert "task_reopened" in script
    assert "Состав" in script
    assert 'membershipLocked = currentWorkset?.status === "completed"' in script
    assert "Состав завершённого рабочего набора нельзя менять" in script
    assert "/static/board-workspace.css?v=0.1.17" in html
