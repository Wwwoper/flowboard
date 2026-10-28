(() => {
  "use strict";

  const STATUSES = ["todo", "doing", "waiting", "done"];
  const STATUS_LABELS = {
    todo: "К выполнению",
    doing: "В работе",
    waiting: "Ожидает",
    done: "Готово",
  };
  function readStorage(key, fallback = "") {
    try {
      return localStorage.getItem(key) ?? fallback;
    } catch {
      return fallback;
    }
  }

  function writeStorage(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch {
      // The app remains usable when browser storage is disabled.
    }
  }

  function readStoredProjects() {
    try {
      const value = JSON.parse(localStorage.getItem("flowboard-projects") || "[]");
      return Array.isArray(value)
        ? [...new Set(value.filter((slug) => typeof slug === "string" && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)))]
        : [];
    } catch {
      return [];
    }
  }

  const DEFAULT_COLUMN_PREFERENCES = {
    todo: { tag: "", sort: "created_desc" },
    doing: { tag: "", sort: "updated_desc" },
    waiting: { tag: "", sort: "updated_asc" },
    done: { tag: "", sort: "closed_desc" },
  };
  const COLUMN_SORT_MODES = new Set([
    "manual", "created_desc", "created_asc", "updated_desc", "updated_asc",
    "closed_desc", "type", "title_asc",
  ]);

  function readColumnPreferences() {
    let stored = {};
    try {
      const parsed = JSON.parse(readStorage("flowboard-column-preferences", "{}"));
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) stored = parsed;
    } catch {
      // Invalid local preferences are ignored; safe defaults keep the board usable.
    }
    return Object.fromEntries(STATUSES.map((status) => {
      const value = stored[status] && typeof stored[status] === "object" ? stored[status] : {};
      return [status, {
        tag: typeof value.tag === "string" ? value.tag : DEFAULT_COLUMN_PREFERENCES[status].tag,
        sort: COLUMN_SORT_MODES.has(value.sort) ? value.sort : DEFAULT_COLUMN_PREFERENCES[status].sort,
      }];
    }));
  }

  const doneColumnCollapseQuery = window.matchMedia("(max-width: 1180px)");

  const state = {
    tasks: [],
    selectedTask: null,
    doneExpanded: false,
    search: "",
    tag: "",
    project: readStorage("flowboard-last-project"),
    projects: readStoredProjects(),
    quickTaskType: "",
    taskTagInputExpanded: false,
    focusTaskId: Number(readStorage("flowboard-focus-task", "0")) || null,
    density: readStorage("flowboard-density", "comfortable") === "compact" ? "compact" : "comfortable",
    dragOrigin: null,
    wipLimit: 3,
    maxFileSizeMb: 20,
    previewVisible: false,
    resultPreviewVisible: true,
    activeTaskTab: "description",
    previewRequest: 0,
    resultPreviewRequest: 0,
    draftSaveTimer: null,
    draftSavePromise: null,
    attachmentPreviewUrl: null,
    attachmentPreviewToken: 0,
  };
  state.columnPreferences = readColumnPreferences();
  state.archivedTasks = [];
  state.archiveSettings = { archive_enabled: true, archive_after_days: 30 };
  state.taskSettings = { require_result_to_close: false };
  state.archiveFilters = { search: "", project: "", tag: "", period: "" };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const els = {
    quickForm: $("#quick-add-form"),
    quickTitle: $("#quick-title"),
    quickTaskType: $("#quick-task-type"),
    search: $("#search-input"),
    searchShortcut: $("#search-shortcut"),
    projectFilter: $("#project-filter"),
    addProject: $("#add-project"),
    tagFilter: $("#tag-filter"),
    focusBar: $("#focus-bar"),
    focusTitle: $("#focus-title"),
    focusProject: $("#focus-project"),
    focusOpen: $("#focus-open"),
    focusDone: $("#focus-done"),
    focusClear: $("#focus-clear"),
    importButton: $("#import-button"),
    importFiles: $("#import-files"),
    exportMd: $("#export-md"),
    exportZip: $("#export-zip"),
    panel: $("#task-panel"),
    overlay: $("#panel-overlay"),
    closePanel: $("#close-panel"),
    taskForm: $("#task-form"),
    taskId: $("#panel-task-id"),
    taskTitle: $("#task-title"),
    taskTitleDisplay: $("#task-title-display"),
    taskTitleDisplayText: $("#task-title-display-text"),
    taskTitleReference: $("#panel-task-reference"),
    taskStatus: $("#task-status"),
    taskTags: $("#task-tags"),
    taskTagList: $("#task-tag-list"),
    taskTagInput: $("#task-tag-input"),
    taskTagCreateRow: $("#task-tag-create-row"),
    taskTagCustomToggle: $("#task-tag-custom-toggle"),
    addTaskTag: $("#add-task-tag"),
    taskDescription: $("#task-description"),
    taskResult: $("#task-result"),
    taskDescriptionTab: $("#task-description-tab"),
    taskResultTab: $("#task-result-tab"),
    taskDescriptionPanel: $("#task-description-panel"),
    taskResultPanel: $("#task-result-panel"),
    taskResultIndicator: $("#task-result-indicator"),
    taskWorkspaceTitle: $("#task-workspace-title"),
    taskWorkspaceHelper: $("#task-workspace-helper"),
    copyDescription: $("#copy-description"),
    descriptionPreview: $("#description-preview"),
    resultPreview: $("#result-preview"),
    togglePreview: $("#toggle-preview"),
    toggleAttachmentUpload: $("#toggle-attachment-upload"),
    taskMoreToggle: $("#task-more-toggle"),
    taskMoreMenu: $("#task-more-menu"),
    taskAutosaveStatus: $("#task-autosave-status"),
    taskAutosaveStatusText: $("#task-autosave-status-text"),
    closeTask: $("#close-task"),
    deleteTask: $("#delete-task"),
    exportTask: $("#export-task"),
    focusTask: $("#focus-task"),
    attachmentInput: $("#attachment-files"),
    chooseFiles: $("#choose-files"),
    attachmentDropzone: $("#attachment-dropzone"),
    attachmentList: $("#attachment-list"),
    attachmentCount: $("#attachment-count"),
    attachmentPreviewDialog: $("#attachment-preview-dialog"),
    attachmentPreviewTitle: $("#attachment-preview-title"),
    attachmentPreviewImage: $("#attachment-preview-image"),
    attachmentPreviewLoading: $("#attachment-preview-loading"),
    attachmentPreviewError: $("#attachment-preview-error"),
    attachmentPreviewDownload: $("#attachment-preview-download"),
    attachmentPreviewClose: $("#attachment-preview-close"),
    maxFileMb: $("#max-file-mb"),
    taskMeta: $("#task-meta"),
    toastRegion: $("#toast-region"),
    toggleDone: $("#toggle-done"),
    wipWarning: $("#wip-warning"),
    themeToggle: $("#theme-toggle"),
    themeToggleIcon: $("#theme-toggle-icon"),
    themeToggleLabel: $("#theme-toggle-label"),
    themeColor: $("meta[name=\"theme-color\"]"),
    importThemeButton: $("#import-theme-button"),
    exportThemeButton: $("#export-theme-button"),
    resetThemeButton: $("#reset-theme-button"),
    savedThemesSelect: $("#saved-themes-select"),
    deleteThemeButton: $("#delete-theme-button"),
    themeImportFile: $("#theme-import-file"),
    customThemeStatus: $("#custom-theme-status"),
    densityToggle: $("#density-toggle"),
    densityToggleLabel: $("#density-toggle-label"),
    shortcutsButton: $("#shortcuts-button"),
    shortcutsDialog: $("#shortcuts-dialog"),
    closeShortcuts: $("#close-shortcuts"),
    projectDialog: $("#project-dialog"),
    closeProjectDialog: $("#close-project-dialog"),
    projectCommandSearch: $("#project-command-search"),
    projectCommandList: $("#project-command-list"),
  };
  Object.assign(els, {
    archiveOpen: $("#open-archive"),
    archiveDialog: $("#archive-dialog"),
    archiveClose: $("#close-archive"),
    archiveAutoEnabled: $("#archive-auto-enabled"),
    requireResultToClose: $("#require-result-to-close"),
    archiveAfterDays: $("#archive-after-days"),
    archiveSearch: $("#archive-search"),
    archiveProjectFilter: $("#archive-project-filter"),
    archiveTagFilter: $("#archive-tag-filter"),
    archivePeriodFilter: $("#archive-period-filter"),
    archiveCompleteNow: $("#archive-completed-now"),
    archiveCount: $("#archive-count"),
    archiveList: $("#archive-list"),
    archiveEmpty: $("#archive-empty"),
    archiveTask: $("#archive-task"),
    columnOptionsToggles: $$("[data-column-options-toggle]"),
  });

  const shortcutPlatform = navigator.userAgentData?.platform || navigator.platform || "";
  const isApplePlatform = /mac|iphone|ipad|ipod/i.test(shortcutPlatform);
  if (els.searchShortcut) {
    els.searchShortcut.textContent = isApplePlatform ? "⌘ K" : "Ctrl K";
    els.searchShortcut.setAttribute(
      "aria-label",
      isApplePlatform ? "Поиск — Command K" : "Поиск — Control K",
    );
  }

  function applyTheme(theme, persist = false) {
    const normalizedTheme = theme === "dark" ? "dark" : "light";
    const isDark = normalizedTheme === "dark";
    document.documentElement.dataset.theme = normalizedTheme;
    window.FlowboardThemeManager?.applyCurrentPalette();
    els.themeToggle.setAttribute("aria-pressed", String(isDark));
    els.themeToggle.setAttribute(
      "aria-label",
      `Переключить на ${isDark ? "светлую" : "тёмную"} тему`,
    );
    els.themeToggle.title = `Переключить на ${isDark ? "светлую" : "тёмную"} тему`;
    els.themeToggleLabel.textContent = `Тема: ${isDark ? "Тёмная" : "Светлая"}`;
    const pageColor = getComputedStyle(document.documentElement).getPropertyValue("--page").trim();
    els.themeColor.setAttribute("content", pageColor || (isDark ? "#0c101a" : "#f4f6fb"));

    if (persist) {
      try {
        localStorage.setItem("flowboard-theme", normalizedTheme);
      } catch {
        // Theme switching still works for this page when storage is unavailable.
      }
    }
  }

  function toggleTheme() {
    const currentTheme = document.documentElement.dataset.theme;
    applyTheme(currentTheme === "dark" ? "light" : "dark", true);
  }

  function updateThemeManagerControls() {
    const manager = window.FlowboardThemeManager;
    if (!manager) return;

    const themes = manager.getThemes();
    const activeId = manager.getActiveThemeId();
    const selectedValue = activeId || "builtin";
    const options = [document.createElement("option"), ...themes.map(() => document.createElement("option"))];
    options[0].value = "builtin";
    options[0].textContent = "Стандартная палитра Flowboard";
    themes.forEach((theme, index) => {
      options[index + 1].value = theme.id;
      options[index + 1].textContent = theme.name;
    });
    els.savedThemesSelect.replaceChildren(...options);
    els.savedThemesSelect.value = selectedValue;

    const hasCustomTheme = selectedValue !== "builtin";
    const themeName = manager.getCustomThemeName() || "";
    els.resetThemeButton.disabled = !hasCustomTheme;
    els.deleteThemeButton.disabled = !hasCustomTheme;
    els.customThemeStatus.textContent = hasCustomTheme
      ? `Активна пользовательская тема. Сохранено тем: ${themes.length}`
      : `Активна встроенная тема. Сохранено тем: ${themes.length}`;
  }

  function applyDensity(density, persist = false) {
    state.density = density === "compact" ? "compact" : "comfortable";
    document.documentElement.dataset.density = state.density;
    const compact = state.density === "compact";
    els.densityToggle.setAttribute("aria-pressed", String(compact));
    els.densityToggle.setAttribute("aria-label", compact ? "Включить комфортные карточки" : "Включить компактные карточки");
    els.densityToggle.title = compact ? "Включить комфортную плотность карточек" : "Включить компактную плотность карточек";
    els.densityToggleLabel.textContent = compact ? "Плотность: компактная" : "Плотность: комфортная";
    if (persist) writeStorage("flowboard-density", state.density);
  }

  function toggleDensity() {
    applyDensity(state.density === "compact" ? "comfortable" : "compact", true);
  }

  async function api(url, options = {}) {
    const request = { ...options, cache: "no-store", headers: { ...(options.headers || {}) } };
    if (request.body && !(request.body instanceof FormData) && typeof request.body !== "string") {
      request.headers["Content-Type"] = "application/json";
      request.body = JSON.stringify(request.body);
    }
    const response = await fetch(url, request);
    if (response.status === 204) return null;
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      const message = typeof data === "object" && data !== null ? data.detail : data;
      const errorMessage = Array.isArray(message)
        ? message.map((entry) => entry.msg || String(entry)).join("; ")
        : (message || `Ошибка ${response.status}`);
      if (response.status === 409 && String(errorMessage).includes("Результат выполнения")) {
        const match = String(url).match(/^\/api\/tasks\/(\d+)/);
        if (match) void focusResultField(Number(match[1]));
      }
      throw new Error(errorMessage);
    }
    return data;
  }

  async function focusResultField(taskId) {
    if (state.selectedTask?.id === taskId) {
      if (els.taskStatus) els.taskStatus.value = state.selectedTask.status;
      els.taskResult.focus({ preventScroll: true });
      return;
    }
    if (state.selectedTask && !(await saveCurrentTaskDraft())) return;
    await openTaskPanel(taskId);
    if (state.selectedTask?.id === taskId) els.taskResult.focus({ preventScroll: true });
  }

  function toast(message, type = "success", actionLabel = "", onAction = null) {
    $$(".toast[data-has-undo=\"true\"]", els.toastRegion).forEach((node) => node.remove());
    const node = make("div", `toast${type === "error" ? " error" : ""}`);
    node.setAttribute("role", type === "error" ? "alert" : "status");
    node.setAttribute("aria-live", type === "error" ? "assertive" : "polite");
    if (actionLabel && typeof onAction === "function") node.dataset.hasUndo = "true";
    const messageNode = make("span", "toast-message", message);
    node.appendChild(messageNode);
    let timer = null;
    const dismiss = () => {
      if (timer !== null) window.clearTimeout(timer);
      node.remove();
    };
    if (actionLabel && typeof onAction === "function") {
      const action = make("button", "toast-action", actionLabel);
      action.type = "button";
      action.addEventListener("click", async () => {
        action.disabled = true;
        if (timer !== null) window.clearTimeout(timer);
        try {
          await onAction();
        } catch (error) {
          toast(`Не удалось отменить действие: ${error.message}`, "error");
        } finally {
          node.remove();
        }
      });
      node.appendChild(action);
    }
    const closeButton = make("button", "toast-close", "×");
    closeButton.type = "button";
    closeButton.setAttribute("aria-label", "Закрыть уведомление");
    closeButton.addEventListener("click", dismiss);
    node.appendChild(closeButton);
    els.toastRegion.appendChild(node);
    timer = window.setTimeout(dismiss, actionLabel ? 8500 : 4200);
  }

  function pluralAttachments(count) {
    const n = Math.abs(count) % 100;
    const n1 = n % 10;
    if (n > 10 && n < 20) return "вложений";
    if (n1 > 1 && n1 < 5) return "вложения";
    if (n1 === 1) return "вложение";
    return "вложений";
  }

  function pluralTasks(count) {
    const n = Math.abs(count) % 100;
    const n1 = n % 10;
    if (n > 10 && n < 20) return `${count} задач`;
    if (n1 > 1 && n1 < 5) return `${count} задачи`;
    if (n1 === 1) return `${count} задача`;
    return `${count} задач`;
  }

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    const now = new Date();
    if (date.toDateString() === now.toDateString()) return "сегодня";
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    if (date.toDateString() === yesterday.toDateString()) return "вчера";
    return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "short" }).format(date).replace(" г.", "");
  }

  function formatDateTime(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(date);
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} Б`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} КБ`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
  }

  function taskTags(task) {
    return String(task.tags || "").split(",").map((tag) => tag.trim()).filter(Boolean);
  }

  function normalizeSearch(value) {
    return String(value || "").toLocaleLowerCase("ru").replace(/ё/g, "е").trim();
  }

  function projectFromTag(tag) {
    const match = /^project:([a-z0-9]+(?:-[a-z0-9]+)*)$/i.exec(String(tag).trim());
    return match ? match[1].toLowerCase() : "";
  }

  function projectTag(slug) {
    return `project:${slug}`;
  }

  function projectLabel(slug) {
    return String(slug || "")
      .split(/[-_]+/)
      .filter(Boolean)
      .map((part) => part.charAt(0).toLocaleUpperCase("ru") + part.slice(1))
      .join(" ");
  }

  function projectForTask(task) {
    const tag = taskTags(task).find((value) => projectFromTag(value));
    return tag ? projectFromTag(tag) : "";
  }

  function persistProjectState() {
    writeStorage("flowboard-projects", JSON.stringify(state.projects));
    writeStorage("flowboard-last-project", state.project);
  }

  function renderProjectCommands(query = "") {
    const normalizedQuery = normalizeSearch(query);
    const projects = [{ slug: "", label: "Все проекты" }, ...state.projects.map((slug) => ({ slug, label: projectLabel(slug) }))]
      .filter((project) => !normalizedQuery || normalizeSearch(project.label).includes(normalizedQuery) || normalizeSearch(project.slug).includes(normalizedQuery));
    els.projectCommandList.replaceChildren();
    if (!projects.length) {
      els.projectCommandList.appendChild(make("p", "project-command-empty", "Проектов не найдено"));
      return;
    }
    projects.forEach((project) => {
      const button = make("button", "project-command-option");
      button.type = "button";
      button.textContent = project.label;
      button.setAttribute("aria-current", String(project.slug === state.project));
      button.appendChild(make("span", "project-command-mark", project.slug === state.project ? "✓" : "↵"));
      button.addEventListener("click", () => {
        state.project = project.slug;
        els.projectFilter.value = project.slug;
        persistProjectState();
        renderBoard();
        els.projectDialog.close();
        els.quickTitle.focus();
      });
      els.projectCommandList.appendChild(button);
    });
  }

  function openProjectDialog() {
    renderProjectCommands("");
    els.projectCommandSearch.value = "";
    els.projectDialog.showModal();
    window.setTimeout(() => els.projectCommandSearch.focus(), 0);
  }

  function populateProjectFilter() {
    const detected = state.tasks.flatMap(taskTags).map(projectFromTag).filter(Boolean);
    state.projects = [...new Set([...state.projects, ...detected])].sort((a, b) => a.localeCompare(b, "ru"));
    els.projectFilter.replaceChildren(new Option("Все проекты", ""));
    state.projects.forEach((slug) => els.projectFilter.appendChild(new Option(projectLabel(slug), slug)));
    if (!state.projects.includes(state.project)) state.project = "";
    els.projectFilter.value = state.project;
    persistProjectState();
  }

  function populateTagFilter() {
    const existingValue = state.tag;
    const tags = [...new Set(state.tasks.flatMap(taskTags).filter((tag) => !projectFromTag(tag)))].sort((a, b) => a.localeCompare(b, "ru"));
    els.tagFilter.replaceChildren();
    els.tagFilter.appendChild(new Option("Все теги", ""));
    tags.forEach((tag) => els.tagFilter.appendChild(new Option(tag, tag)));
    els.tagFilter.value = tags.includes(existingValue) ? existingValue : "";
    state.tag = els.tagFilter.value;
  }

  function matchesFilters(task) {
    const query = normalizeSearch(state.search);
    const terms = query ? query.split(/\s+/).filter(Boolean) : [];
    const searchable = normalizeSearch([task.title, task.description, ...taskTags(task)].join(" "));
    if (terms.some((term) => !searchable.includes(term))) return false;
    if (state.tag && !taskTags(task).includes(state.tag)) return false;
    if (state.project && !taskTags(task).some((tag) => projectFromTag(tag) === state.project)) return false;
    return true;
  }

  function make(tagName, className, text) {
    const node = document.createElement(tagName);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  const TASK_TYPE_LABELS = {
    bug: "Ошибка",
    feature: "Функция",
    docs: "Документация",
    refactor: "Рефакторинг",
  };
  const PROJECT_ACCENT_KEYS = [
    "--project-accent-1",
    "--project-accent-2",
    "--project-accent-3",
    "--project-accent-4",
    "--project-accent-5",
    "--project-accent-6",
  ];

  function setQuickTaskType(type) {
    const normalizedType = String(type || "").toLowerCase();
    state.quickTaskType = Object.hasOwn(TASK_TYPE_LABELS, normalizedType) ? normalizedType : "";
    $$("[data-task-type]", els.quickTaskType).forEach((button) => {
      const selected = button.dataset.taskType === state.quickTaskType;
      button.setAttribute("aria-pressed", String(selected));
    });
  }

  function taskDescriptionExcerpt(description, title = "", limit = 112) {
    const source = String(description || "").replace(/\r\n?/g, "\n");
    const lines = source.split("\n");
    const firstLine = lines[0].trim().replace(/^#{1,6}\s+/, "");
    const duplicateTitle = firstLine.match(/^Задача:\s*(.+?)\s*$/i);
    const normalizeTitle = (value) => value.replace(/\s+/g, " ").trim().toLocaleLowerCase().replace(/ё/g, "е");
    if (duplicateTitle && normalizeTitle(duplicateTitle[1]) === normalizeTitle(String(title || ""))) {
      lines.shift();
    }

    const plainText = lines.join("\n")
      // Keep code contents; remove only the Markdown fences around fenced blocks.
      .replace(/^\s{0,3}(```+|~~~+)[^\n]*$/gm, "")
      .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
      .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
      // Markdown markers are removed only in their syntactic positions.
      .replace(/^\s{0,3}#{1,6}\s+/gm, "")
      .replace(/^\s{0,3}>\s?/gm, "")
      .replace(/^\s{0,3}(?:[-+*]|\d+[.)])\s+/gm, "")
      .replace(/\*\*(.*?)\*\*/gs, "$1")
      .replace(/__(.*?)__/gs, "$1")
      .replace(/\*(.*?)\*/gs, "$1")
      .replace(/~~(.*?)~~/gs, "$1")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\s+/g, " ")
      .trim();
    if (!plainText) return "";
    return plainText.length > limit ? `${plainText.slice(0, limit - 1).trimEnd()}…` : plainText;
  }

  function projectAccent(slug) {
    let hash = 0;
    for (const char of String(slug || "")) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
    const key = PROJECT_ACCENT_KEYS[hash % PROJECT_ACCENT_KEYS.length];
    return getComputedStyle(document.documentElement).getPropertyValue(key).trim() || "var(--line-strong)";
  }

  function makeTaskCard(task) {
    const card = make("article", `task-card${task.status === "done" ? " done-card" : ""}${state.focusTaskId === task.id ? " is-focused" : ""}`);
    card.dataset.taskId = String(task.id);
    card.dataset.position = String(task.position);
    card.draggable = true;
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-label", `Открыть задачу: ${task.title}`);

    const tags = taskTags(task);
    const project = projectForTask(task);
    const typeTag = tags.find((tag) => Object.hasOwn(TASK_TYPE_LABELS, tag.toLowerCase()));
    const hiddenTags = tags.filter((tag) => !projectFromTag(tag) && (!typeTag || tag !== typeTag));

    const top = make("div", "task-card-top");
    top.appendChild(make("div", "task-card-title", task.title));
    top.appendChild(make("span", "task-open-hint", "↗"));
    card.appendChild(top);

    // The title leads; the short description provides meaning before metadata.
    const excerpt = taskDescriptionExcerpt(task.description, task.title);
    if (excerpt) card.appendChild(make("p", "task-card-excerpt", excerpt));

    // Do not render an empty metadata row or a placeholder for a missing project.
    if ((project && project !== state.project) || typeTag) {
      const metadata = make("div", "task-card-meta");
      // The selected project is already clear from the board filter context.
      if (project && project !== state.project) {
        const projectChip = make("span", "task-project-chip");
        const projectMark = make("span", "task-project-mark");
        projectMark.style.backgroundColor = projectAccent(project);
        projectChip.appendChild(projectMark);
        projectChip.appendChild(make("span", "task-project-name", projectLabel(project)));
        metadata.appendChild(projectChip);
      }
      if (typeTag) {
        metadata.appendChild(make("span", `task-type-chip task-type-${typeTag.toLowerCase()}`, TASK_TYPE_LABELS[typeTag.toLowerCase()]));
      }
      card.appendChild(metadata);
    }

    if (hiddenTags.length) {
      const tagRow = make("div", "task-tags");
      hiddenTags.slice(0, 2).forEach((tag) => tagRow.appendChild(make("span", "tag-pill", tag)));
      if (hiddenTags.length > 2) tagRow.appendChild(make("span", "tag-pill tag-pill-more", `+${hiddenTags.length - 2}`));
      card.appendChild(tagRow);
    }

    const footer = make("div", "task-card-footer");
    const updated = make("time", "task-updated", formatDate(task.updated_at));
    const updatedDateTime = formatDateTime(task.updated_at);
    updated.dateTime = task.updated_at || "";
    updated.title = `Последнее изменение: ${updatedDateTime}`;
    updated.setAttribute("aria-label", `Последнее изменение: ${updatedDateTime}`);
    footer.appendChild(updated);
    if (task.attachments_count) {
      const metrics = make("span", "task-card-metrics");
      const attachment = make("span", "attachment-mini");
      attachment.setAttribute("role", "img");
      const attachmentIcon = make("span", "attachment-mini-icon", "📎");
      attachmentIcon.setAttribute("aria-hidden", "true");
      attachment.appendChild(attachmentIcon);
      attachment.appendChild(make("span", "attachment-mini-count", String(task.attachments_count)));
      attachment.setAttribute("aria-label", `${task.attachments_count} ${pluralAttachments(task.attachments_count)}`);
      metrics.appendChild(attachment);
      footer.appendChild(metrics);
    }
    card.appendChild(footer);
    card.addEventListener("click", (event) => {
      if (event.target.closest("button, a")) return;
      openTaskPanel(task.id);
    });
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openTaskPanel(task.id);
      }
    });
    return card;
  }

  function columnTagLabel(tag) {
    const normalized = String(tag || "").toLowerCase();
    return Object.hasOwn(TASK_TYPE_LABELS, normalized) ? `Тип: ${TASK_TYPE_LABELS[normalized]}` : tag;
  }

  function persistColumnPreferences() {
    writeStorage("flowboard-column-preferences", JSON.stringify(state.columnPreferences));
  }

  function populateColumnFilters() {
    const tags = [...new Set(state.tasks.flatMap(taskTags).filter((tag) => !projectFromTag(tag)))]
      .sort((a, b) => a.localeCompare(b, "ru"));
    STATUSES.forEach((status) => {
      const select = $(`[data-column-filter="${status}"]`);
      if (!select) return;
      const current = state.columnPreferences[status].tag;
      select.replaceChildren(new Option("Все теги и типы", ""));
      tags.forEach((tag) => select.appendChild(new Option(columnTagLabel(tag), tag)));
      state.columnPreferences[status].tag = tags.includes(current) ? current : "";
      select.value = state.columnPreferences[status].tag;
      const sorter = $(`[data-column-sort="${status}"]`);
      if (sorter) sorter.value = state.columnPreferences[status].sort;
      const toggle = $(`[data-column-options-toggle="${status}"]`);
      if (toggle) toggle.classList.toggle("has-column-filter", Boolean(state.columnPreferences[status].tag));
    });
    persistColumnPreferences();
  }

  function compareDateValues(left, right, key) {
    const leftTime = Date.parse(left[key] || "") || 0;
    const rightTime = Date.parse(right[key] || "") || 0;
    return leftTime - rightTime;
  }

  function taskTypePriority(task) {
    const tags = taskTags(task).map((tag) => tag.toLowerCase());
    const order = ["bug", "feature", "docs", "refactor"];
    const index = order.findIndex((type) => tags.includes(type));
    return index < 0 ? order.length : index;
  }

  function sortColumnTasks(tasks, mode) {
    const sorted = [...tasks];
    const byPosition = (a, b) => Number(a.position) - Number(b.position) || Number(a.id) - Number(b.id);
    sorted.sort((a, b) => {
      if (mode === "manual") return byPosition(a, b);
      if (mode === "created_desc") return -compareDateValues(a, b, "created_at") || Number(b.id) - Number(a.id);
      if (mode === "created_asc") return compareDateValues(a, b, "created_at") || Number(a.id) - Number(b.id);
      if (mode === "updated_desc") return -compareDateValues(a, b, "updated_at") || Number(b.id) - Number(a.id);
      if (mode === "updated_asc") return compareDateValues(a, b, "updated_at") || Number(a.id) - Number(b.id);
      if (mode === "closed_desc") return -compareDateValues(
        { closed_at: a.closed_at || a.updated_at },
        { closed_at: b.closed_at || b.updated_at },
        "closed_at",
      ) || Number(b.id) - Number(a.id);
      if (mode === "type") return taskTypePriority(a) - taskTypePriority(b)
        || a.title.localeCompare(b.title, "ru");
      if (mode === "title_asc") return a.title.localeCompare(b.title, "ru");
      return byPosition(a, b);
    });
    return sorted;
  }

  function syncFocusedTask() {
    if (state.focusTaskId === null) return;
    const focusedTask = state.tasks.find((item) => item.id === state.focusTaskId);
    if (focusedTask && focusedTask.status !== "done") return;
    state.focusTaskId = null;
    writeStorage("flowboard-focus-task", "");
  }

  function renderBoard() {
    syncFocusedTask();
    const visibleTasks = state.tasks.filter(matchesFilters);
    const doingCount = state.tasks.filter((task) => task.status === "doing").length;

    for (const status of STATUSES) {
      const column = $(`.board-column[data-column="${status}"]`);
      const list = $(`.task-list[data-status="${status}"]`);
      let statusTasks = visibleTasks.filter((task) => task.status === status);
      const preference = state.columnPreferences[status];
      if (preference.tag) statusTasks = statusTasks.filter((task) => taskTags(task).includes(preference.tag));
      statusTasks = sortColumnTasks(statusTasks, preference.sort);
      $(`#count-${status}`).textContent = String(statusTasks.length);
      list.dataset.sortMode = preference.sort;
      list.replaceChildren();

      let tasksToRender = statusTasks;
      if (status === "done" && doneColumnCollapseQuery.matches && !state.doneExpanded) {
        tasksToRender = statusTasks.slice(0, 5);
      }

      if (status === "done") {
        const canCollapseDone = doneColumnCollapseQuery.matches && statusTasks.length > 5;
        const isExpanded = canCollapseDone && state.doneExpanded;
        const label = isExpanded
          ? "Свернуть список завершённых задач"
          : "Показать остальные завершённые задачи";
        els.toggleDone.hidden = !canCollapseDone;
        els.toggleDone.setAttribute("aria-label", label);
        els.toggleDone.title = label;
        els.toggleDone.setAttribute("aria-expanded", String(isExpanded));
      }

      tasksToRender.forEach((task) => list.appendChild(makeTaskCard(task)));
      column.classList.toggle("is-empty", tasksToRender.length === 0);
      column.classList.toggle("has-column-filter", Boolean(preference.tag));
    }

    const overLimit = doingCount > state.wipLimit;
    $(".board-column[data-column='doing']").classList.toggle("wip-over-limit", overLimit);
    els.wipWarning.hidden = !overLimit;
    renderFocusBar();
  }

  function updateTaskFocusButton() {
    const isFocused = Boolean(state.selectedTask && state.selectedTask.id === state.focusTaskId);
    els.focusTask.setAttribute("aria-pressed", String(isFocused));
    els.focusTask.setAttribute("aria-label", isFocused ? "Снять задачу с фокуса" : "Добавить задачу в фокус");
    els.focusTask.title = isFocused ? "Снять с фокуса" : "Добавить в фокус";
  }

  function renderFocusBar() {
    const task = state.tasks.find((item) => item.id === state.focusTaskId);
    if (!task || task.status === "done") {
      if (state.focusTaskId !== null) {
        state.focusTaskId = null;
        writeStorage("flowboard-focus-task", "");
      }
      els.focusBar.hidden = true;
      updateTaskFocusButton();
      return;
    }
    els.focusBar.hidden = false;
    els.focusTitle.textContent = task.title;
    const project = projectForTask(task);
    els.focusProject.textContent = project ? `${projectLabel(project)} · ${STATUS_LABELS[task.status]}` : STATUS_LABELS[task.status];
    els.focusDone.disabled = task.status === "done";
    els.focusDone.textContent = task.status === "done" ? "Уже готово" : "Завершить";
    if (state.selectedTask && state.selectedTask.id === task.id) updateTaskFocusButton();
  }

  function setFocusedTask(taskId) {
    state.focusTaskId = taskId || null;
    writeStorage("flowboard-focus-task", state.focusTaskId ? String(state.focusTaskId) : "");
    renderBoard();
    if (state.selectedTask) {
      updateTaskFocusButton();
    }
  }

  function clearFocus() {
    setFocusedTask(null);
    toast("Фокус снят");
  }

  async function loadTasks() {
    state.tasks = await api("/api/tasks");
    populateProjectFilter();
    populateTagFilter();
    populateColumnFilters();
    renderBoard();
  }

  function populateArchiveFilters() {
    const projects = [...new Set(state.archivedTasks.flatMap(taskTags).map(projectFromTag).filter(Boolean))]
      .sort((a, b) => a.localeCompare(b, "ru"));
    const tags = [...new Set(state.archivedTasks.flatMap(taskTags).filter((tag) => !projectFromTag(tag)))]
      .sort((a, b) => a.localeCompare(b, "ru"));
    const selectedProject = state.archiveFilters.project;
    const selectedTag = state.archiveFilters.tag;
    els.archiveProjectFilter.replaceChildren(new Option("Все проекты", ""));
    projects.forEach((slug) => els.archiveProjectFilter.appendChild(new Option(projectLabel(slug), slug)));
    els.archiveTagFilter.replaceChildren(new Option("Все теги", ""));
    tags.forEach((tag) => els.archiveTagFilter.appendChild(new Option(columnTagLabel(tag), tag)));
    state.archiveFilters.project = projects.includes(selectedProject) ? selectedProject : "";
    state.archiveFilters.tag = tags.includes(selectedTag) ? selectedTag : "";
    els.archiveProjectFilter.value = state.archiveFilters.project;
    els.archiveTagFilter.value = state.archiveFilters.tag;
  }

  function renderArchive() {
    const query = normalizeSearch(state.archiveFilters.search);
    const terms = query ? query.split(/\s+/).filter(Boolean) : [];
    const filtered = state.archivedTasks.filter((task) => {
      const tags = taskTags(task);
      const searchable = normalizeSearch([task.title, task.description, ...tags].join(" "));
      if (terms.some((term) => !searchable.includes(term))) return false;
      if (state.archiveFilters.project && !tags.some((tag) => projectFromTag(tag) === state.archiveFilters.project)) return false;
      if (state.archiveFilters.tag && !tags.includes(state.archiveFilters.tag)) return false;
      if (state.archiveFilters.period) {
        const archivedAt = Date.parse(task.archived_at || "");
        const cutoff = Date.now() - Number(state.archiveFilters.period) * 24 * 60 * 60 * 1000;
        if (!archivedAt || archivedAt < cutoff) return false;
      }
      return true;
    });
    els.archiveList.replaceChildren();
    els.archiveCount.textContent = state.archivedTasks.length === filtered.length
      ? `${pluralTasks(filtered.length)} в архиве`
      : `Показано ${filtered.length} из ${state.archivedTasks.length}`;
    els.archiveEmpty.hidden = filtered.length > 0;
    els.archiveEmpty.textContent = state.archivedTasks.length
      ? "По этим условиям задачи не найдены. Измените поиск или фильтры."
      : "В архиве пока нет задач.";

    filtered.forEach((task) => {
      const item = make("article", "archive-item");
      const copy = make("div", "archive-item-copy");
      const title = make("button", "archive-task-title", task.title);
      title.type = "button";
      title.addEventListener("click", () => {
        els.archiveDialog.close();
        void openTaskPanel(task.id);
      });
      copy.appendChild(title);
      const metadata = make("div", "archive-item-tags");
      const project = projectForTask(task);
      if (project) {
        const chip = make("span", "archive-chip archive-project-chip", projectLabel(project));
        chip.style.setProperty("--project-accent", projectAccent(project));
        metadata.appendChild(chip);
      }
      const taskType = taskTags(task).find((tag) => Object.hasOwn(TASK_TYPE_LABELS, tag.toLowerCase()));
      if (taskType) metadata.appendChild(make("span", `archive-chip task-type-${taskType.toLowerCase()}`, TASK_TYPE_LABELS[taskType.toLowerCase()]));
      const otherTags = taskTags(task).filter((tag) => !projectFromTag(tag) && tag !== taskType).slice(0, 3);
      otherTags.forEach((tag) => metadata.appendChild(make("span", "archive-chip", tag)));
      if (metadata.childElementCount) copy.appendChild(metadata);
      const dates = make("p", "archive-item-dates", `Завершена: ${formatDateTime(task.closed_at)} · В архиве: ${formatDateTime(task.archived_at)}`);
      copy.appendChild(dates);
      if (task.description) copy.appendChild(make("p", "archive-item-excerpt", taskDescriptionExcerpt(task.description, task.title, 180)));
      item.appendChild(copy);
      const restore = make("button", "button button-small button-quiet archive-restore", "↶ Восстановить");
      restore.type = "button";
      restore.addEventListener("click", () => { void restoreArchivedTask(task.id); });
      item.appendChild(restore);
      els.archiveList.appendChild(item);
    });
  }

  async function loadTaskSettings() {
    state.taskSettings = await api("/api/task-settings");
    els.requireResultToClose.checked = state.taskSettings.require_result_to_close;
  }

  async function saveTaskSettings() {
    const requested = { require_result_to_close: els.requireResultToClose.checked };
    try {
      state.taskSettings = await api("/api/task-settings", { method: "PATCH", body: requested });
      els.requireResultToClose.checked = state.taskSettings.require_result_to_close;
      toast(state.taskSettings.require_result_to_close
        ? "Для закрытия задачи теперь требуется результат выполнения"
        : "Обязательность результата перед закрытием отключена");
    } catch (error) {
      els.requireResultToClose.checked = state.taskSettings.require_result_to_close;
      toast(`Не удалось сохранить настройку задач: ${error.message}`, "error");
    }
  }

  async function loadArchiveSettings() {
    state.archiveSettings = await api("/api/archive/settings");
    els.archiveAutoEnabled.checked = state.archiveSettings.archive_enabled;
    els.archiveAfterDays.value = String(state.archiveSettings.archive_after_days);
    els.archiveAfterDays.disabled = !state.archiveSettings.archive_enabled;
  }

  async function loadArchivedTasks() {
    state.archivedTasks = await api("/api/archive/tasks");
    populateArchiveFilters();
    renderArchive();
  }

  async function openArchive() {
    if (!els.archiveDialog.open) els.archiveDialog.showModal();
    els.archiveCount.textContent = "Загрузка архива…";
    try {
      await Promise.all([loadArchiveSettings(), loadArchivedTasks()]);
      // Loading the archive can auto-archive overdue tasks; keep the board in sync.
      await loadTasks();
    } catch (error) {
      toast(`Не удалось загрузить архив: ${error.message}`, "error");
      els.archiveCount.textContent = "Не удалось загрузить архив";
    }
  }

  async function saveArchiveSettings() {
    const requested = {
      archive_enabled: els.archiveAutoEnabled.checked,
      archive_after_days: Number(els.archiveAfterDays.value),
    };
    try {
      state.archiveSettings = await api("/api/archive/settings", { method: "PATCH", body: requested });
      els.archiveAfterDays.disabled = !state.archiveSettings.archive_enabled;
      await loadTasks();
      await loadArchivedTasks();
      toast(state.archiveSettings.archive_enabled
        ? `Автоархивирование включено: через ${state.archiveSettings.archive_after_days} дней без изменений`
        : "Автоархивирование отключено");
    } catch (error) {
      toast(`Не удалось сохранить настройки архива: ${error.message}`, "error");
      els.archiveAutoEnabled.checked = state.archiveSettings.archive_enabled;
      els.archiveAfterDays.value = String(state.archiveSettings.archive_after_days);
      els.archiveAfterDays.disabled = !state.archiveSettings.archive_enabled;
    }
  }

  async function archiveCompletedTasks() {
    const confirmed = window.confirm("Переместить все задачи из колонки «Готово» в архив? Их можно будет восстановить позже.");
    if (!confirmed) return;
    try {
      const result = await api("/api/archive/completed", { method: "POST" });
      await loadTasks();
      if (els.archiveDialog.open) await loadArchivedTasks();
      toast(result.archived
        ? `В архив перемещено: ${pluralTasks(result.archived)}`
        : "В колонке «Готово» нет задач для архивирования");
    } catch (error) {
      toast(`Не удалось архивировать задачи: ${error.message}`, "error");
    }
  }

  async function archiveSingleTask(taskId) {
    try {
      if (typeof saveCurrentTaskDraft === "function" && !(await saveCurrentTaskDraft())) return;
      await api(`/api/archive/tasks/${taskId}`, { method: "POST" });
      if (state.selectedTask?.id === taskId) closePanel();
      await loadTasks();
      if (els.archiveDialog.open) await loadArchivedTasks();
      toast("Задача перемещена в архив", "success", "Восстановить", async () => {
        await api(`/api/archive/tasks/${taskId}/restore`, { method: "POST" });
        await loadTasks();
        if (els.archiveDialog.open) await loadArchivedTasks();
      });
    } catch (error) {
      toast(`Не удалось архивировать задачу: ${error.message}`, "error");
    }
  }

  async function restoreArchivedTask(taskId) {
    try {
      await api(`/api/archive/tasks/${taskId}/restore`, { method: "POST" });
      await loadTasks();
      await loadArchivedTasks();
      toast("Задача восстановлена на доске");
    } catch (error) {
      toast(`Не удалось восстановить задачу: ${error.message}`, "error");
    }
  }

  function openPanel() {
    els.overlay.hidden = false;
    els.panel.classList.add("is-open");
    els.panel.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function closePanel() {
    clearTaskDraftSaveTimer();
    closeAttachmentPreview();
    els.panel.classList.remove("is-open");
    els.panel.setAttribute("aria-hidden", "true");
    els.attachmentList.querySelectorAll(".attachment-preview").forEach((image) => {
      if (image.dataset.objectUrl) URL.revokeObjectURL(image.dataset.objectUrl);
    });
    els.overlay.hidden = true;
    document.body.style.overflow = "";
    state.selectedTask = null;
    state.previewVisible = false;
    state.resultPreviewVisible = true;
    setTaskWorkspaceTab("description");
    updateTaskResultIndicator();
    els.descriptionPreview.hidden = true;
    els.taskDescription.hidden = false;
    els.resultPreview.hidden = false;
    els.taskResult.hidden = true;
    els.togglePreview.textContent = "✎";
    els.togglePreview.setAttribute("aria-label", "Редактировать описание");
    els.togglePreview.title = "Редактировать описание";
    els.taskTitle.hidden = true;
    els.taskTitleDisplay.hidden = false;
    els.attachmentDropzone.hidden = true;
    els.toggleAttachmentUpload.setAttribute("aria-expanded", "false");
    els.toggleAttachmentUpload.setAttribute("aria-label", "Добавить вложение");
    els.toggleAttachmentUpload.title = "Добавить вложение";
    els.taskMoreMenu.hidden = true;
    els.taskMoreToggle.setAttribute("aria-expanded", "false");
    els.archiveTask.hidden = true;
  }

  async function openTaskPanel(taskId) {
    try {
      const task = await api(`/api/tasks/${taskId}`);
      state.selectedTask = task;
      els.taskId.value = String(task.id);
      els.taskTitle.value = task.title;
      els.taskTitleDisplayText.textContent = task.title || "Без названия";
      els.taskTitle.hidden = true;
      els.taskTitleDisplay.hidden = false;
      els.taskTitleReference.textContent = `#${task.id}`;
      els.taskStatus.value = task.status;
      els.taskTags.value = task.tags || "";
      state.taskTagInputExpanded = false;
      els.taskTagInput.value = "";
      renderTaskTagEditor();
      els.taskDescription.value = task.description || "";
      els.taskResult.value = task.result || "";
      state.resultPreviewVisible = true;
      setTaskWorkspaceTab("description");
      updateTaskResultIndicator();
      els.descriptionPreview.replaceChildren();
      els.resultPreview.replaceChildren();
      els.descriptionPreview.scrollTop = 0;
      els.resultPreview.scrollTop = 0;
      els.descriptionPreview.hidden = false;
      els.taskDescription.hidden = true;
      els.resultPreview.hidden = false;
      els.taskResult.hidden = true;
      els.togglePreview.textContent = "✎";
      els.togglePreview.setAttribute("aria-label", "Редактировать описание");
      els.togglePreview.title = "Редактировать описание";
      state.previewVisible = true;
      void requestResultMarkdownPreview();
      els.attachmentDropzone.hidden = true;
      els.toggleAttachmentUpload.setAttribute("aria-expanded", "false");
      els.toggleAttachmentUpload.setAttribute("aria-label", "Добавить вложение");
      els.toggleAttachmentUpload.title = "Добавить вложение";
      els.taskMoreMenu.hidden = true;
      els.taskMoreToggle.setAttribute("aria-expanded", "false");
      els.closeTask.textContent = task.status === "done" ? "↶ Вернуть в работу" : "✓ Закрыть задачу";
      els.closeTask.dataset.action = task.status === "done" ? "reopen" : "close";
      els.archiveTask.hidden = task.status !== "done" || Boolean(task.archived_at);
      els.taskMeta.textContent = `Создана: ${formatDateTime(task.created_at)} · Изменена: ${formatDateTime(task.updated_at)}${task.closed_at ? ` · Закрыта: ${formatDateTime(task.closed_at)}` : ""}`;
      renderAttachments(task.attachments || []);
      updateTaskFocusButton();
      setTaskAutosaveStatus("saved", "Все изменения сохранены");
      openPanel();
      void requestMarkdownPreview();
      window.setTimeout(() => els.taskTitleDisplay.focus({ preventScroll: true }), 100);
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function refreshSelectedTask() {
    const taskId = state.selectedTask?.id;
    if (!taskId) return;
    if (!(await saveCurrentTaskDraft())) return;
    if (state.selectedTask?.id === taskId) await openTaskPanel(taskId);
  }

  function clearTaskDraftSaveTimer() {
    if (state.draftSaveTimer !== null) {
      window.clearTimeout(state.draftSaveTimer);
      state.draftSaveTimer = null;
    }
  }

  function normalizedTaskTags(value) {
    return String(value || "")
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean)
      .join(", ");
  }

  function currentTaskDraft(task = state.selectedTask) {
    return {
      title: String(els.taskTitle.value || "").trim() || task?.title || "",
      status: els.taskStatus.value || task?.status || "todo",
      tags: editableTaskTags().join(", "),
      description: els.taskDescription.value,
      result: els.taskResult.value,
    };
  }

  function taskDraftMatches(draft, task) {
    return Boolean(task)
      && draft.title === task.title
      && draft.status === task.status
      && normalizedTaskTags(draft.tags) === normalizedTaskTags(task.tags)
      && draft.description === (task.description || "")
      && draft.result === (task.result || "");
  }

  function setTaskAutosaveStatus(status, message) {
    els.taskAutosaveStatus.dataset.state = status;
    els.taskAutosaveStatusText.textContent = message;
  }

  function scheduleTaskDraftSave(delay = 180) {
    if (!state.selectedTask) return;
    setTaskAutosaveStatus("pending", "Есть несохранённые изменения");
    clearTaskDraftSaveTimer();
    state.draftSaveTimer = window.setTimeout(() => {
      state.draftSaveTimer = null;
      void saveCurrentTaskDraft();
    }, delay);
  }

  async function saveCurrentTaskDraft() {
    clearTaskDraftSaveTimer();
    if (state.draftSavePromise) {
      const pending = state.draftSavePromise;
      const succeeded = await pending;
      if (!succeeded) return false;
      if (state.draftSavePromise === pending) state.draftSavePromise = null;
      return saveCurrentTaskDraft();
    }

    const task = state.selectedTask;
    if (!task) return true;
    const draft = currentTaskDraft(task);
    if (taskDraftMatches(draft, task)) {
      setTaskAutosaveStatus("saved", "Все изменения сохранены");
      return true;
    }
    setTaskAutosaveStatus("saving", "Сохраняем изменения…");
    const taskId = task.id;
    const previousDetails = {
      title: task.title,
      description: task.description || "",
      result: task.result || "",
      tags: task.tags || "",
      status: task.status,
      position: task.position,
    };

    const operation = (async () => {
      try {
        const updated = await api(`/api/tasks/${taskId}`, { method: "PATCH", body: draft });
        if (state.selectedTask?.id === taskId) {
          state.selectedTask = { ...state.selectedTask, ...updated };
          els.taskTitleDisplayText.textContent = updated.title || "Без названия";
          els.taskMeta.textContent = `Создана: ${formatDateTime(updated.created_at)} · Изменена: ${formatDateTime(updated.updated_at)}${updated.closed_at ? ` · Закрыта: ${formatDateTime(updated.closed_at)}` : ""}`;
          els.closeTask.textContent = updated.status === "done" ? "↶ Вернуть в работу" : "✓ Закрыть задачу";
          els.closeTask.dataset.action = updated.status === "done" ? "reopen" : "close";
        }
        state.tasks = state.tasks.map((entry) => entry.id === updated.id ? { ...entry, ...updated } : entry);
        populateProjectFilter();
        populateTagFilter();
        renderBoard();
        return true;
      } catch (error) {
        toast(`Не удалось автоматически сохранить изменения: ${error.message}`, "error");
        return false;
      }
    })();
    state.draftSavePromise = operation;
    const succeeded = await operation;
    if (state.draftSavePromise === operation) state.draftSavePromise = null;
    if (!succeeded) {
      if (state.selectedTask?.id === taskId) setTaskAutosaveStatus("error", "Не удалось сохранить изменения");
      return false;
    }

    // If the user changed a field while the request was in flight, save the newer draft too.
    if (state.selectedTask?.id === taskId && !taskDraftMatches(currentTaskDraft(), state.selectedTask)) {
      setTaskAutosaveStatus("pending", "Есть несохранённые изменения");
      const saved = await saveCurrentTaskDraft();
      toast("Изменения сохранены", "success", "Отменить", () => restoreTaskDetails(taskId, previousDetails));
      return saved;
    }
    if (state.selectedTask?.id === taskId) setTaskAutosaveStatus("saved", "Все изменения сохранены");
    toast("Изменения сохранены", "success", "Отменить", () => restoreTaskDetails(taskId, previousDetails));
    return true;
  }

  async function dismissTaskPanel() {
    if (!(await saveCurrentTaskDraft())) return;
    closePanel();
  }

  function editableTaskTags() {
    return [...new Set(String(els.taskTags.value || "")
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean))];
  }

  function tagChoiceDetails(value) {
    const tag = String(value || "").trim();
    const normalized = tag.toLocaleLowerCase("ru");
    if (Object.hasOwn(TASK_TYPE_LABELS, normalized)) {
      return { value: normalized, label: TASK_TYPE_LABELS[normalized], kind: "type" };
    }
    const project = projectFromTag(tag);
    if (project) {
      return { value: projectTag(project), label: `Проект: ${projectLabel(project)}`, kind: "project" };
    }
    return { value: tag, label: tag, kind: "custom" };
  }

  function availableTaskTagChoices() {
    const choices = new Map();
    const addChoice = (value) => {
      const detail = tagChoiceDetails(value);
      if (!detail.value) return;
      const key = detail.value.toLocaleLowerCase("ru");
      if (!choices.has(key)) choices.set(key, detail);
    };

    Object.keys(TASK_TYPE_LABELS).forEach(addChoice);
    state.projects.forEach((slug) => addChoice(projectTag(slug)));
    state.tasks.flatMap(taskTags).forEach(addChoice);
    editableTaskTags().forEach(addChoice);

    const kindOrder = { type: 0, project: 1, custom: 2 };
    const typeOrder = Object.keys(TASK_TYPE_LABELS);
    return [...choices.values()].sort((a, b) => {
      if (kindOrder[a.kind] !== kindOrder[b.kind]) return kindOrder[a.kind] - kindOrder[b.kind];
      if (a.kind === "type") return typeOrder.indexOf(a.value) - typeOrder.indexOf(b.value);
      return a.label.localeCompare(b.label, "ru");
    });
  }

  function renderTaskTagEditor() {
    const tags = editableTaskTags();
    const selected = new Set(tags.map((tag) => tag.toLocaleLowerCase("ru")));
    els.taskTags.value = tags.join(", ");
    els.taskTagList.replaceChildren();

    const choices = availableTaskTagChoices();
    const customChoicesExist = choices.some((choice) => choice.kind === "custom");
    choices.forEach((choice) => {
      const isSelected = selected.has(choice.value.toLocaleLowerCase("ru"));
      const option = make("button", `tag-choice tag-choice-${choice.kind}${choice.kind === "type" ? ` tag-choice-${choice.value}` : ""}`, choice.label);
      option.type = "button";
      option.dataset.tag = choice.value;
      option.setAttribute("aria-pressed", String(isSelected));
      option.setAttribute("aria-label", `${isSelected ? "Убрать" : "Добавить"} тег ${choice.label}`);
      option.title = `${isSelected ? "Убрать" : "Добавить"} тег «${choice.label}»`;
      option.addEventListener("click", () => toggleTaskTagChoice(choice.value));
      els.taskTagList.appendChild(option);
    });

    // Keep the editor compact when the workspace only uses reserved tags.
    els.taskTagCreateRow.hidden = !customChoicesExist && !state.taskTagInputExpanded;
    els.taskTagCustomToggle.hidden = customChoicesExist || state.taskTagInputExpanded;
  }

  function toggleTaskTagChoice(value) {
    const detail = tagChoiceDetails(value);
    const tags = editableTaskTags();
    const normalized = detail.value.toLocaleLowerCase("ru");
    const existingIndex = tags.findIndex((tag) => tag.toLocaleLowerCase("ru") === normalized);
    if (existingIndex >= 0) {
      tags.splice(existingIndex, 1);
    } else {
      tags.push(detail.value);
    }
    const combined = tags.join(", ");
    if (combined.length > 1000) {
      toast("Список тегов не должен превышать 1000 символов", "error");
      return;
    }
    els.taskTags.value = combined;
    renderTaskTagEditor();
    scheduleTaskDraftSave();
  }

  function addTaskTags(value = els.taskTagInput.value) {
    const incoming = String(value || "").split(",").map((tag) => tag.trim()).filter(Boolean);
    if (!incoming.length) return;
    const tags = editableTaskTags();
    const known = new Set(tags.map((tag) => tag.toLocaleLowerCase("ru")));
    for (const tag of incoming) {
      const normalized = tag.toLocaleLowerCase("ru");
      if (!known.has(normalized)) {
        tags.push(tag);
        known.add(normalized);
      }
    }
    const combined = tags.join(", ");
    if (combined.length > 1000) {
      toast("Список тегов не должен превышать 1000 символов", "error");
      return;
    }
    els.taskTags.value = combined;
    els.taskTagInput.value = "";
    renderTaskTagEditor();
    scheduleTaskDraftSave();
    els.taskTagInput.focus({ preventScroll: true });
  }

  function renderAttachments(attachments) {
    els.attachmentList.querySelectorAll(".attachment-preview").forEach((image) => {
      if (image.dataset.objectUrl) URL.revokeObjectURL(image.dataset.objectUrl);
    });
    els.attachmentList.replaceChildren();
    els.attachmentCount.textContent = String(attachments.length);
    if (!attachments.length) {
      els.attachmentList.appendChild(make("li", "attachment-empty", "Пока нет вложений. Нажмите «Добавить», чтобы прикрепить файл."));
    }
    attachments.forEach((attachment) => {
      const item = make("li", "attachment-item");
      const extension = attachment.filename.includes(".") ? attachment.filename.split(".").pop().toLowerCase() : "FILE";
      const isPreviewableImage = ["png", "jpg", "jpeg", "gif", "webp", "avif", "bmp", "svg"].includes(extension);
      const isImageAttachment = /^(?:apng|avif|bmp|gif|heic|heif|ico|icon|jpe?g|jfif|png|svg|tiff?|webp)$/i.test(extension);
      const details = make("span", "attachment-file-details");
      const fileDate = make("small", "", `${formatBytes(attachment.size)} · ${formatDate(attachment.created_at)}`);

      if (isPreviewableImage) {
        details.appendChild(make("span", "attachment-file-name", attachment.filename));
        details.appendChild(fileDate);
        const trigger = make("button", "attachment-preview-trigger");
        trigger.type = "button";
        trigger.setAttribute("aria-label", `Открыть предпросмотр изображения ${attachment.filename}`);
        trigger.title = `Открыть предпросмотр: ${attachment.filename}`;
        const preview = make("img", "attachment-preview");
        preview.alt = "";
        preview.loading = "lazy";
        trigger.appendChild(preview);
        trigger.appendChild(details);
        trigger.addEventListener("click", () => { void openAttachmentPreview(attachment); });
        item.appendChild(trigger);
        fetch(`/api/files/${attachment.id}`, { cache: "no-store" })
          .then((response) => {
            if (!response.ok) throw new Error("Не удалось загрузить предпросмотр");
            return response.blob();
          })
          .then((blob) => {
            if (!preview.isConnected) return;
            const objectUrl = URL.createObjectURL(blob);
            preview.dataset.objectUrl = objectUrl;
            preview.src = objectUrl;
          })
          .catch(() => { if (preview.isConnected) preview.remove(); });
        const download = make("a", "attachment-download", "↓");
        download.href = `/api/files/${attachment.id}`;
        download.download = attachment.filename;
        download.title = `Скачать ${attachment.filename}`;
        download.setAttribute("aria-label", `Скачать ${attachment.filename}`);
        item.appendChild(download);
      } else {
        const link = make("a", "", attachment.filename);
        link.href = `/api/files/${attachment.id}`;
        link.download = attachment.filename;
        link.title = "Скачать файл";
        details.appendChild(link);
        details.appendChild(fileDate);
        item.appendChild(make("span", "attachment-file-icon", extension.slice(0, 4) || "FILE"));
        item.appendChild(details);
      }

      const remove = make("button", "attachment-remove", "×");
      remove.type = "button";
      remove.setAttribute("aria-label", `Удалить вложение ${attachment.filename}`);
      remove.addEventListener("click", () => removeAttachment(attachment.id, attachment.filename, isImageAttachment));
      item.appendChild(remove);
      els.attachmentList.appendChild(item);
    });
  }

  function releaseAttachmentPreviewUrl() {
    if (state.attachmentPreviewUrl) {
      URL.revokeObjectURL(state.attachmentPreviewUrl);
      state.attachmentPreviewUrl = null;
    }
    els.attachmentPreviewImage.removeAttribute("src");
  }

  function closeAttachmentPreview() {
    state.attachmentPreviewToken += 1;
    if (els.attachmentPreviewDialog.open) els.attachmentPreviewDialog.close();
    releaseAttachmentPreviewUrl();
    els.attachmentPreviewImage.hidden = true;
    els.attachmentPreviewLoading.hidden = false;
    els.attachmentPreviewError.hidden = true;
  }

  async function openAttachmentPreview(attachment) {
    const token = ++state.attachmentPreviewToken;
    releaseAttachmentPreviewUrl();
    els.attachmentPreviewTitle.textContent = attachment.filename;
    els.attachmentPreviewDownload.href = `/api/files/${attachment.id}`;
    els.attachmentPreviewDownload.download = attachment.filename;
    els.attachmentPreviewDownload.setAttribute("aria-label", `Скачать ${attachment.filename}`);
    els.attachmentPreviewImage.alt = attachment.filename;
    els.attachmentPreviewImage.hidden = true;
    els.attachmentPreviewLoading.hidden = false;
    els.attachmentPreviewError.hidden = true;
    if (!els.attachmentPreviewDialog.open) els.attachmentPreviewDialog.showModal();

    try {
      const response = await fetch(`/api/files/${attachment.id}`, { cache: "no-store" });
      if (!response.ok) throw new Error("Не удалось загрузить изображение");
      const blob = await response.blob();
      if (token !== state.attachmentPreviewToken || !els.attachmentPreviewDialog.open) return;
      state.attachmentPreviewUrl = URL.createObjectURL(blob);
      els.attachmentPreviewImage.src = state.attachmentPreviewUrl;
      els.attachmentPreviewImage.hidden = false;
      els.attachmentPreviewLoading.hidden = true;
    } catch (error) {
      if (token !== state.attachmentPreviewToken || !els.attachmentPreviewDialog.open) return;
      els.attachmentPreviewLoading.hidden = true;
      els.attachmentPreviewError.textContent = `${error.message}. Можно скачать исходный файл кнопкой выше.`;
      els.attachmentPreviewError.hidden = false;
    }
  }

  async function requestMarkdownPreview() {
    const requestId = ++state.previewRequest;
    const taskId = state.selectedTask?.id;
    try {
      const result = await api("/api/preview-markdown", { method: "POST", body: { text: els.taskDescription.value } });
      if (requestId !== state.previewRequest || !state.previewVisible || state.selectedTask?.id !== taskId) return;
      els.descriptionPreview.innerHTML = result.html;
    } catch (error) {
      if (requestId === state.previewRequest) toast(`Не удалось построить предпросмотр: ${error.message}`, "error");
    }
  }

  async function requestResultMarkdownPreview() {
    const requestId = ++state.resultPreviewRequest;
    const taskId = state.selectedTask?.id;
    try {
      const result = await api("/api/preview-markdown", { method: "POST", body: { text: els.taskResult.value } });
      if (requestId !== state.resultPreviewRequest || !state.resultPreviewVisible || state.selectedTask?.id !== taskId) return;
      els.resultPreview.innerHTML = result.html;
    } catch (error) {
      if (requestId === state.resultPreviewRequest) toast(`Не удалось построить предпросмотр результата: ${error.message}`, "error");
    }
  }

  async function createTask(title, status = "todo", taskType = state.quickTaskType) {
    // Keep a selected type filter from silently assigning a type to every new task.
    const inheritedTag = state.tag && !Object.hasOwn(TASK_TYPE_LABELS, state.tag.toLowerCase())
      ? state.tag
      : "";
    const tags = [...new Set([
      state.project ? projectTag(state.project) : "",
      inheritedTag,
      taskType,
    ].filter(Boolean))].join(", ");
    let task = await api("/api/tasks", { method: "POST", body: { title: title.trim(), tags } });
    if (status !== "todo") {
      task = await api(`/api/tasks/${task.id}`, { method: "PATCH", body: { status } });
    }
    await loadTasks();
    return task;
  }

  async function undoCreation(taskId) {
    await api(`/api/tasks/${taskId}`, { method: "DELETE" });
    await loadTasks();
    toast("Создание задачи отменено");
  }

  async function restoreTaskState(taskId, snapshot, successMessage = "Действие отменено") {
    await api(`/api/tasks/${taskId}`, {
      method: "PATCH",
      body: { status: snapshot.status, position: snapshot.position },
    });
    await loadTasks();
    toast(successMessage);
  }

  async function restoreTaskDetails(taskId, snapshot) {
    await api(`/api/tasks/${taskId}`, {
      method: "PATCH",
      body: {
        title: snapshot.title,
        description: snapshot.description || "",
        result: snapshot.result || "",
        tags: snapshot.tags || "",
        status: snapshot.status,
        position: snapshot.position,
      },
    });
    await loadTasks();
    if (state.selectedTask?.id === taskId) await openTaskPanel(taskId);
    toast("Изменения задачи отменены");
  }

  async function undoAttachmentUpload(attachments) {
    for (const attachment of attachments) {
      await api(`/api/files/${attachment.id}`, { method: "DELETE" });
    }
    await loadTasks();
    if (state.selectedTask) await refreshSelectedTask();
    toast("Загрузка вложений отменена");
  }

  async function undoAttachmentRemoval(taskId, file) {
    const data = new FormData();
    data.append("files", file, file.name);
    await api(`/api/tasks/${taskId}/files`, { method: "POST", body: data });
    await loadTasks();
    if (state.selectedTask?.id === taskId) await refreshSelectedTask();
    toast("Вложение восстановлено");
  }

  async function handleTaskExport() {
    if (!state.selectedTask) return;
    els.exportTask.disabled = true;
    try {
      if (!(await saveCurrentTaskDraft())) return;
      const task = state.selectedTask;
      const current = {
        title: els.taskTitle.value.trim(),
        status: els.taskStatus.value,
        tags: editableTaskTags().join(", "),
        description: els.taskDescription.value,
        result: els.taskResult.value,
      };
      const previousTags = String(task.tags || "")
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean)
        .join(", ");
      if (
        current.title !== task.title ||
        current.status !== task.status ||
        current.tags !== previousTags ||
        current.description !== (task.description || "") ||
        current.result !== (task.result || "")
      ) {
        await api(`/api/tasks/${task.id}`, {
          method: "PATCH",
          body: current,
        });
        await loadTasks();
        await openTaskPanel(task.id);
      }
      window.location.href = `/api/tasks/${task.id}/export`;
    } catch (error) {
      toast(`Не удалось экспортировать задачу: ${error.message}`, "error");
    } finally {
      els.exportTask.disabled = false;
    }
  }

  async function handleCloseTask() {
    if (!(await saveCurrentTaskDraft())) return;
    const task = state.selectedTask;
    if (!task) return;
    const status = els.closeTask.dataset.action === "reopen" ? "todo" : "done";
    try {
      await api(`/api/tasks/${task.id}`, { method: "PATCH", body: { status } });
      closePanel();
      await loadTasks();
      const previousState = { status: task.status, position: task.position };
      toast(
        status === "done" ? "Задача закрыта" : "Задача возвращена к выполнению",
        "success",
        "Отменить",
        () => restoreTaskState(task.id, previousState),
      );
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function snapshotAttachmentFiles(attachments) {
    const files = [];
    for (const attachment of attachments || []) {
      const response = await fetch(`/api/files/${attachment.id}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`Не удалось сохранить вложение «${attachment.filename}» для отмены удаления`);
      const blob = await response.blob();
      files.push(new File([blob], attachment.filename, { type: blob.type || "application/octet-stream" }));
    }
    return files;
  }

  async function restoreDeletedTask(snapshot, files, wasFocused) {
    const created = await api("/api/tasks", {
      method: "POST",
      body: { title: snapshot.title, description: snapshot.description || "", result: snapshot.result || "", tags: snapshot.tags || "" },
    });
    try {
      await api(`/api/tasks/${created.id}`, {
        method: "PATCH",
        body: { status: snapshot.status, position: snapshot.position },
      });
      if (files.length) {
        const data = new FormData();
        files.forEach((file) => data.append("files", file, file.name));
        await api(`/api/tasks/${created.id}/files`, { method: "POST", body: data });
      }
    } catch (error) {
      await api(`/api/tasks/${created.id}`, { method: "DELETE" }).catch(() => null);
      throw error;
    }
    await loadTasks();
    if (wasFocused) setFocusedTask(created.id);
    toast("Задача восстановлена вместе с вложениями");
  }

  const deleteTaskDialog = $("#delete-task-dialog");
  const deleteTaskMessage = $("#delete-task-message");
  const closeDeleteTaskDialogButton = $("#close-delete-task");
  const cancelDeleteTaskButton = $("#cancel-delete-task");
  const confirmDeleteTaskButton = $("#confirm-delete-task");
  let pendingTaskDeleteConfirmation = null;

  function requestTaskDeleteConfirmation(title) {
    if (deleteTaskDialog.open) return Promise.resolve(false);

    deleteTaskMessage.textContent = `Вы действительно хотите удалить задачу «${title}» вместе со всеми вложениями? После удаления задачу можно будет восстановить из уведомления.`;
    return new Promise((resolve) => {
      pendingTaskDeleteConfirmation = resolve;
      deleteTaskDialog.showModal();
      cancelDeleteTaskButton.focus({ preventScroll: true });
    });
  }

  function finishTaskDeleteConfirmation(confirmed) {
    const resolve = pendingTaskDeleteConfirmation;
    if (!resolve) return;
    pendingTaskDeleteConfirmation = null;
    if (deleteTaskDialog.open) deleteTaskDialog.close();
    resolve(confirmed);
  }

  closeDeleteTaskDialogButton.addEventListener("click", () => finishTaskDeleteConfirmation(false));
  cancelDeleteTaskButton.addEventListener("click", () => finishTaskDeleteConfirmation(false));
  confirmDeleteTaskButton.addEventListener("click", () => finishTaskDeleteConfirmation(true));
  deleteTaskDialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    finishTaskDeleteConfirmation(false);
  });

  async function handleDeleteTask() {
    const task = state.selectedTask;
    if (!task) return;
    if (!(await requestTaskDeleteConfirmation(els.taskTitle.value || task.title))) return;
    if (!(await saveCurrentTaskDraft())) return;
    const currentTask = state.selectedTask;
    if (!currentTask) return;
    try {
      const files = await snapshotAttachmentFiles(currentTask.attachments || []);
      const snapshot = {
        title: currentTask.title,
        description: currentTask.description || "",
        result: currentTask.result || "",
        tags: currentTask.tags || "",
        status: currentTask.status,
        position: currentTask.position,
      };
      const wasFocused = state.focusTaskId === currentTask.id;
      await api(`/api/tasks/${currentTask.id}`, { method: "DELETE" });
      closePanel();
      await loadTasks();
      toast("Задача удалена", "success", "Восстановить", () => restoreDeletedTask(snapshot, files, wasFocused));
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function uploadFiles(fileList) {
    const files = Array.from(fileList || []);
    if (!state.selectedTask || files.length === 0) return;
    const taskId = state.selectedTask.id;
    // Upload refreshes the panel from the server, so persist the current form first.
    if (!(await saveCurrentTaskDraft())) return;
    if (state.selectedTask?.id !== taskId) return;
    const data = new FormData();
    files.forEach((file) => data.append("files", file, file.name));
    els.chooseFiles.disabled = true;
    try {
      const uploaded = await api(`/api/tasks/${taskId}/files`, { method: "POST", body: data });
      await loadTasks();
      await refreshSelectedTask();
      toast(
        `Загружено файлов: ${uploaded.length}`,
        "success",
        "Отменить",
        () => undoAttachmentUpload(uploaded),
      );
    } catch (error) {
      toast(error.message, "error");
    } finally {
      els.chooseFiles.disabled = false;
      els.attachmentInput.value = "";
    }
  }

  function clipboardImageExtension(mimeType) {
    const extensions = {
      "image/png": "png",
      "image/jpeg": "jpg",
      "image/gif": "gif",
      "image/webp": "webp",
      "image/avif": "avif",
      "image/bmp": "bmp",
      "image/x-ms-bmp": "bmp",
      "image/heic": "heic",
      "image/heif": "heif",
      "image/svg+xml": "svg",
      "image/tiff": "tiff",
    };
    const fallback = mimeType.split("/")[1]?.split("+")[0]?.replace(/^x-/, "").replace(/[^a-z0-9]/g, "");
    return extensions[mimeType] || fallback || "png";
  }

  function pastedImageFiles(clipboardData) {
    const items = Array.from(clipboardData?.items || []);
    const files = items.flatMap((item, index) => {
      const mimeType = String(item.type || "").toLowerCase();
      if (!mimeType.startsWith("image/") || typeof item.getAsFile !== "function") return [];
      const blob = item.getAsFile();
      if (!blob) return [];
      const extension = clipboardImageExtension(mimeType);
      const filename = `pasted-image-${Date.now()}-${index + 1}.${extension}`;
      return [new File([blob], filename, { type: mimeType })];
    });
    if (files.length) return files;

    return Array.from(clipboardData?.files || []).filter((file) => file.type?.toLowerCase().startsWith("image/"));
  }

  function handleTaskPanelPaste(event) {
    if (!state.selectedTask || !els.panel.classList.contains("is-open")) return;
    const files = pastedImageFiles(event.clipboardData);
    if (!files.length) return;
    event.preventDefault();
    void uploadFiles(files);
  }

  async function removeAttachment(attachmentId, filename, isImage = false) {
    const confirmed = isImage
      ? await requestImageDeleteConfirmation(filename)
      : window.confirm(`Удалить вложение «${filename}»?`);
    if (!confirmed) return;
    if (!(await saveCurrentTaskDraft())) return;
    try {
      const response = await fetch(`/api/files/${attachmentId}`, { cache: "no-store" });
      if (!response.ok) throw new Error("Не удалось сохранить вложение для отмены удаления");
      const blob = await response.blob();
      const file = new File([blob], filename, { type: blob.type || "application/octet-stream" });
      const taskId = state.selectedTask?.id;
      await api(`/api/files/${attachmentId}`, { method: "DELETE" });
      await loadTasks();
      await refreshSelectedTask();
      toast("Вложение удалено", "success", "Восстановить", () => undoAttachmentRemoval(taskId, file));
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function importMarkdown(fileList) {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    const data = new FormData();
    files.forEach((file) => data.append("files", file, file.name));
    try {
      const result = await api("/api/import", { method: "POST", body: data });
      await loadTasks();
      if (result.skipped.length) {
        const first = result.skipped.slice(0, 3).map((item) => `${item.filename}: ${item.reason}${item.line ? ` (строка ${item.line})` : ""}`).join("; ");
        const suffix = result.skipped.length > 3 ? `; и ещё ${result.skipped.length - 3}` : "";
        toast(`Создано задач: ${result.created}. Пропущено: ${result.skipped.length}. ${first}${suffix}`, result.created ? "success" : "error");
      } else {
        toast(`Импорт завершён: создано задач ${result.created}`);
      }
    } catch (error) {
      toast(error.message, "error");
    } finally {
      els.importFiles.value = "";
    }
  }

  async function reorderAfterDrop(event) {
    const item = event.item;
    const list = event.to;
    if (!item || !list || !STATUSES.includes(list.dataset.status)) {
      await loadTasks();
      return;
    }
    const sameColumn = event.from === event.to;
    if (sameColumn && state.columnPreferences[list.dataset.status].sort !== "manual") {
      await loadTasks();
      toast("Чтобы менять порядок перетаскиванием, выберите «Ручной порядок» в настройках колонки.");
      return;
    }
    const previous = item.previousElementSibling && item.previousElementSibling.classList.contains("task-card") ? item.previousElementSibling : null;
    const next = item.nextElementSibling && item.nextElementSibling.classList.contains("task-card") ? item.nextElementSibling : null;
    const prevPosition = previous ? Number(previous.dataset.position) : null;
    const nextPosition = next ? Number(next.dataset.position) : null;
    let position;
    if (prevPosition !== null && nextPosition !== null) {
      position = prevPosition < nextPosition ? (prevPosition + nextPosition) / 2 : prevPosition + 0.000001;
    } else if (prevPosition !== null) {
      position = prevPosition + 1;
    } else if (nextPosition !== null) {
      position = nextPosition - 1;
    } else {
      position = 0;
    }
    try {
      const taskId = Number(item.dataset.taskId);
      const previousState = state.dragOrigin || state.tasks.find((task) => task.id === taskId);
      const wasFocused = state.focusTaskId === taskId;
      const changes = { status: list.dataset.status };
      if (sameColumn || state.columnPreferences[list.dataset.status].sort === "manual") {
        changes.position = position;
      }
      await api(`/api/tasks/${taskId}`, { method: "PATCH", body: changes });
      await loadTasks();
      if (previousState) {
        toast("Положение задачи изменено", "success", "Отменить", async () => {
          await restoreTaskState(taskId, previousState);
          if (wasFocused && previousState.status !== "done") setFocusedTask(taskId);
        });
      }
      state.dragOrigin = null;
    } catch (error) {
      toast(`Не удалось переместить задачу: ${error.message}`, "error");
      state.dragOrigin = null;
      await loadTasks();
    }
  }

  function initializeSortables() {
    $$(".task-list").forEach((list) => {
      Sortable.create(list, {
        group: "kanban",
        draggable: ".task-card",
        animation: 160,
        onStart: (event) => {
          const taskId = Number(event.item?.dataset.taskId);
          const task = state.tasks.find((item) => item.id === taskId);
          state.dragOrigin = task ? { status: task.status, position: task.position } : null;
        },
        onEnd: reorderAfterDrop,
      });
    });
  }

  const createProjectDialog = $("#create-project-dialog");
  const createProjectForm = $("#create-project-form");
  const createProjectKey = $("#create-project-key");
  const createProjectError = $("#create-project-error");
  const createProjectClose = $("#close-create-project");
  const createProjectCancel = $("#cancel-create-project");
  const createProjectSubmit = $("#submit-create-project");
  const IMAGE_DELETE_CONFIRMATION_KEY = "flowboard-skip-image-delete-confirmation";
  const deleteImageDialog = $("#delete-image-dialog");
  const deleteImageMessage = $("#delete-image-message");
  const skipImageDeleteConfirmation = $("#skip-image-delete-confirmation");
  const closeDeleteImageDialogButton = $("#close-delete-image");
  const cancelDeleteImageButton = $("#cancel-delete-image");
  const confirmDeleteImageButton = $("#confirm-delete-image");
  let pendingImageDeleteConfirmation = null;
  let createProjectBusy = false;
  let focusQuickTitleAfterCreateProject = false;

  function requestImageDeleteConfirmation(filename) {
    if (readStorage(IMAGE_DELETE_CONFIRMATION_KEY) === "true") return Promise.resolve(true);
    if (deleteImageDialog.open) return Promise.resolve(false);

    deleteImageMessage.textContent = `Вы действительно хотите удалить изображение «${filename}»? Это действие нельзя отменить.`;
    skipImageDeleteConfirmation.checked = false;
    return new Promise((resolve) => {
      pendingImageDeleteConfirmation = resolve;
      deleteImageDialog.showModal();
      cancelDeleteImageButton.focus({ preventScroll: true });
    });
  }

  function finishImageDeleteConfirmation(confirmed) {
    const resolve = pendingImageDeleteConfirmation;
    if (!resolve) return;
    pendingImageDeleteConfirmation = null;

    if (confirmed && skipImageDeleteConfirmation.checked) {
      writeStorage(IMAGE_DELETE_CONFIRMATION_KEY, "true");
    }
    if (deleteImageDialog.open) deleteImageDialog.close();
    resolve(confirmed);
  }

  closeDeleteImageDialogButton.addEventListener("click", () => finishImageDeleteConfirmation(false));
  cancelDeleteImageButton.addEventListener("click", () => finishImageDeleteConfirmation(false));
  confirmDeleteImageButton.addEventListener("click", () => finishImageDeleteConfirmation(true));
  deleteImageDialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    finishImageDeleteConfirmation(false);
  });

  function setCreateProjectError(message) {
    createProjectError.textContent = message;
    createProjectError.hidden = !message;
    createProjectKey.setAttribute("aria-invalid", String(Boolean(message)));
  }

  function setCreateProjectBusy(busy) {
    createProjectBusy = busy;
    createProjectForm.setAttribute("aria-busy", String(busy));
    createProjectKey.disabled = busy;
    createProjectClose.disabled = busy;
    createProjectCancel.disabled = busy;
    createProjectSubmit.disabled = busy;
    createProjectSubmit.textContent = busy ? "Создание…" : "Создать проект";
  }

  function openCreateProjectDialog() {
    if (createProjectBusy || createProjectDialog.open) return;
    focusQuickTitleAfterCreateProject = false;
    createProjectForm.reset();
    setCreateProjectError("");
    setCreateProjectBusy(false);
    createProjectDialog.showModal();
    createProjectKey.focus({ preventScroll: true });
  }

  function closeCreateProjectDialog() {
    if (createProjectBusy || !createProjectDialog.open) return;
    createProjectDialog.close();
  }

  async function createProjectFromDialog(event) {
    event.preventDefault();
    if (createProjectBusy) return;

    const slug = createProjectKey.value.trim().toLowerCase().replace(/\s+/g, "-");
    createProjectKey.value = slug;
    setCreateProjectError("");

    if (!slug) {
      setCreateProjectError("Введите ключ проекта.");
      createProjectKey.focus({ preventScroll: true });
      return;
    }
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) {
      setCreateProjectError("Используйте латинские буквы и цифры, разделяя части ключа одиночным дефисом. Ключ не должен начинаться или заканчиваться дефисом.");
      createProjectKey.focus({ preventScroll: true });
      return;
    }
    if (state.projects.includes(slug)) {
      setCreateProjectError("Проект с таким ключом уже существует.");
      createProjectKey.focus({ preventScroll: true });
      return;
    }

    setCreateProjectBusy(true);
    try {
      // Let the progress state render before the existing local creation flow runs.
      await new Promise((resolve) => window.setTimeout(resolve, 0));
      addProject();
      focusQuickTitleAfterCreateProject = true;
      setCreateProjectBusy(false);
      createProjectDialog.close();
    } catch {
      setCreateProjectError("Не удалось создать проект. Проверьте введённые данные и попробуйте ещё раз.");
    } finally {
      setCreateProjectBusy(false);
      if (createProjectDialog.open && createProjectError.textContent) {
        createProjectKey.focus({ preventScroll: true });
      }
    }
  }
  function addProject() {
    const raw = createProjectKey.value;
    const slug = raw.trim().toLowerCase().replace(/\s+/g, "-");
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) {
      toast("Используй латиницу, цифры и дефисы без пробелов по краям", "error");
      return;
    }
    if (!state.projects.includes(slug)) state.projects.push(slug);
    state.projects.sort((a, b) => a.localeCompare(b, "ru"));
    state.project = slug;
    populateProjectFilter();
    renderBoard();
    els.quickTitle.focus();
    persistProjectState();
    toast(`Проект «${projectLabel(slug)}» выбран. Новые задачи получат тег ${projectTag(slug)}.`);
  }

  async function handleFocusDone() {
    const task = state.tasks.find((item) => item.id === state.focusTaskId);
    if (!task || task.status === "done") return;
    const previousState = { status: task.status, position: task.position };
    try {
      await api(`/api/tasks/${task.id}`, { method: "PATCH", body: { status: "done" } });
      setFocusedTask(null);
      await loadTasks();
      toast("Задача закрыта", "success", "Отменить", async () => {
        await restoreTaskState(task.id, previousState);
        setFocusedTask(task.id);
      });
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function initialize() {
    try {
      const config = await api("/api/config");
      state.wipLimit = config.wip_limit;
      state.maxFileSizeMb = config.max_file_size_mb;
      els.maxFileMb.textContent = String(config.max_file_size_mb);
      await Promise.all([loadTaskSettings(), loadTasks()]);
    } catch (error) {
      toast(`Не удалось загрузить данные: ${error.message}`, "error");
    }
  }

  els.quickTaskType.addEventListener("click", (event) => {
    const button = event.target.closest("[data-task-type]");
    if (!button) return;
    setQuickTaskType(button.dataset.taskType);
    // Keep the quick-entry flow moving: choose a type, then submit with Enter.
    els.quickTitle.focus({ preventScroll: true });
  });

  els.quickForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const title = els.quickTitle.value.trim();
    if (!title) return;
    const status = els.quickForm.dataset.newStatus || "todo";
    const taskType = state.quickTaskType;
    try {
      const task = await createTask(title, status, taskType);
      els.quickTitle.value = "";
      setQuickTaskType("");
      els.quickTitle.focus();
      els.quickForm.dataset.newStatus = "todo";
      els.quickTitle.placeholder = "Добавить задачу… и нажать Enter";
      toast(
        status === "todo" ? "Задача добавлена" : `Задача добавлена в колонку «${STATUS_LABELS[status]}»`,
        "success",
        "Отменить",
        () => undoCreation(task.id),
      );
    } catch (error) {
      toast(error.message, "error");
    }
  });

  els.search.addEventListener("input", () => {
    state.search = els.search.value;
    renderBoard();
  });
  els.projectFilter.addEventListener("change", () => {
    state.project = els.projectFilter.value;
    persistProjectState();
    renderBoard();
    els.quickTitle.focus();
  });
  els.addProject.addEventListener("click", openCreateProjectDialog);
  createProjectForm.addEventListener("submit", createProjectFromDialog);
  createProjectCancel.addEventListener("click", closeCreateProjectDialog);
  createProjectClose.addEventListener("click", closeCreateProjectDialog);
  createProjectKey.addEventListener("input", () => setCreateProjectError(""));
  createProjectDialog.addEventListener("cancel", (event) => {
    if (createProjectBusy) event.preventDefault();
  });
  createProjectDialog.addEventListener("close", () => {
    createProjectForm.reset();
    setCreateProjectError("");
    if (focusQuickTitleAfterCreateProject) {
      focusQuickTitleAfterCreateProject = false;
      els.quickTitle.focus({ preventScroll: true });
    } else {
      els.addProject.focus({ preventScroll: true });
    }
  });
  els.tagFilter.addEventListener("change", () => {
    state.tag = els.tagFilter.value;
    renderBoard();
  });

  $$("[data-add-status]").forEach((button) => button.addEventListener("click", () => {
    els.quickTitle.focus();
    if (button.dataset.addStatus !== "todo") {
      els.quickTitle.placeholder = `Новая задача в колонке «${STATUS_LABELS[button.dataset.addStatus]}»…`;
      els.quickForm.dataset.newStatus = button.dataset.addStatus;
    } else {
      els.quickTitle.placeholder = "Добавить задачу… и нажать Enter";
      els.quickForm.dataset.newStatus = "todo";
    }
  }));

  els.taskForm.addEventListener("submit", (event) => event.preventDefault());
  els.taskTagCustomToggle.addEventListener("click", () => {
    state.taskTagInputExpanded = true;
    renderTaskTagEditor();
    els.taskTagInput.focus({ preventScroll: true });
  });
  els.addTaskTag.addEventListener("click", () => addTaskTags());
  els.taskTagInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      addTaskTags();
    }
  });
  els.exportTask.addEventListener("click", handleTaskExport);
  els.closePanel.addEventListener("click", () => { void dismissTaskPanel(); });
  els.overlay.addEventListener("click", () => { void dismissTaskPanel(); });
  els.closeTask.addEventListener("click", handleCloseTask);
  els.deleteTask.addEventListener("click", handleDeleteTask);
  els.focusTask.addEventListener("click", () => {
    if (!state.selectedTask) return;
    if (state.focusTaskId === state.selectedTask.id) {
      setFocusedTask(null);
      toast("Фокус снят");
    } else {
      setFocusedTask(state.selectedTask.id);
      toast("Задача добавлена в фокус");
    }
  });
  els.focusOpen.addEventListener("click", () => {
    if (state.focusTaskId) openTaskPanel(state.focusTaskId);
  });
  els.focusDone.addEventListener("click", handleFocusDone);
  els.focusClear.addEventListener("click", clearFocus);
  els.importButton.addEventListener("click", () => els.importFiles.click());
  els.importFiles.addEventListener("change", () => importMarkdown(els.importFiles.files));
  els.exportMd.addEventListener("click", () => { window.location.href = "/api/export?format=md"; });
  els.exportZip.addEventListener("click", () => { window.location.href = "/api/export?format=zip"; });
  els.chooseFiles.addEventListener("click", () => els.attachmentInput.click());
  els.toggleAttachmentUpload.addEventListener("click", () => {
    const expanded = els.attachmentDropzone.hidden;
    els.attachmentDropzone.hidden = !expanded;
    els.toggleAttachmentUpload.setAttribute("aria-expanded", String(expanded));
    els.toggleAttachmentUpload.setAttribute("aria-label", expanded ? "Скрыть загрузку файлов" : "Добавить вложение");
    els.toggleAttachmentUpload.title = expanded ? "Скрыть загрузку файлов" : "Добавить вложение";
    if (expanded) els.chooseFiles.focus({ preventScroll: true });
  });
  els.attachmentInput.addEventListener("change", () => uploadFiles(els.attachmentInput.files));
  els.taskMoreToggle.addEventListener("click", () => {
    const expanded = els.taskMoreMenu.hidden;
    els.taskMoreMenu.hidden = !expanded;
    els.taskMoreToggle.setAttribute("aria-expanded", String(expanded));
  });
  [els.exportTask, els.focusTask, els.archiveTask, els.closeTask, els.deleteTask].forEach((button) => button.addEventListener("click", () => {
    els.taskMoreMenu.hidden = true;
    els.taskMoreToggle.setAttribute("aria-expanded", "false");
  }));
  document.addEventListener("click", (event) => {
    if (!els.taskMoreMenu.hidden && !event.target.closest(".task-more-actions")) {
      els.taskMoreMenu.hidden = true;
      els.taskMoreToggle.setAttribute("aria-expanded", "false");
    }
  });
  els.panel.addEventListener("paste", handleTaskPanelPaste);
  els.attachmentPreviewClose.addEventListener("click", closeAttachmentPreview);
  els.attachmentPreviewDialog.addEventListener("click", (event) => {
    if (event.target === els.attachmentPreviewDialog) closeAttachmentPreview();
  });
  els.attachmentPreviewDialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeAttachmentPreview();
  });
  els.attachmentPreviewDialog.addEventListener("close", () => {
    state.attachmentPreviewToken += 1;
    releaseAttachmentPreviewUrl();
    els.attachmentPreviewImage.hidden = true;
    els.attachmentPreviewLoading.hidden = false;
    els.attachmentPreviewError.hidden = true;
  });
  els.attachmentPreviewImage.addEventListener("error", () => {
    if (!els.attachmentPreviewDialog.open || els.attachmentPreviewImage.hidden) return;
    els.attachmentPreviewImage.hidden = true;
    els.attachmentPreviewLoading.hidden = true;
    els.attachmentPreviewError.textContent = "Браузер не смог показать этот формат. Можно скачать исходный файл кнопкой выше.";
    els.attachmentPreviewError.hidden = false;
  });
  els.toggleDone.addEventListener("click", () => { state.doneExpanded = !state.doneExpanded; renderBoard(); });
  doneColumnCollapseQuery.addEventListener("change", () => renderBoard());

  els.columnOptionsToggles.forEach((button) => button.addEventListener("click", (event) => {
    event.stopPropagation();
    const status = button.dataset.columnOptionsToggle;
    const panel = $(`[data-column-options-panel="${status}"]`);
    const shouldOpen = panel.hidden;
    $$('[data-column-options-panel]').forEach((otherPanel) => {
      otherPanel.hidden = true;
      const otherStatus = otherPanel.dataset.columnOptionsPanel;
      const otherToggle = $(`[data-column-options-toggle="${otherStatus}"]`);
      if (otherToggle) otherToggle.setAttribute("aria-expanded", "false");
    });
    panel.hidden = !shouldOpen;
    button.setAttribute("aria-expanded", String(shouldOpen));
  }));

  $$('[data-column-filter]').forEach((select) => select.addEventListener("change", () => {
    state.columnPreferences[select.dataset.columnFilter].tag = select.value;
    persistColumnPreferences();
    renderBoard();
    const toggle = $(`[data-column-options-toggle="${select.dataset.columnFilter}"]`);
    if (toggle) toggle.classList.toggle("has-column-filter", Boolean(select.value));
  }));

  $$('[data-column-sort]').forEach((select) => select.addEventListener("change", () => {
    const status = select.dataset.columnSort;
    state.columnPreferences[status].sort = COLUMN_SORT_MODES.has(select.value)
      ? select.value
      : DEFAULT_COLUMN_PREFERENCES[status].sort;
    persistColumnPreferences();
    renderBoard();
  }));

  $$('[data-column-reset]').forEach((button) => button.addEventListener("click", () => {
    const status = button.dataset.columnReset;
    state.columnPreferences[status] = { ...DEFAULT_COLUMN_PREFERENCES[status] };
    persistColumnPreferences();
    populateColumnFilters();
    renderBoard();
  }));

  document.addEventListener("click", (event) => {
    if (event.target.closest(".column-options")) return;
    $$('[data-column-options-panel]').forEach((panel) => {
      panel.hidden = true;
      const toggle = $(`[data-column-options-toggle="${panel.dataset.columnOptionsPanel}"]`);
      if (toggle) toggle.setAttribute("aria-expanded", "false");
    });
  });

  $$('[data-archive-completed]').forEach((button) => button.addEventListener("click", () => {
    void archiveCompletedTasks();
  }));
  els.archiveOpen.addEventListener("click", () => { void openArchive(); });
  els.archiveClose.addEventListener("click", () => els.archiveDialog.close());
  els.archiveDialog.addEventListener("click", (event) => {
    if (event.target === els.archiveDialog) els.archiveDialog.close();
  });
  els.archiveAutoEnabled.addEventListener("change", () => { void saveArchiveSettings(); });
  els.archiveAfterDays.addEventListener("change", () => { void saveArchiveSettings(); });
  els.archiveSearch.addEventListener("input", () => {
    state.archiveFilters.search = els.archiveSearch.value;
    renderArchive();
  });
  els.archiveProjectFilter.addEventListener("change", () => {
    state.archiveFilters.project = els.archiveProjectFilter.value;
    renderArchive();
  });
  els.archiveTagFilter.addEventListener("change", () => {
    state.archiveFilters.tag = els.archiveTagFilter.value;
    renderArchive();
  });
  els.archivePeriodFilter.addEventListener("change", () => {
    state.archiveFilters.period = els.archivePeriodFilter.value;
    renderArchive();
  });
  els.archiveCompleteNow.addEventListener("click", () => { void archiveCompletedTasks(); });
  els.archiveTask.addEventListener("click", () => {
    const taskId = state.selectedTask?.id;
    if (taskId) void archiveSingleTask(taskId);
  });

  els.taskTitleDisplay.addEventListener("click", () => {
    els.taskTitleDisplay.hidden = true;
    els.taskTitle.hidden = false;
    els.taskTitle.focus({ preventScroll: true });
    els.taskTitle.select();
  });
  els.taskTitle.addEventListener("input", () => {
    els.taskTitleDisplayText.textContent = els.taskTitle.value.trim() || "Введите название задачи";
  });
  els.taskTitle.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      finishTitleEditing();
    } else if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      els.taskTitle.value = state.selectedTask?.title || els.taskTitle.value;
      finishTitleEditing();
    }
  });

  function finishTitleEditing() {
    const title = els.taskTitle.value.trim();
    if (!title) {
      els.taskTitle.value = "";
      els.taskTitle.focus({ preventScroll: true });
      toast("У задачи должно быть название", "error");
      return;
    }
    els.taskTitle.value = title;
    els.taskTitleDisplayText.textContent = title;
    els.taskTitle.hidden = true;
    els.taskTitleDisplay.hidden = false;
    els.taskTitleDisplay.focus({ preventScroll: true });
  }

  function updateTaskResultIndicator() {
    els.taskResultIndicator.hidden = !els.taskResult.value.trim();
  }

  function updateTaskWorkspaceHeading() {
    const isResult = state.activeTaskTab === "result";
    const isEditing = isResult ? !state.resultPreviewVisible : !state.previewVisible;
    els.taskWorkspaceTitle.textContent = isResult ? "Результат" : "Описание";
    els.taskWorkspaceTitle.htmlFor = isResult ? "task-result" : "task-description";
    els.taskWorkspaceHelper.textContent = isResult
      ? "Итог работы с форматированием Markdown"
      : "Текст с форматированием Markdown";
    const subject = isResult ? "результат" : "описание";
    els.copyDescription.setAttribute("aria-label", `Копировать ${subject}`);
    els.copyDescription.title = `Копировать ${subject}`;
    els.togglePreview.setAttribute("aria-label", `${isEditing ? "Показать" : "Редактировать"} ${subject}`);
    els.togglePreview.title = isEditing ? "Завершить редактирование" : `Редактировать ${subject}`;
  }

  function setTaskWorkspaceTab(tab, focus = false) {
    const activeTab = tab === "result" ? "result" : "description";
    state.activeTaskTab = activeTab;
    const descriptionSelected = activeTab === "description";
    els.taskDescriptionTab.setAttribute("aria-selected", String(descriptionSelected));
    els.taskDescriptionTab.tabIndex = descriptionSelected ? 0 : -1;
    els.taskDescriptionPanel.hidden = !descriptionSelected;
    els.taskResultTab.setAttribute("aria-selected", String(!descriptionSelected));
    els.taskResultTab.tabIndex = descriptionSelected ? -1 : 0;
    els.taskResultPanel.hidden = descriptionSelected;
    updateTaskWorkspaceHeading();
    updateDescriptionActionIcon();
    if (focus) (descriptionSelected ? els.taskDescriptionTab : els.taskResultTab).focus({ preventScroll: true });
  }

  function handleTaskWorkspaceTabKeydown(event) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    let tab = state.activeTaskTab;
    if (event.key === "Home") tab = "description";
    else if (event.key === "End") tab = "result";
    else tab = state.activeTaskTab === "description" ? "result" : "description";
    setTaskWorkspaceTab(tab, true);
  }

  async function setDescriptionEditing(editing) {
    if (!editing && !(await saveCurrentTaskDraft())) return;
    state.previewVisible = !editing;
    els.descriptionPreview.hidden = editing;
    els.taskDescription.hidden = !editing;
    updateTaskWorkspaceHeading();
    updateDescriptionActionIcon();
    if (editing) els.taskDescription.focus({ preventScroll: true });
    else void requestMarkdownPreview();
  }

  async function setResultEditing(editing) {
    if (!editing && !(await saveCurrentTaskDraft())) return;
    state.resultPreviewVisible = !editing;
    els.resultPreview.hidden = editing;
    els.taskResult.hidden = !editing;
    updateTaskWorkspaceHeading();
    updateDescriptionActionIcon();
    if (editing) els.taskResult.focus({ preventScroll: true });
    else void requestResultMarkdownPreview();
  }

  let copyFeedbackTimer = null;

  function showDescriptionCopiedFeedback() {
    if (copyFeedbackTimer !== null) window.clearTimeout(copyFeedbackTimer);
    const subject = state.activeTaskTab === "result" ? "Результат" : "Описание";
    els.copyDescription.classList.add("is-copied");
    els.copyDescription.setAttribute("aria-label", `${subject} скопирован${subject === "Описание" ? "о" : ""}`);
    els.copyDescription.title = `${subject} скопирован${subject === "Описание" ? "о" : ""}`;
    copyFeedbackTimer = window.setTimeout(() => {
      els.copyDescription.classList.remove("is-copied");
      updateTaskWorkspaceHeading();
      copyFeedbackTimer = null;
    }, 1200);
  }

  async function copyTaskDescription() {
    if (!navigator.clipboard?.writeText) {
      toast("Копирование недоступно в этом браузере", "error");
      return;
    }
    const isResult = state.activeTaskTab === "result";
    try {
      await navigator.clipboard.writeText(isResult ? els.taskResult.value : els.taskDescription.value);
      showDescriptionCopiedFeedback();
    } catch {
      toast(`Не удалось скопировать ${isResult ? "результат" : "описание"}. Проверьте разрешение браузера и защищённое соединение.`, "error");
    }
  }

  function toggleMarkdownChecklistItem(input, textarea, isPreviewVisible, refreshPreview) {
    if (!isPreviewVisible || !state.selectedTask) return;
    const lineNumber = Number(input.dataset.taskCheckbox);
    if (!Number.isInteger(lineNumber) || lineNumber < 0) return;
    const lines = textarea.value.split("\n");
    const line = lines[lineNumber];
    const match = typeof line === "string"
      ? line.match(/^(\s*(?:[-*+]|\d+[.)])\s+)\[([ xX])\]/)
      : null;
    if (!match) {
      void refreshPreview();
      return;
    }
    lines[lineNumber] = `${match[1]}[${input.checked ? "x" : " "}]${line.slice(match[0].length)}`;
    textarea.value = lines.join("\n");
    input.setAttribute("aria-label", input.checked ? "Снять отметку" : "Отметить пункт списка");
    void refreshPreview();
    scheduleTaskDraftSave(0);
  }

  els.taskDescriptionTab.addEventListener("click", () => setTaskWorkspaceTab("description"));
  els.taskResultTab.addEventListener("click", () => setTaskWorkspaceTab("result"));
  els.taskDescriptionTab.addEventListener("keydown", handleTaskWorkspaceTabKeydown);
  els.taskResultTab.addEventListener("keydown", handleTaskWorkspaceTabKeydown);
  els.copyDescription.addEventListener("click", () => { void copyTaskDescription(); });
  els.togglePreview.addEventListener("click", () => {
    if (state.activeTaskTab === "result") void setResultEditing(state.resultPreviewVisible);
    else void setDescriptionEditing(state.previewVisible);
  });
  els.descriptionPreview.addEventListener("click", (event) => {
    if (!state.previewVisible || event.target.closest("input[data-task-checkbox], a, button")) return;
    void setDescriptionEditing(true);
  });
  els.descriptionPreview.addEventListener("keydown", (event) => {
    if (!state.previewVisible || !["Enter", " "].includes(event.key)) return;
    if (event.target.closest("input[data-task-checkbox], a, button")) return;
    event.preventDefault();
    void setDescriptionEditing(true);
  });
  els.descriptionPreview.addEventListener("change", (event) => {
    const checkbox = event.target.closest("input[data-task-checkbox]");
    if (checkbox) toggleMarkdownChecklistItem(checkbox, els.taskDescription, state.previewVisible, requestMarkdownPreview);
  });
  els.resultPreview.addEventListener("change", (event) => {
    const checkbox = event.target.closest("input[data-task-checkbox]");
    if (checkbox) toggleMarkdownChecklistItem(checkbox, els.taskResult, state.resultPreviewVisible, requestResultMarkdownPreview);
  });
  els.resultPreview.addEventListener("click", (event) => {
    if (!state.resultPreviewVisible || event.target.closest("input[data-task-checkbox], a, button")) return;
    void setResultEditing(true);
  });
  els.resultPreview.addEventListener("keydown", (event) => {
    if (!state.resultPreviewVisible || !["Enter", " "].includes(event.key)) return;
    if (event.target.closest("input[data-task-checkbox], a, button")) return;
    event.preventDefault();
    void setResultEditing(true);
  });
  els.taskDescription.addEventListener("input", () => {
    if (state.previewVisible) requestMarkdownPreview();
  });
  els.taskDescription.addEventListener("blur", () => scheduleTaskDraftSave(180));
  els.taskResult.addEventListener("input", () => {
    updateTaskResultIndicator();
    scheduleTaskDraftSave(180);
  });
  els.taskResult.addEventListener("blur", () => scheduleTaskDraftSave(180));
  els.taskTitle.addEventListener("blur", () => scheduleTaskDraftSave(180));
  els.taskStatus.addEventListener("change", () => scheduleTaskDraftSave(180));
  els.requireResultToClose.addEventListener("change", () => { void saveTaskSettings(); });

  for (const eventName of ["dragenter", "dragover"]) {
    els.attachmentDropzone.addEventListener(eventName, (event) => {
      if (!Array.from(event.dataTransfer?.types || []).includes("Files")) return;
      event.preventDefault();
      els.attachmentDropzone.classList.add("is-dragover");
    });
  }
  for (const eventName of ["dragleave", "drop"]) {
    els.attachmentDropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      els.attachmentDropzone.classList.remove("is-dragover");
      if (eventName === "drop" && event.dataTransfer?.files?.length) uploadFiles(event.dataTransfer.files);
    });
  }
  els.attachmentDropzone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); els.attachmentInput.click(); }
  });

  const toolbarMenus = $$(".toolbar-menu");
  toolbarMenus.forEach((menu) => {
    menu.addEventListener("toggle", () => {
      if (menu.open) toolbarMenus.forEach((otherMenu) => {
        if (otherMenu !== menu) otherMenu.open = false;
      });
    });
    menu.addEventListener("click", (event) => {
      if (!event.target.closest("summary, select, input, textarea, label")) menu.open = false;
    });
  });
  document.addEventListener("click", (event) => {
    if (event.target.closest(".toolbar-menu")) return;
    toolbarMenus.forEach((menu) => { menu.open = false; });
  });

  document.addEventListener("keydown", (event) => {
    const tag = event.target && event.target.tagName;
    const isTyping = ["INPUT", "TEXTAREA", "SELECT"].includes(tag) || event.target?.isContentEditable;
    if (event.key === "Escape") {
      if (createProjectDialog.open) return;
      if (els.attachmentPreviewDialog.open) {
        event.preventDefault();
        closeAttachmentPreview();
        return;
      }
      const openToolbarMenu = toolbarMenus.find((menu) => menu.open);
      if (openToolbarMenu) {
        openToolbarMenu.open = false;
        return;
      }
      if (els.shortcutsDialog.open) els.shortcutsDialog.close();
      else if (els.projectDialog.open) els.projectDialog.close();
      else if (!els.overlay.hidden) void dismissTaskPanel();
      else {
        const latestToast = els.toastRegion.lastElementChild;
        if (latestToast) {
          event.preventDefault();
          latestToast.remove();
        }
      }
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLocaleLowerCase("en") === "k") {
      event.preventDefault();
      els.search.focus();
      els.search.select();
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLocaleLowerCase("en") === "p") {
      event.preventDefault();
      if (!els.projectDialog.open) openProjectDialog();
      return;
    }
    if (isTyping || event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.key.toLocaleLowerCase("en") === "n") {
      event.preventDefault();
      els.quickTitle.focus();
    } else if (event.key === "/") {
      event.preventDefault();
      els.search.focus();
      els.search.select();
    } else if (event.key === "?") {
      event.preventDefault();
      if (!els.shortcutsDialog.open) els.shortcutsDialog.showModal();
    }
  });

  els.themeToggle.addEventListener("click", toggleTheme);
  els.densityToggle.addEventListener("click", toggleDensity);
  els.importThemeButton.addEventListener("click", () => els.themeImportFile.click());
  els.themeImportFile.addEventListener("change", async () => {
    const file = els.themeImportFile.files?.[0];
    if (!file) return;
    try {
      const result = await window.FlowboardThemeManager.importFile(file);
      applyTheme(document.documentElement.dataset.theme || "light");
      updateThemeManagerControls();
      toast(result.updated
        ? `Тема «${result.name}» обновлена и сохранена`
        : `Тема «${result.name}» добавлена в библиотеку`, "success");
    } catch (error) {
      toast(error.message || "Не удалось импортировать тему", "error");
    } finally {
      els.themeImportFile.value = "";
    }
  });
  els.exportThemeButton.addEventListener("click", () => {
    try {
      const name = window.FlowboardThemeManager.downloadTheme();
      toast(`Тема «${name}» экспортирована`, "success");
    } catch (error) {
      toast(error.message || "Не удалось экспортировать тему", "error");
    }
  });
  els.savedThemesSelect.addEventListener("change", () => {
    try {
      const result = window.FlowboardThemeManager.selectTheme(els.savedThemesSelect.value);
      applyTheme(document.documentElement.dataset.theme || "light");
      updateThemeManagerControls();
      toast(`Тема «${result.name}» активирована`, "success");
    } catch (error) {
      updateThemeManagerControls();
      toast(error.message || "Не удалось переключить тему", "error");
    }
  });
  els.deleteThemeButton.addEventListener("click", () => {
    const themeId = els.savedThemesSelect.value;
    if (!themeId || themeId === "builtin") return;
    const name = window.FlowboardThemeManager.getThemeName(themeId);
    if (!window.confirm(`Удалить тему «${name}» из библиотеки? Это действие нельзя отменить.`)) return;
    try {
      window.FlowboardThemeManager.deleteTheme(themeId);
      applyTheme(document.documentElement.dataset.theme || "light");
      updateThemeManagerControls();
      toast(`Тема «${name}» удалена из библиотеки`, "success");
    } catch (error) {
      toast(error.message || "Не удалось удалить тему", "error");
    }
  });
  els.resetThemeButton.addEventListener("click", () => {
    try {
      window.FlowboardThemeManager.resetTheme();
      applyTheme(document.documentElement.dataset.theme || "light");
      updateThemeManagerControls();
      toast("Возвращена стандартная палитра Flowboard", "success");
    } catch (error) {
      toast(error.message || "Не удалось сбросить тему", "error");
    }
  });
  els.shortcutsButton.addEventListener("click", () => els.shortcutsDialog.showModal());
  els.closeShortcuts.addEventListener("click", () => els.shortcutsDialog.close());
  els.shortcutsDialog.addEventListener("click", (event) => {
    if (event.target === els.shortcutsDialog) els.shortcutsDialog.close();
  });
  els.closeProjectDialog.addEventListener("click", () => els.projectDialog.close());
  els.projectDialog.addEventListener("click", (event) => {
    if (event.target === els.projectDialog) els.projectDialog.close();
  });
  els.projectCommandSearch.addEventListener("input", () => renderProjectCommands(els.projectCommandSearch.value));
  applyTheme(document.documentElement.dataset.theme || "light");
  updateThemeManagerControls();
  applyDensity(state.density);

  function readStoredArchivedProjects() {
    try {
      const value = JSON.parse(readStorage("flowboard-archived-projects", "[]"));
      return Array.isArray(value)
        ? [...new Set(value.filter((slug) => typeof slug === "string" && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)))]
        : [];
    } catch {
      return [];
    }
  }

  let archivedProjectSlugs = readStoredArchivedProjects();

  // Keep archived projects in the saved project registry so their history is preserved,
  // but exclude them from the project selector and the keyboard project switcher.
  const persistProjectStateBeforeArchive = persistProjectState;
  persistProjectState = function persistProjectStateWithArchive() {
    persistProjectStateBeforeArchive();
    writeStorage("flowboard-archived-projects", JSON.stringify(archivedProjectSlugs));
  };

  populateProjectFilter = function populateProjectFilterWithArchive() {
    const archived = new Set(archivedProjectSlugs);
    const detected = state.tasks.flatMap(taskTags).map(projectFromTag).filter((slug) => slug && !archived.has(slug));
    state.projects = [...new Set([...state.projects, ...detected])].sort((a, b) => a.localeCompare(b, "ru"));
    els.projectFilter.replaceChildren(new Option("Все проекты", ""));
    state.projects
      .filter((slug) => !archived.has(slug))
      .forEach((slug) => els.projectFilter.appendChild(new Option(projectLabel(slug), slug)));
    if (!state.projects.includes(state.project) || archived.has(state.project)) state.project = "";
    els.projectFilter.value = state.project;
    persistProjectState();
  };

  renderProjectCommands = function renderActiveProjectCommands(query = "") {
    const normalizedQuery = normalizeSearch(query);
    const archived = new Set(archivedProjectSlugs);
    const projects = [
      { slug: "", label: "Все проекты" },
      ...state.projects.filter((slug) => !archived.has(slug)).map((slug) => ({ slug, label: projectLabel(slug) })),
    ].filter((project) => !normalizedQuery
      || normalizeSearch(project.label).includes(normalizedQuery)
      || normalizeSearch(project.slug).includes(normalizedQuery));
    els.projectCommandList.replaceChildren();
    if (!projects.length) {
      els.projectCommandList.appendChild(make("p", "project-command-empty", "Проектов не найдено"));
      return;
    }
    projects.forEach((project) => {
      const button = make("button", "project-command-option");
      button.type = "button";
      button.textContent = project.label;
      button.setAttribute("aria-current", String(project.slug === state.project));
      button.appendChild(make("span", "project-command-mark", project.slug === state.project ? "✓" : "↵"));
      button.addEventListener("click", () => {
        state.project = project.slug;
        els.projectFilter.value = project.slug;
        persistProjectState();
        renderBoard();
        els.projectDialog.close();
        els.quickTitle.focus();
      });
      els.projectCommandList.appendChild(button);
    });
  };

  const projectManagerStyles = document.createElement("style");
  projectManagerStyles.textContent = `
    .manage-projects-dialog { width: min(620px, calc(100vw - 28px)); max-height: min(82vh, 760px); overflow: auto; }
    .manage-projects-help { margin: 12px 0 18px; color: var(--muted); font-size: 13px; line-height: 1.5; }
    .project-manager-section { margin-top: 16px; }
    .project-manager-section + .project-manager-section { margin-top: 20px; padding-top: 18px; border-top: 1px solid var(--line); }
    .project-manager-section-heading { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
    .project-manager-section-heading h3 { margin: 0; color: var(--ink); font-size: 14px; font-weight: 650; }
    .project-manager-count { display: inline-flex; align-items: center; justify-content: center; min-width: 22px; height: 22px; padding: 0 6px; border: 1px solid var(--line); border-radius: 999px; color: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
    .project-manager-list { display: grid; gap: 7px; }
    .project-manager-item { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-width: 0; padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface-soft, var(--surface)); }
    .project-manager-copy { display: grid; gap: 3px; min-width: 0; }
    .project-manager-name { overflow-wrap: anywhere; color: var(--ink); font-size: 13px; font-weight: 600; }
    .project-manager-key { color: var(--muted); font-size: 11px; overflow-wrap: anywhere; }
    .project-manager-action { flex: 0 0 auto; min-height: 32px; padding: 0 10px; font-size: 12px; }
    .project-manager-action.is-archive { color: var(--red, var(--muted)); }
    .project-manager-empty { margin: 0; padding: 12px; border: 1px dashed var(--line); border-radius: 10px; color: var(--muted); font-size: 12px; line-height: 1.5; }
    .project-manager-empty[hidden] { display: none; }
    @media (max-width: 480px) {
      .manage-projects-dialog { width: calc(100vw - 20px); padding: 16px; }
      .project-manager-item { align-items: flex-start; gap: 8px; padding: 9px; }
      .project-manager-action { padding-inline: 7px; }
    }
  `;
  document.head.appendChild(projectManagerStyles);

  const manageProjectsButton = make("button", "button button-quiet toolbar-menu-item manage-projects-button");
  manageProjectsButton.type = "button";
  manageProjectsButton.setAttribute("aria-label", "Управление проектами");
  manageProjectsButton.title = "Управление проектами";
  const manageProjectsIcon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  manageProjectsIcon.setAttribute("class", "toolbar-menu-item-icon");
  manageProjectsIcon.setAttribute("viewBox", "0 0 20 20");
  manageProjectsIcon.setAttribute("aria-hidden", "true");
  manageProjectsIcon.setAttribute("focusable", "false");
  const manageProjectsIconPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
  manageProjectsIconPath.setAttribute("d", "M3.5 3.5h5v5h-5zM11.5 3.5h5v5h-5zM3.5 11.5h5v5h-5zM11.5 11.5h5v5h-5z");
  manageProjectsIcon.append(manageProjectsIconPath);
  manageProjectsButton.append(manageProjectsIcon, make("span", "manage-projects-label", "Управление проектами"));
  $("#settings-other-heading").parentElement.append(manageProjectsButton);

  const manageProjectsDialog = document.createElement("dialog");
  manageProjectsDialog.id = "manage-projects-dialog";
  manageProjectsDialog.className = "shortcuts-dialog manage-projects-dialog";
  manageProjectsDialog.setAttribute("aria-labelledby", "manage-projects-heading");
  manageProjectsDialog.setAttribute("aria-describedby", "manage-projects-help");

  const manageProjectsHeader = make("div", "shortcuts-dialog-header");
  const manageProjectsTitleBlock = make("div");
  manageProjectsTitleBlock.append(
    make("p", "eyebrow", "ПРОЕКТЫ"),
    make("h2", "", "Управление проектами"),
  );
  manageProjectsTitleBlock.lastElementChild.id = "manage-projects-heading";
  const closeManageProjectsButton = make("button", "icon-button", "×");
  closeManageProjectsButton.type = "button";
  closeManageProjectsButton.setAttribute("aria-label", "Закрыть управление проектами");
  closeManageProjectsButton.title = "Закрыть";
  manageProjectsHeader.append(manageProjectsTitleBlock, closeManageProjectsButton);
  manageProjectsDialog.append(manageProjectsHeader);
  manageProjectsDialog.append(make("p", "manage-projects-help", "Архив скрывает проект из обычного списка, не удаляя задачи и теги. Архивный проект можно восстановить в любое время."));

  function createProjectManagerSection(id, title, emptyText) {
    const section = make("section", "project-manager-section");
    section.setAttribute("aria-labelledby", `${id}-heading`);
    const heading = make("div", "project-manager-section-heading");
    const titleNode = make("h3", "", title);
    titleNode.id = `${id}-heading`;
    const count = make("span", "project-manager-count", "0");
    const list = make("div", "project-manager-list");
    list.setAttribute("role", "list");
    const empty = make("p", "project-manager-empty", emptyText);
    section.append(heading, list, empty);
    heading.append(titleNode, count);
    manageProjectsDialog.append(section);
    return { count, list, empty };
  }

  const activeProjectSection = createProjectManagerSection("active-projects", "Активные", "Активных проектов пока нет.");
  const archivedProjectSection = createProjectManagerSection("archived-projects", "Архивные", "В архиве пока нет проектов.");
  document.body.append(manageProjectsDialog);

  function renderProjectManagerList(section, projects, actionLabel, actionClass, onAction) {
    section.list.replaceChildren();
    section.empty.hidden = projects.length > 0;
    projects.forEach((slug) => {
      const item = make("div", "project-manager-item");
      item.setAttribute("role", "listitem");
      const copy = make("div", "project-manager-copy");
      copy.append(make("span", "project-manager-name", projectLabel(slug)), make("code", "project-manager-key", slug));
      const action = make("button", `button button-small button-quiet project-manager-action ${actionClass}`, actionLabel);
      action.type = "button";
      action.addEventListener("click", () => onAction(slug));
      item.append(copy, action);
      section.list.append(item);
    });
    section.count.textContent = String(projects.length);
  }

  function renderProjectManager() {
    const archived = new Set(archivedProjectSlugs);
    const activeProjects = [...new Set(state.projects)].filter((slug) => !archived.has(slug))
      .sort((a, b) => a.localeCompare(b, "ru"));
    const archivedProjects = [...archived].sort((a, b) => a.localeCompare(b, "ru"));
    renderProjectManagerList(activeProjectSection, activeProjects, "В архив", "is-archive", archiveProject);
    renderProjectManagerList(archivedProjectSection, archivedProjects, "Восстановить", "is-restore", restoreProject);
  }

  function openManageProjectsDialog() {
    if (manageProjectsDialog.open) return;
    renderProjectManager();
    manageProjectsDialog.showModal();
    closeManageProjectsButton.focus({ preventScroll: true });
  }

  function archiveProject(slug) {
    if (!state.projects.includes(slug) || archivedProjectSlugs.includes(slug)) return;
    archivedProjectSlugs = [...new Set([...archivedProjectSlugs, slug])].sort((a, b) => a.localeCompare(b, "ru"));
    if (state.project === slug) state.project = "";
    populateProjectFilter();
    renderBoard();
    renderProjectManager();
    toast(`Проект «${projectLabel(slug)}» перемещён в архив`);
  }

  function restoreProject(slug) {
    if (!archivedProjectSlugs.includes(slug)) return;
    archivedProjectSlugs = archivedProjectSlugs.filter((project) => project !== slug);
    state.projects = [...new Set([...state.projects, slug])].sort((a, b) => a.localeCompare(b, "ru"));
    populateProjectFilter();
    renderBoard();
    renderProjectManager();
    toast(`Проект «${projectLabel(slug)}» восстановлен`);
  }

  manageProjectsButton.addEventListener("click", openManageProjectsDialog);
  closeManageProjectsButton.addEventListener("click", () => manageProjectsDialog.close());
  manageProjectsDialog.addEventListener("click", (event) => {
    if (event.target === manageProjectsDialog) manageProjectsDialog.close();
  });
  manageProjectsDialog.addEventListener("close", () => $("#settings-menu > summary").focus({ preventScroll: true }));
  manageProjectsDialog.addEventListener("keydown", (event) => {
    // Keep workspace shortcuts from leaking out of the modal without blocking input typing.
    event.stopPropagation();
    if (event.key === "Escape") {
      event.preventDefault();
      manageProjectsDialog.close();
    }
  });
  initializeSortables();
  /* Keep the title and save status fixed while the workspace and properties scroll independently. */
  const taskPanelHeader = make("div", "task-panel-header");
  const taskPanelContent = make("div", "task-form-content");
  const taskPropertiesSidebar = make("aside", "task-properties-sidebar");
  const taskPanelFooter = make("div", "task-panel-footer");
  const taskPanelFooterNodes = new Set([els.taskMeta, els.taskAutosaveStatus]);
  const taskPropertiesNodes = new Set([
    $(".field-grid", els.taskForm),
    $(".attachment-section", els.taskForm),
  ]);
  Array.from(els.taskForm.children).forEach((child) => {
    if (child === els.taskId) return;
    if (child.classList.contains("task-title-field")) {
      taskPanelHeader.appendChild(child);
    } else if (taskPropertiesNodes.has(child)) {
      taskPropertiesSidebar.appendChild(child);
    } else if (taskPanelFooterNodes.has(child)) {
      taskPanelFooter.appendChild(child);
    } else {
      taskPanelContent.appendChild(child);
    }
  });
  taskPanelContent.appendChild(taskPropertiesSidebar);
  els.taskForm.replaceChildren(els.taskId, taskPanelHeader, taskPanelContent, taskPanelFooter);

  // Keep editor controls in one lightweight outline-icon style.
  const taskPanelIconNamespace = "http://www.w3.org/2000/svg";
  function createTaskPanelIcon(paths, size = 17) {
    const svg = document.createElementNS(taskPanelIconNamespace, "svg");
    svg.setAttribute("viewBox", "0 0 20 20");
    svg.setAttribute("width", String(size));
    svg.setAttribute("height", String(size));
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "1.65");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    paths.forEach((data) => {
      const path = document.createElementNS(taskPanelIconNamespace, "path");
      path.setAttribute("d", data);
      svg.appendChild(path);
    });
    return svg;
  }

  // The reference badge is informative, not a second button.
  els.taskTitleReference.setAttribute("role", "note");
  const taskTitlePencil = $(".task-title-pencil", els.taskTitleDisplay);
  if (taskTitlePencil) {
    taskTitlePencil.replaceChildren(createTaskPanelIcon([
      "m4 14.8-.7 2.8 2.8-.7 9.8-9.8a1.8 1.8 0 0 0-2.6-2.6Z",
      "m12.1 5.6 2.6 2.6",
    ], 15));
  }
  const taskMoreIcon = $(".task-action-icon", els.taskMoreToggle);
  if (taskMoreIcon) {
    taskMoreIcon.replaceWith(createTaskPanelIcon(["M4 10h.01M10 10h.01M16 10h.01"], 17));
    $("svg", els.taskMoreToggle).setAttribute("stroke-width", "2.8");
  }
  if (!$("svg", els.togglePreview)) {
    els.togglePreview.replaceChildren(createTaskPanelIcon([
      "m4 14.8-.7 2.8 2.8-.7 9.8-9.8a1.8 1.8 0 0 0-2.6-2.6Z",
      "m12.1 5.6 2.6 2.6",
    ], 16));
  }

  const taskTagError = make("p", "task-tag-error");
  taskTagError.id = "task-tag-error";
  taskTagError.setAttribute("role", "alert");
  taskTagError.setAttribute("aria-live", "polite");
  taskTagError.hidden = true;
  els.taskTagInput.setAttribute("aria-describedby", taskTagError.id);
  els.taskTagInput.setAttribute("aria-invalid", "false");
  els.taskTagList.classList.remove("tag-choice-list");
  els.taskTagList.classList.add("tag-choice-groups");
  els.taskTagList.setAttribute("aria-label", "Тип, проект и теги задачи");
  els.taskTagCreateRow.hidden = false;
  els.taskTagCustomToggle.hidden = true;

  function setTaskTagError(message) {
    taskTagError.textContent = message;
    taskTagError.hidden = !message;
    els.taskTagInput.setAttribute("aria-invalid", String(Boolean(message)));
  }

  tagChoiceDetails = function tagChoiceDetailsForGroupedEditor(value) {
    const tag = String(value || "").trim();
    const normalized = tag.toLocaleLowerCase("ru");
    if (Object.hasOwn(TASK_TYPE_LABELS, normalized)) {
      return { value: normalized, label: TASK_TYPE_LABELS[normalized], kind: "type" };
    }
    const project = projectFromTag(tag);
    if (project) {
      return { value: projectTag(project), label: projectLabel(project), kind: "project" };
    }
    return { value: tag, label: tag, kind: "custom" };
  };

  availableTaskTagChoices = function availableTaskTagChoicesGrouped() {
    const choices = new Map();
    const addChoice = (value) => {
      const detail = tagChoiceDetails(value);
      if (!detail.value) return;
      const key = detail.value.toLocaleLowerCase("ru");
      if (!choices.has(key)) choices.set(key, detail);
    };

    Object.keys(TASK_TYPE_LABELS).forEach(addChoice);
    const archived = typeof archivedProjectSlugs === "undefined"
      ? new Set()
      : new Set(archivedProjectSlugs);
    state.projects.filter((slug) => !archived.has(slug)).forEach((slug) => addChoice(projectTag(slug)));
    const currentTags = editableTaskTags();
    state.tasks.flatMap(taskTags).forEach((tag) => {
      const detail = tagChoiceDetails(tag);
      const project = projectFromTag(tag);
      if (detail.kind === "project" && archived.has(project)
        && !currentTags.some((currentTag) => projectFromTag(currentTag) === project)) return;
      addChoice(tag);
    });
    currentTags.forEach(addChoice);

    const kindOrder = { type: 0, project: 1, custom: 2 };
    const typeOrder = Object.keys(TASK_TYPE_LABELS);
    return [...choices.values()].sort((a, b) => {
      if (kindOrder[a.kind] !== kindOrder[b.kind]) return kindOrder[a.kind] - kindOrder[b.kind];
      if (a.kind === "type") return typeOrder.indexOf(a.value) - typeOrder.indexOf(b.value);
      return a.label.localeCompare(b.label, "ru");
    });
  };

  renderTaskTagEditor = function renderGroupedTaskTagEditor() {
    const tags = editableTaskTags();
    const selected = new Set(tags.map((tag) => tag.toLocaleLowerCase("ru")));
    const choices = availableTaskTagChoices();
    const groupDefinitions = [
      { kind: "type", label: "Тип" },
      { kind: "project", label: "Проект" },
      { kind: "custom", label: "Теги" },
    ];
    els.taskTags.value = tags.join(", ");
    els.taskTagList.replaceChildren();

    groupDefinitions.forEach((definition) => {
      const group = make("section", `tag-choice-group tag-choice-group-${definition.kind}`);
      const heading = make("h4", "tag-choice-group-heading", definition.label);
      const list = make("div", "tag-choice-list");
      list.setAttribute("role", "group");
      list.setAttribute("aria-label", definition.kind === "project" ? "Проект, можно выбрать один" : definition.label);
      const groupChoices = choices.filter((choice) => choice.kind === definition.kind);

      groupChoices.forEach((choice) => {
        const isSelected = selected.has(choice.value.toLocaleLowerCase("ru"));
        const noun = definition.kind === "project" ? "проект" : definition.kind === "type" ? "тип" : "тег";
        const option = make("button", `tag-choice tag-choice-${choice.kind}${choice.kind === "type" ? ` tag-choice-${choice.value}` : ""}`, choice.label);
        option.type = "button";
        option.dataset.tag = choice.value;
        option.setAttribute("aria-pressed", String(isSelected));
        option.setAttribute("aria-label", `${isSelected ? "Снять выбор" : "Выбрать"}: ${noun} ${choice.label}`);
        option.title = `${isSelected ? "Снять выбор" : "Выбрать"}: ${choice.label}`;
        option.addEventListener("click", () => toggleTaskTagChoice(choice.value));
        list.appendChild(option);
      });

      if (!groupChoices.length && definition.kind === "project") {
        list.appendChild(make("p", "tag-choice-empty", "Активных проектов пока нет."));
      }
      if (definition.kind === "custom") {
        list.appendChild(els.taskTagCreateRow);
        group.append(heading, list, taskTagError);
      } else {
        group.append(heading, list);
      }
      els.taskTagList.appendChild(group);
    });
    els.taskTagCustomToggle.hidden = true;
    els.taskTagCreateRow.hidden = false;
  };

  toggleTaskTagChoice = function toggleGroupedTaskTagChoice(value) {
    const detail = tagChoiceDetails(value);
    const tags = editableTaskTags();
    const normalized = detail.value.toLocaleLowerCase("ru");

    if (detail.kind === "project") {
      const alreadySelected = tags.some((tag) => {
        const current = tagChoiceDetails(tag);
        return current.kind === "project" && current.value.toLocaleLowerCase("ru") === normalized;
      });
      const nextTags = tags.filter((tag) => tagChoiceDetails(tag).kind !== "project");
      if (!alreadySelected) nextTags.push(detail.value);
      tags.splice(0, tags.length, ...nextTags);
    } else {
      const existingIndex = tags.findIndex((tag) => tag.toLocaleLowerCase("ru") === normalized);
      if (existingIndex >= 0) tags.splice(existingIndex, 1);
      else tags.push(detail.value);
    }

    const combined = tags.join(", ");
    if (combined.length > 1000) {
      toast("Список тегов не должен превышать 1000 символов", "error");
      return;
    }
    setTaskTagError("");
    els.taskTags.value = combined;
    renderTaskTagEditor();
    scheduleTaskDraftSave();
  };

  addTaskTags = function addTaskTagsWithValidation(value = els.taskTagInput.value) {
    const incoming = String(value ?? "").split(",").map((tag) => tag.trim()).filter(Boolean);
    if (!incoming.length) {
      setTaskTagError("Введите название тега.");
      els.taskTagInput.focus({ preventScroll: true });
      return;
    }

    if (incoming.some((tag) => projectFromTag(tag))) {
      setTaskTagError("Проект выбирается в группе «Проект», а не добавляется как обычный тег.");
      els.taskTagInput.focus({ preventScroll: true });
      return;
    }

    const existing = editableTaskTags();
    const existingValues = new Set(existing.map((tag) => tag.toLocaleLowerCase("ru")));
    const duplicate = incoming.find((tag, index) => {
      const normalized = tag.toLocaleLowerCase("ru");
      return existingValues.has(normalized)
        || incoming.slice(0, index).some((previous) => previous.toLocaleLowerCase("ru") === normalized);
    });
    if (duplicate) {
      setTaskTagError(`Тег «${duplicate}» уже добавлен.`);
      els.taskTagInput.focus({ preventScroll: true });
      return;
    }

    const combined = [...existing, ...incoming].join(", ");
    if (combined.length > 1000) {
      setTaskTagError("Список тегов не должен превышать 1000 символов.");
      els.taskTagInput.focus({ preventScroll: true });
      return;
    }

    setTaskTagError("");
    els.taskTags.value = combined;
    els.taskTagInput.value = "";
    renderTaskTagEditor();
    scheduleTaskDraftSave();
    els.taskTagInput.focus({ preventScroll: true });
  };

  els.taskTagInput.addEventListener("input", () => setTaskTagError(""));

  function updateDescriptionActionIcon() {
    const isEditing = state.activeTaskTab === "result"
      ? !state.resultPreviewVisible
      : !state.previewVisible;
    const icon = isEditing
      ? ["M3.5 10.5 8 15l8.5-9"]
      : [
        "m4 14.8-.7 2.8 2.8-.7 9.8-9.8a1.8 1.8 0 0 0-2.6-2.6Z",
        "m12.1 5.6 2.6 2.6",
      ];
    els.togglePreview.replaceChildren(createTaskPanelIcon(icon, 16));
    updateTaskWorkspaceHeading();
  }

  const setDescriptionEditingBeforeRedesign = setDescriptionEditing;
  setDescriptionEditing = async function setDescriptionEditingWithStableIcon(editing) {
    await setDescriptionEditingBeforeRedesign(editing);
    updateDescriptionActionIcon();
  };

  const closePanelBeforeRedesign = closePanel;
  closePanel = function closePanelWithStableEditorIcon() {
    closePanelBeforeRedesign();
    updateDescriptionActionIcon(false);
  };

  const renderAttachmentsBeforeRedesign = renderAttachments;
  renderAttachments = function renderAttachmentsWithClearEmptyState(attachments) {
    renderAttachmentsBeforeRedesign(attachments);
    const emptyState = $(".attachment-empty", els.attachmentList);
    if (emptyState) {
      emptyState.textContent = "Нет вложений. Нажмите «Добавить», чтобы прикрепить файл.";
    }
  };

  const attachmentUploadLabel = make("span", "attachment-icon-label", "Добавить");
  if (!$(".attachment-icon-label", els.toggleAttachmentUpload)) {
    els.toggleAttachmentUpload.appendChild(attachmentUploadLabel);
  }
  els.toggleAttachmentUpload.setAttribute("aria-label", "Добавить вложение");
  els.toggleAttachmentUpload.title = "Добавить вложение или перетащить файлы";

  els.copyDescription.setAttribute("aria-label", "Копировать");
  els.copyDescription.title = "Копировать";

  const openTaskPanelBeforeRedesign = openTaskPanel;
  openTaskPanel = async function openTaskPanelWithAccessibleReference(taskId) {
    await openTaskPanelBeforeRedesign(taskId);
    const actualId = state.selectedTask?.id;
    updateDescriptionActionIcon();
    if (actualId !== undefined && String(actualId) === String(taskId)) {
      els.taskTitleReference.setAttribute("aria-label", `Номер задачи ${actualId}`);
      els.taskTitleReference.title = `Номер задачи ${actualId}`;
    }
  };
  initialize();
})();
