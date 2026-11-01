from __future__ import annotations


def test_search_filter_toolbar_controls_are_aligned_and_platform_shortcut_is_rendered(client):
    html = client.get("/").text
    assert 'class="board-toolbar" aria-label="Поиск и фильтры"' in html
    assert html.count('class="toolbar-icon"') == 3
    assert 'id="search-shortcut" class="quick-add-keycap search-shortcut-keycap"' in html
    assert 'placeholder="Поиск…"' in html
    assert 'value="__create_project__">＋ Создать проект…</option>' in html
    assert 'id="shortcuts-settings-page" class="settings-subpage"' in html
    assert "⌘/Ctrl K" in html.split('id="shortcuts-settings-page"', 1)[1]

    css = client.get("/static/themed-controls.css").text
    for selector in (
        ".toolbar-main-group > .search-box",
        ".board-toolbar .filter-box",
        ".toolbar-main-group > .search-box:focus-within",
        ".board-toolbar .search-shortcut-keycap",
        ".board-toolbar .toolbar-icon",
    ):
        assert selector in css
    assert "--toolbar-control-height: 40px" in css

    script = client.get("/static/app.js").text
    assert 'const shortcutPlatform = navigator.userAgentData?.platform || navigator.platform || "";' in script
    assert 'els.searchShortcut.textContent = isApplePlatform ? "⌘ K" : "Ctrl K";' in script


def test_project_workspace_controls_are_served(client):
    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    for element_id in (
        "project-filter",
        "project-dialog",
        "project-command-search",
        "focus-bar",
        "focus-task",
        "density-toggle",
        "shortcuts-settings-page",
    ):
        assert f'id="{element_id}"' in html
    assert "/static/app.js?v=0.5.57" in html
    assert "/static/style.css?v=0.5.33" in html


def test_frontend_includes_project_search_undo_focus_and_density_behaviors(client):
    response = client.get("/static/app.js")
    assert response.status_code == 200
    script = response.text

    assert 'projectTag(state.project)' in script
    assert 'writeStorage("flowboard-projects", JSON.stringify(state.projects))' in script
    assert 'function normalizeSearch(value)' in script
    assert '.replace(/ё/g, "е")' in script
    assert 'function restoreDeletedTask(snapshot, files, wasFocused)' in script
    assert 'function handleFocusDone()' in script
    assert 'function syncFocusedTask()' in script
    assert 'syncFocusedTask();' in script
    assert 'if (!task || task.status === "done")' in script
    assert 'const wasFocused = state.focusTaskId === taskId;' in script
    assert 'if (wasFocused && previousState.status !== "done") setFocusedTask(taskId);' in script
    assert 'function applyDensity(density, persist = false)' in script
    assert 'event.key === "/"' in script
    assert 'event.code === "KeyK"' in script
    assert 'event.code === "KeyP"' in script
    assert 'event.code === "KeyN"' in script
    assert 'event.key.toLocaleLowerCase("en")' not in script
    assert "Буквенные сочетания работают при любой раскладке" in client.get("/").text
    dragdrop = client.get("/static/dragdrop.js")
    assert dragdrop.status_code == 200
    assert (
        'this.options.onStart({ item, from: this.element, oldIndex: this.oldIndex })'
        in dragdrop.text
    )


def test_markdown_code_blocks_preserve_formatting_and_support_horizontal_scroll(client):
    css = client.get("/static/style.css").text

    assert ".markdown-preview pre {" in css
    assert "overflow-x: auto;" in css
    assert "white-space: pre;" in css
    assert ".markdown-preview pre code {" in css
    assert "[data-theme=\"dark\"] .markdown-preview pre code { background: transparent; }" in css


def test_frontend_styles_support_compact_density_focus_and_image_previews(client):
    response = client.get("/static/style.css")
    assert response.status_code == 200
    css = response.text

    assert ':root[data-density="compact"] .task-card' in css
    assert ".focus-bar" in css
    assert ".attachment-preview" in css
    assert ".project-command-option" in css
    assert '[data-theme="dark"] .focus-bar' in css
    assert "border-left: 3px solid var(--accent);" in css
    assert "@keyframes focus-indicator-pulse" in css
    assert ".focus-indicator::before { animation: none; }" in css
    assert "#copy-description.is-copied .copy-description-check" in css


def test_frontend_offers_undo_for_task_edits_and_attachment_changes(client):
    script = client.get("/static/app.js").text
    assert "function restoreTaskDetails(taskId, snapshot)" in script
    assert 'toast("Изменения сохранены", "success", "Отменить"' in script
    assert "function undoAttachmentUpload(attachments)" in script
    assert "function undoAttachmentRemoval(taskId, file)" in script
    assert 'toast("Вложение удалено", "success", "Восстановить"' in script
    assert '"Загрузка вложений отменена"' in script
    assert '"Вложение восстановлено"' in script


def test_task_cards_have_scan_friendly_project_type_description_and_tag_hierarchy(client):
    script = client.get("/static/app.js").text
    assert 'function taskDescriptionExcerpt(description, title = "", limit = 240)' in script
    assert "const project = projectForTask(task);" in script
    assert "TASK_TYPE_LABELS = {" in script
    assert "hiddenTags.slice(0, 2)" in script
    assert "task.attachments_count" in script

    css = client.get("/static/style.css").text
    for selector in (
        ".task-card-meta",
        ".task-project-chip",
        ".task-type-chip",
        ".task-card-excerpt",
        ".tag-pill-more",
        ':root[data-density="compact"] .task-card-excerpt',
        '[data-theme="dark"] .task-card-excerpt',
    ):
        assert selector in css


def test_quick_add_can_assign_optional_task_type(client):
    html = client.get("/").text
    assert '<details id="quick-task-type" class="quick-task-type">' in html
    assert 'id="quick-task-type-label">Тип: Без типа</span>' in html
    assert 'data-task-type="" aria-pressed="true"' in html
    for task_type in ("bug", "feature", "docs", "refactor"):
        assert f'data-task-type="{task_type}"' in html

    script = client.get("/static/app.js").text
    assert 'quickTaskType: ""' in script
    assert "function setQuickTaskType(type)" in script
    assert 'els.quickTaskTypeLabel.textContent = `Тип: ${label}`' in script
    assert 'els.quickTaskType.open = false;' in script
    assert "createTask(title, status, taskType)" in script
    assert 'setQuickTaskType("")' in script
    assert 'const quickAdd = els.quickForm.closest(".quick-add")' in script
    assert 'quickAdd.dataset.taskType = state.quickTaskType' in script
    assert 'delete quickAdd.dataset.taskType' in script
    picker_css = client.get("/static/board-workspace.css").text
    type_tokens = {
        "bug": ("gh-red-fg", "gh-red-bg"),
        "feature": ("gh-green-fg", "gh-green-bg"),
        "docs": ("gh-yellow-fg", "gh-yellow-bg"),
        "refactor": ("gh-purple-fg", "gh-purple-bg"),
    }
    for task_type, (foreground, background) in type_tokens.items():
        assert f'.quick-add[data-task-type="{task_type}"]' in picker_css
        assert f'--quick-type-fg: var(--{foreground}' in picker_css
        assert f'--quick-type-bg: var(--{background}' in picker_css
    assert '.quick-add[data-task-type] .quick-task-type > summary.quick-task-type-trigger' in picker_css
    assert '.quick-add[data-task-type] .quick-add-entry' in picker_css
    assert (
        '.quick-add[data-task-type] .quick-add-form {\n  padding-inline: 10px 0;\n}'
        in picker_css
    )
    create_task = script.split("async function createTask(", 1)[1].split("async function undoCreation(", 1)[0]
    assert 'task_type: taskType || ""' in create_task
    assert 'taskFilters: readTaskFiltersFromUrl()' in script

    css = client.get("/static/style.css").text
    assert ".quick-task-type" in css
    assert ".quick-task-type-options" in client.get("/static/board-workspace.css").text
    assert '.quick-type-option[aria-pressed="true"]' in css
    assert "@media (max-width: 640px)" in css


def test_task_panel_can_upload_images_pasted_from_clipboard(client):
    html = client.get("/").text
    assert "Можно также вставить изображение: ⌘/Ctrl+V" in html

    script = client.get("/static/app.js").text
    assert "function clipboardImageExtension(mimeType)" in script
    assert "function pastedImageFiles(clipboardData)" in script
    assert 'mimeType.startsWith("image/")' in script
    assert "function handleTaskPanelPaste(event)" in script
    assert 'els.panel.addEventListener("paste", handleTaskPanelPaste)' in script
    assert "event.preventDefault();" in script

    css = client.get("/static/style.css").text
    assert ".attachment-paste-hint" in css


def test_task_panel_has_compact_layout_searchable_tag_editor_and_single_task_export(client):
    html = client.get("/").text
    for element_id in (
        "task-tag-list",
        "task-tag-input",
        "task-tag-create-row",
        "task-tag-custom-toggle",
        "add-task-tag",
        "export-task",
        "task-description-section",
    ):
        assert f'id="{element_id}"' in html
    assert "/static/app.js?v=0.5.57" in html
    assert "/static/style.css?v=0.5.33" in html

    script = client.get("/static/app.js").text
    assert "function renderTaskTagEditor()" in script
    assert "function tagChoiceDetails(value)" in script
    assert "function availableTaskTagChoices()" in script
    assert "function toggleTaskTagChoice(value)" in script
    assert 'option.setAttribute("aria-selected", String(isSelected))' in script
    assert 'const canCreate = Boolean(els.taskTagInput.value.trim()) && inputDetail.kind === "custom" && !exactMatch' in script
    assert 'els.taskTagCustomToggle.addEventListener("click", toggleTaskTagPopover)' in script
    assert 'els.addTaskTag.addEventListener("click", () => addTaskTags())' in script
    assert 'els.exportTask.addEventListener("click", handleTaskExport)' in script
    assert 'window.location.href = `/api/tasks/${task.id}/export`' in script
    assert "async function handleTaskExport()" in script

    css = client.get("/static/style.css").text
    redesign_css = client.get("/static/task-editor-redesign.css").text
    assert "grid-template-columns: minmax(0, 1.08fr) minmax(245px, .92fr)" in css
    assert ".task-tag-option.is-selected" in redesign_css
    assert ".task-tag-add-trigger" in redesign_css
    assert "overflow-y: auto" in redesign_css
    assert "@media (max-height: 720px) and (min-width: 721px)" in css



def test_task_panel_is_reading_first_and_has_compact_attachment_and_action_controls(client):
    html = client.get("/").text
    assert "TASK DETAILS" not in html
    assert "Детали задачи" not in html
    assert "НАЗВАНИЕ ЗАДАЧИ" not in html
    assert 'class="task-title-row"' in html
    assert 'class="task-title-reference"' in html
    assert 'aria-label="Добавить вложение"' in html
    assert 'id="copy-description" class="icon-button workspace-copy-button"' in html
    assert 'id="toggle-preview"' not in html
    assert 'aria-label="Описание задачи. Нажмите Enter, чтобы редактировать."' in html
    assert 'id="focus-task" class="icon-button task-header-action focus-task-action"' in html
    assert html.index('id="focus-task"') < html.index('id="task-more-menu"')
    assert html.index('id="export-task"') > html.index('id="task-more-menu"')
    for element_id in (
        "task-title-display",
        "task-title-display-text",
        "panel-task-reference",
        "toggle-attachment-upload",
        "task-more-toggle",
        "task-more-menu",
    ):
        assert f'id="{element_id}"' in html
    assert 'id="task-description" class="text-field description-field" maxlength="30000" rows="8" placeholder="Контекст, решение или следующие шаги… Поддерживается Markdown." hidden' in html
    assert 'id="description-preview" class="markdown-preview markdown-preview-editable"' in html

    script = client.get("/static/app.js").text
    assert 'els.taskTitleDisplayText.textContent = task.title || "Без названия"' in script
    assert 'els.taskTitleDisplay.addEventListener("click"' in script
    assert 'event.stopPropagation();' in script
    assert 'toast("У задачи должно быть название", "error")' in script
    assert 'els.descriptionPreview.addEventListener("click"' in script
    assert 'els.descriptionPreview.addEventListener("keydown"' in script
    assert 'function setDescriptionEditing(editing)' in script
    assert 'els.toggleAttachmentUpload.addEventListener("click"' in script
    assert 'els.taskMoreToggle.addEventListener("click"' in script
    assert 'void requestMarkdownPreview()' in script

    css = client.get("/static/style.css").text
    assert "width: min(1180px, calc(100vw - 34px))" in css
    assert ".task-title-display" in css
    assert ".task-more-menu[hidden]" in css
    assert ".task-title-row" in css
    assert ".task-title-reference" in css
    assert ".tag-add-row { width: min(100%, 235px)" in css
    assert ".attachment-icon-button" in css
    assert ".markdown-preview-editable" in css
    assert ".attachment-dropzone[hidden]" in css
    assert ".description-field[hidden]" in css
    assert "grid-template-columns: minmax(0, 1.12fr) minmax(300px, .88fr)" in css
    assert "@media (max-width: 900px) and (min-width: 641px)" in css


def test_main_board_promotes_task_import_and_moves_backup_to_settings(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert 'id="files-menu"' not in html
    assert 'id="open-settings"' in html
    assert 'id="settings-dialog"' in html
    assert 'id="settings-menu"' not in html
    assert 'role="tablist" aria-label="Разделы настроек"' in html
    assert 'id="import-button" class="toolbar-menu-trigger topbar-import-button"' in html
    assert 'id="import-files" class="visually-hidden" type="file" accept=".md,text/markdown" multiple' in html
    assert 'aria-label="Импорт задач"' in html
    assert 'Импорт задач</span>' in html
    assert 'id="export-md"' not in html
    assert 'id="export-zip"' not in html
    organization_panel = html.split('id="settings-panel-organization"', 1)[1].split('</section>', 1)[0]
    assert 'id="backup-export-button"' in organization_panel
    assert 'Данные и резервные копии' in organization_panel
    assert 'Скачать резервную копию ZIP' in html
    assert 'id="theme-toggle"' in html
    assert 'id="density-toggle"' in html
    assert 'id="shortcuts-button"' in html
    assert "MY PROJECT" not in html
    assert "Доска задач" not in html
    assert "Мои задачи" in html
    assert 'id="total-count"' not in html
    assert 'id="active-count"' not in html
    assert 'id="doing-count"' not in html
    assert 'id="filter-summary"' not in html

    css = client.get("/static/style.css").text
    assert ".topbar-import-button" in css
    assert ".settings-dialog" in css
    assert "@media (max-width: 640px)" in css
    assert ".task-card-title" in css

    script = client.get("/static/app.js").text
    assert 'els.totalCount.textContent' not in script
    assert 'els.activeCount.textContent' not in script
    assert 'els.doingCount.textContent' not in script
    assert 'els.filterSummary.textContent' not in script
    assert (
        'count.textContent = status === "doing" ? `${statusTasks.length}/${state.wipLimit}`'
        in script
    )
    assert (
        'count.classList.toggle("is-over-limit", status === "doing" && '
        'statusTasks.length > state.wipLimit)'
        in script
    )
    assert 'selectSettingsTab(tabs[nextIndex].dataset.settingsTab, { focus: true })' in script
    assert 'els.settingsDialog.addEventListener("close", () => {' in script
    assert 'els.settingsDialog.addEventListener("cancel", (event) => {' in script
    assert 'if (activeSettingsSubpage) closeSettingsSubpage();' in script
    assert 'function openSettingsSubpage(name)' in script
    assert 'function closeSettingsSubpage({ focus = true } = {})' in script
    assert 'els.backupExport.addEventListener("click", () => { window.location.href = "/api/export?format=zip"; });' in script
    assert 'els.exportMd' not in script
    assert 'els.exportZip' not in script



def test_settings_tools_open_as_nested_pages_and_keep_the_settings_dialog_open(client):
    html = client.get("/").text
    settings_dialog = html.split('<dialog id="settings-dialog"', 1)[1].split('</dialog>', 1)[0]
    for page_id in (
        "shortcuts-settings-page",
        "archive-settings-page",
    ):
        assert f'id="{page_id}"' in settings_dialog
    assert 'id="shortcuts-dialog"' not in html
    assert 'id="archive-dialog"' not in html

    script = client.get("/static/app.js").text
    for fragment in (
        'shortcuts: els.shortcutsPage',
        'archive: els.archivePage',
        'projects: manageProjectsPage',
        'function openSettingsSubpage(name)',
        'returnToSettingsSubpageAfterPanel = "archive"',
        'if (returnToSettingsSubpageAfterPanel) {',
        'void openArchive();',
        'function closeSettingsSubpage({ focus = true } = {})',
        'settingsParentScrollTop = $(".settings-panels").scrollTop',
        'page.querySelector(".settings-back-button")',
        'els.settingsDialog.classList.add("is-subpage")',
        'els.settingsDialog.classList.remove("is-subpage")',
        'els.settingsDialog.addEventListener("cancel", (event) => {',
        'els.shortcutsButton.addEventListener("click", () => openSettingsSubpage("shortcuts"))',
        'function openManageProjectsPage() {',
        'openSettingsSubpage("projects")',
    ):
        assert fragment in script
    assert 'els.archiveDialog.showModal()' not in script
    assert 'manageProjectsDialog.showModal()' not in script

    css = client.get("/static/style.css").text
    assert ".settings-dialog.is-subpage .settings-tabs { display: none; }" in css
    assert ".settings-tab[hidden] { display: none; }" in css

def test_archive_and_unified_type_tag_filters_leave_only_sorting_in_columns(client):
    html = client.get("/").text
    assert 'id="archive-settings-page" class="settings-subpage archive-settings-page"' in html
    assert 'id="archive-dialog"' not in html
    assert 'id="open-archive"' in html
    assert 'id="archive-auto-enabled"' in html
    assert 'id="archive-after-days"' in html
    assert 'id="archive-search"' in html
    assert 'id="archive-project-filter"' in html
    assert 'id="archive-tag-filter"' in html
    assert html.count('data-column-options-toggle=') == 4
    assert html.count('data-column-filter=') == 0
    assert html.count('data-column-sort=') == 4
    assert 'id="task-filter-menu"' in html
    assert 'id="task-filter-types"' in html
    assert 'id="task-filter-tags"' in html
    assert 'data-archive-completed' in html
    assert 'id="archive-task"' in html
    assert "/static/app.js?v=0.5.57" in html
    assert "/static/style.css?v=0.5.33" in html
    assert 'id="toggle-done" class="done-toggle"' in html
    assert '<span>Ещё</span>' in html
    assert 'aria-label="Показать остальные завершённые задачи"' in html
    assert '<path d="m7 10 5 5 5-5"/>' in html

    script = client.get("/static/app.js").text
    for fragment in (
        "function readColumnPreferences()",
        "function renderTaskFilters()",
        "function matchesFilters(task, { skipTypes = false, skipTags = false } = {})",
        "function sortColumnTasks(tasks, mode)",
        'writeStorage("flowboard-column-preferences"',
        'api("/api/archive/tasks")',
        'api("/api/archive/settings")',
        'api("/api/archive/completed", { method: "POST" })',
        'api(`/api/archive/tasks/${taskId}/restore`, { method: "POST" })',
        'const label = isExpanded',
        '? "Свернуть список завершённых задач"',
        '"Показать остальные завершённые задачи"',
        'els.toggleDone.setAttribute("aria-label", label)',
        'els.toggleDone.setAttribute("aria-expanded", String(isExpanded))',
    ):
        assert fragment in script

    css = client.get("/static/style.css").text
    assert ".column-options-popover" in css
    assert ".archive-settings-page" in css
    assert ".settings-subpage" in css
    assert ".archive-item" in css
    assert '.done-toggle[aria-expanded="true"] svg' in css
    assert "transform: rotate(180deg)" in css
    assert "flex: 0 0 32px;" in css


def test_input_focus_uses_theme_ring_only_for_keyboard_navigation(client):
    html = client.get("/").text
    assert "/static/style.css?v=0.5.33" in html
    assert '/static/github-theme.css?v=0.2.5' in html
    assert '/static/themed-controls.css?v=0.1.15' in html
    assert '/static/board-workspace.css?v=0.1.17' in html
    assert '/static/app.js?v=0.5.57' in html

    style = client.get("/static/style.css").text
    theme = client.get("/static/github-theme.css").text
    workspace = client.get("/static/board-workspace.css").text
    script = client.get("/static/app.js").text

    for stylesheet in (style, theme):
        assert "button:focus-visible" in stylesheet
        assert "\ninput:focus-visible {" not in stylesheet
        assert "\nselect:focus-visible {" not in stylesheet
        assert "\ntextarea:focus-visible {" not in stylesheet

    assert "--focus-ring: var(--gh-focus, color-mix(in srgb, var(--accent) 35%, transparent));" in workspace
    assert "*:focus {\n  outline: none !important;\n}" in workspace
    assert ':root[data-focus-modality="keyboard"] *:focus-visible' in workspace
    assert ':root[data-focus-modality="pointer"] *:focus-visible' in workspace
    assert ".quick-add:has(.quick-add-form input:focus-visible)" in workspace
    assert ".search-box:has(input:focus-visible)" in workspace
    assert ".filter-box:has(:is(select, .theme-select-trigger):focus-visible)" in workspace
    assert ".toast-position-option:has(input:focus-visible)" in workspace
    assert ".toolbar-main-group > .search-box:has(input:focus-visible)" in workspace
    assert (
        ':root[data-focus-modality="pointer"] .toolbar-main-group > .search-box:focus-within,\n'
        ':root[data-focus-modality="pointer"] .toast-position-option:focus-within {\n  outline: none !important;'
    ) in workspace
    assert "box-shadow: none !important;" in workspace
    assert 'focusRoot.dataset.focusModality = "pointer"' in script
    assert 'focusRoot.dataset.focusModality = "keyboard"' in script
    assert 'document.addEventListener("pointerdown"' in script
    assert 'document.addEventListener("keydown"' in script


def test_file_and_settings_menus_are_grouped_and_explain_theme_states(client):
    html = client.get("/").text
    controls = client.get("/static/themed-controls.css").text
    assert "/static/themed-controls.css?v=0.1.15" in html
    assert html.count('class="settings-tab"') == 4
    for fragment in (
        'id="settings-tab-tasks" class="settings-tab" type="button" role="tab" aria-selected="true" aria-controls="settings-panel-tasks" data-settings-tab="tasks">Задачи и архив</button>',
        'id="settings-tab-appearance" class="settings-tab" type="button" role="tab" aria-selected="false" aria-controls="settings-panel-appearance" data-settings-tab="appearance"',
        'id="settings-tab-behavior" class="settings-tab" type="button" role="tab" aria-selected="false" aria-controls="settings-panel-behavior" data-settings-tab="behavior"',
        'id="settings-tab-organization" class="settings-tab" type="button" role="tab" aria-selected="false" aria-controls="settings-panel-organization" data-settings-tab="organization"',
        'id="settings-panel-tasks" class="settings-panel" role="tabpanel"',
        'id="settings-panel-appearance" class="settings-panel" role="tabpanel"',
        'id="settings-panel-behavior" class="settings-panel" role="tabpanel"',
        'id="settings-panel-organization" class="settings-panel" role="tabpanel"',
        '<h4>Пользовательские темы</h4>',
        '<h4>Архив задач</h4>',
        'id="open-archive"',
        'id="organization-settings-actions"',
        'id="theme-delete-help"',
        'id="theme-reset-help"',
        'id="theme-toggle-icon" class="toolbar-menu-item-icon theme-toggle-icon"',
        'id="reset-theme-button" class="button button-quiet toolbar-menu-item" type="button" disabled aria-describedby="theme-reset-help" title="Восстановить стандартную тему"',
        'id="delete-theme-button" class="button button-quiet button-danger-quiet toolbar-menu-item"',
    ):
        assert fragment in html

    assert ".theme-manager-select" in controls
    assert "text-overflow: ellipsis" in controls
    assert ".toolbar-menu-section" in controls
    assert ".settings-dialog .theme-manager-select" in controls

    script = client.get("/static/app.js").text
    assert 'Активна встроенная тема. Сохранено тем: ${themes.length}' in script
    assert '$("#organization-settings-actions").append(manageProjectsButton);' in script
    assert '$("#settings-panel-other .settings-option-list").append(manageProjectsButton);' not in script
    assert 'selectSettingsTab(tabs[nextIndex].dataset.settingsTab, { focus: true })' in script


def test_column_header_actions_have_contextual_names_and_comfortable_hit_areas(client):
    html = client.get("/").text
    for label in ("К выполнению", "В работе", "Ожидает", "Готово"):
        assert f'aria-label="Сортировка задач: {label}"' in html
        assert f'title="Сортировка задач: {label}"' in html
    for label in ("К выполнению", "В работе", "Ожидает"):
        assert f'aria-label="Добавить задачу в колонку «{label}»"' in html

    css = client.get("/static/style.css").text
    board_css = client.get("/static/board-workspace.css").text
    assert ".column-add { display: grid; place-items: center; flex: 0 0 32px;" in css
    assert "flex-basis: 40px;" in board_css
    assert "width: 40px;" in board_css
    assert ".column-options-toggle:focus-visible" in css
    assert ".column-add:focus-visible" in css
    assert ".column-options-toggle {" in css
    assert 'id="toggle-done" class="done-toggle"' in html
    assert 'aria-label="Показать остальные завершённые задачи"' in html


def test_unified_type_tag_filter_uses_or_within_groups_and_and_between_them(client):
    import json
    import shutil
    import subprocess

    if not shutil.which("node"):
        return
    script = client.get("/static/app.js").text
    function = script.split("function matchesFilters", 1)[1].split(
        "function availableBoardTags", 1
    )[0]
    tasks = [
        {"id": 1, "task_type": "bug", "tags": "frontend"},
        {"id": 2, "task_type": "feature", "tags": "ui"},
        {"id": 3, "task_type": "docs", "tags": "frontend"},
        {"id": 4, "task_type": "bug", "tags": "backend"},
        {"id": 5, "task_type": "", "tags": "frontend"},
    ]
    node_script = f"""
const state = {{search: "", project: "", worksetId: null,
  taskFilters: {{types: ["bug", "feature"], tags: ["frontend", "ui"]}}}};
const TASK_TYPE_LABELS = {{
  bug: "Ошибка", feature: "Функция", docs: "Документация", refactor: "Рефакторинг"
}};
const normalizeSearch = value => String(value || "").toLocaleLowerCase("ru").replace(/ё/g, "е").trim();
const taskTags = task => String(task.tags || "")
  .split(",").map(tag => tag.trim()).filter(Boolean);
const projectFromTag = () => "";
const taskMatchesType = (task, value) => value === "__none__"
  ? !task.task_type
  : task.task_type === value;
function matchesFilters{function}
const tasks = {json.dumps(tasks, ensure_ascii=False)};
const matched = tasks.filter(task => matchesFilters(task)).map(task => task.id);
const typeCount = tasks.filter(task => matchesFilters(task, {{skipTypes: true}})
  && (task.task_type === "bug" || task.task_type === "feature")).length;
state.taskFilters.types = ["__none__"];
const noneMatches = matchesFilters({{task_type: "", tags: "frontend"}}, {{skipTags: true}});
console.log(JSON.stringify({{matched, typeCount, noneMatches}}));
"""
    result = subprocess.run(
        ["node", "-e", node_script], check=True, capture_output=True, text=True
    )
    assert json.loads(result.stdout) == {
        "matched": [1, 2],
        "typeCount": 2,
        "noneMatches": True,
    }
