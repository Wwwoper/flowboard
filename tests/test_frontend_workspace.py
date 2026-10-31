from __future__ import annotations


def test_search_filter_toolbar_controls_are_aligned_and_platform_shortcut_is_rendered(client):
    html = client.get("/").text
    assert 'class="board-toolbar" aria-label="Поиск и фильтры"' in html
    assert html.count('class="toolbar-icon"') == 5
    assert 'id="search-shortcut" class="quick-add-keycap search-shortcut-keycap"' in html
    assert 'aria-label="Создать проект" title="Создать проект"' in html
    toolbar_html, _, shortcuts_html = html.partition('<dialog id="shortcuts-dialog"')
    assert "⌘/Ctrl K" not in toolbar_html
    assert "⌘/Ctrl K" in shortcuts_html

    css = client.get("/static/themed-controls.css").text
    for selector in (
        ".board-toolbar > .search-box",
        ".board-toolbar .filter-box",
        ".board-toolbar .add-project-button",
        ".board-toolbar > .search-box:focus-within",
        ".board-toolbar .search-shortcut-keycap",
        ".board-toolbar .toolbar-icon",
    ):
        assert selector in css
    assert "--toolbar-control-height: 36px" in css

    script = client.get("/static/app.js").text
    assert 'const shortcutPlatform = navigator.userAgentData?.platform || navigator.platform || "";' in script
    assert 'els.searchShortcut.textContent = isApplePlatform ? "⌘ K" : "Ctrl K";' in script


def test_project_workspace_controls_are_served(client):
    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    for element_id in (
        "project-filter",
        "add-project",
        "project-dialog",
        "project-command-search",
        "focus-bar",
        "focus-task",
        "density-toggle",
        "shortcuts-dialog",
    ):
        assert f'id="{element_id}"' in html
    assert "/static/app.js?v=0.5.46" in html
    assert "/static/style.css?v=0.5.28" in html


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
    assert 'event.key.toLocaleLowerCase("en") === "p"' in script
    dragdrop = client.get("/static/dragdrop.js")
    assert dragdrop.status_code == 200
    assert (
        'this.options.onStart({ item, from: this.element, oldIndex: this.oldIndex })'
        in dragdrop.text
    )


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
    assert 'function taskDescriptionExcerpt(description, title = "", limit = 112)' in script
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
    assert 'id="quick-task-type"' in html
    assert 'data-task-type="" aria-pressed="true"' in html
    for task_type in ("bug", "feature", "docs", "refactor"):
        assert f'data-task-type="{task_type}"' in html

    script = client.get("/static/app.js").text
    assert 'quickTaskType: ""' in script
    assert "function setQuickTaskType(type)" in script
    assert "createTask(title, status, taskType)" in script
    assert 'setQuickTaskType("")' in script
    assert (
        'const inheritedTag = state.tag && !Object.hasOwn(TASK_TYPE_LABELS, state.tag.toLowerCase())'
        in script
    )

    css = client.get("/static/style.css").text
    assert ".quick-task-type" in css
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
    assert "/static/app.js?v=0.5.46" in html
    assert "/static/style.css?v=0.5.28" in html

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
    assert 'id="task-description" class="text-field description-field" maxlength="5000" rows="8" placeholder="Контекст, решение или следующие шаги… Поддерживается Markdown." hidden' in html
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
    assert 'let doingCount = 0;' in script
    assert 'if (status === "doing") doingCount = statusTasks.length;' in script
    assert 'const overLimit = doingCount > state.wipLimit;' in script
    assert 'selectSettingsTab(tabs[nextIndex].dataset.settingsTab, { focus: true })' in script
    assert 'els.settingsDialog.addEventListener("close", () => els.settingsOpen.focus({ preventScroll: true }));' in script
    assert 'if (els.settingsDialog.open) els.settingsDialog.close();' in script
    assert 'els.backupExport.addEventListener("click", () => { window.location.href = "/api/export?format=zip"; });' in script
    assert 'els.exportMd' not in script
    assert 'els.exportZip' not in script


def test_archive_and_per_column_filters_are_available_without_adding_a_board_column(client):
    html = client.get("/").text
    assert 'id="archive-dialog"' in html
    assert 'id="open-archive"' in html
    assert 'id="archive-auto-enabled"' in html
    assert 'id="archive-after-days"' in html
    assert 'id="archive-search"' in html
    assert 'id="archive-project-filter"' in html
    assert 'id="archive-tag-filter"' in html
    assert html.count('data-column-options-toggle=') == 4
    assert html.count('data-column-filter=') == 4
    assert html.count('data-column-sort=') == 4
    assert 'data-archive-completed' in html
    assert 'id="archive-task"' in html
    assert "/static/app.js?v=0.5.46" in html
    assert "/static/style.css?v=0.5.28" in html
    assert 'id="toggle-done" class="done-toggle"' in html
    assert 'aria-label="Показать остальные завершённые задачи"' in html
    assert '<path d="m7 10 5 5 5-5"/>' in html

    script = client.get("/static/app.js").text
    for fragment in (
        "function readColumnPreferences()",
        "function populateColumnFilters()",
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
    assert ".archive-dialog" in css
    assert ".archive-item" in css
    assert '.done-toggle[aria-expanded="true"] svg' in css
    assert "transform: rotate(180deg)" in css
    assert "flex: 0 0 32px;" in css


def test_input_focus_does_not_highlight_form_frames(client):
    html = client.get("/").text
    assert "/static/style.css?v=0.5.28" in html
    assert '/static/github-theme.css?v=0.2.4' in html

    style = client.get("/static/style.css").text
    theme = client.get("/static/github-theme.css").text

    for stylesheet in (style, theme):
        assert "button:focus-visible" in stylesheet
        assert "input:focus-visible" not in stylesheet
        assert "select:focus-visible" not in stylesheet
        assert "textarea:focus-visible" not in stylesheet

    for selector in (".quick-add:focus-within", ".text-field:focus {"):
        assert selector not in style
    for selector in (
        ".quick-add:focus-within",
        ".search-box:focus-within",
        ".filter-box:focus-within",
        ".text-field:focus {",
    ):
        assert selector not in theme


def test_file_and_settings_menus_are_grouped_and_explain_theme_states(client):
    html = client.get("/").text
    assert "/static/themed-controls.css?v=0.1.12" in html
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

    controls = client.get("/static/themed-controls.css").text
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
        assert f'aria-label="Фильтр и сортировка задач: {label}"' in html
        assert f'title="Фильтр и сортировка задач: {label}"' in html
    for label in ("К выполнению", "В работе", "Ожидает"):
        assert f'aria-label="Добавить задачу в колонку «{label}»"' in html

    css = client.get("/static/style.css").text
    assert ".column-add { display: grid; place-items: center; flex: 0 0 32px;" in css
    assert "width: 32px; height: 32px;" in css
    assert ".column-options-toggle:focus-visible" in css
    assert ".column-add:focus-visible" in css
    assert "flex: 0 0 32px;" in css
    assert 'id="toggle-done" class="done-toggle"' in html
    assert 'aria-label="Показать остальные завершённые задачи"' in html
