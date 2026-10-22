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

  const state = {
    tasks: [],
    selectedTask: null,
    doneExpanded: false,
    search: "",
    tag: "",
    project: readStorage("flowboard-last-project"),
    projects: readStoredProjects(),
    quickTaskType: "",
    focusTaskId: Number(readStorage("flowboard-focus-task", "0")) || null,
    density: readStorage("flowboard-density", "comfortable") === "compact" ? "compact" : "comfortable",
    dragOrigin: null,
    wipLimit: 3,
    maxFileSizeMb: 20,
    previewVisible: false,
    previewRequest: 0,
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const els = {
    totalCount: $("#total-count"),
    quickForm: $("#quick-add-form"),
    quickTitle: $("#quick-title"),
    quickTaskType: $("#quick-task-type"),
    search: $("#search-input"),
    projectFilter: $("#project-filter"),
    addProject: $("#add-project"),
    tagFilter: $("#tag-filter"),
    filterSummary: $("#filter-summary"),
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
    taskStatus: $("#task-status"),
    taskTags: $("#task-tags"),
    taskDescription: $("#task-description"),
    descriptionPreview: $("#description-preview"),
    togglePreview: $("#toggle-preview"),
    closeTask: $("#close-task"),
    deleteTask: $("#delete-task"),
    saveTask: $("#save-task"),
    focusTask: $("#focus-task"),
    attachmentInput: $("#attachment-files"),
    chooseFiles: $("#choose-files"),
    attachmentDropzone: $("#attachment-dropzone"),
    attachmentList: $("#attachment-list"),
    attachmentCount: $("#attachment-count"),
    maxFileMb: $("#max-file-mb"),
    taskMeta: $("#task-meta"),
    toastRegion: $("#toast-region"),
    toggleDone: $("#toggle-done"),
    wipWarning: $("#wip-warning"),
    themeToggle: $("#theme-toggle"),
    themeToggleIcon: $("#theme-toggle-icon"),
    themeToggleLabel: $("#theme-toggle-label"),
    themeColor: $("meta[name=\"theme-color\"]"),
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

  function applyTheme(theme, persist = false) {
    const normalizedTheme = theme === "dark" ? "dark" : "light";
    const isDark = normalizedTheme === "dark";
    document.documentElement.dataset.theme = normalizedTheme;
    els.themeToggle.setAttribute("aria-pressed", String(isDark));
    els.themeToggle.setAttribute(
      "aria-label",
      `Переключить на ${isDark ? "светлую" : "тёмную"} тему`,
    );
    els.themeToggle.title = `Переключить на ${isDark ? "светлую" : "тёмную"} тему`;
    els.themeToggleIcon.textContent = isDark ? "☀" : "☾";
    els.themeToggleLabel.textContent = isDark ? "Светлая тема" : "Тёмная тема";
    els.themeColor.setAttribute("content", isDark ? "#0c101a" : "#f4f6fb");

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

  function applyDensity(density, persist = false) {
    state.density = density === "compact" ? "compact" : "comfortable";
    document.documentElement.dataset.density = state.density;
    const compact = state.density === "compact";
    els.densityToggle.setAttribute("aria-pressed", String(compact));
    els.densityToggle.setAttribute("aria-label", compact ? "Включить комфортные карточки" : "Включить компактные карточки");
    els.densityToggle.title = compact ? "Включить комфортную плотность карточек" : "Включить компактную плотность карточек";
    els.densityToggleLabel.textContent = compact ? "Компактно" : "Комфортно";
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
      throw new Error(Array.isArray(message) ? message.map((entry) => entry.msg || String(entry)).join("; ") : (message || `Ошибка ${response.status}`));
    }
    return data;
  }

  function toast(message, type = "success", actionLabel = "", onAction = null) {
    $$(".toast[data-has-undo=\"true\"]", els.toastRegion).forEach((node) => node.remove());
    const node = make("div", `toast${type === "error" ? " error" : ""}`);
    if (actionLabel && typeof onAction === "function") node.dataset.hasUndo = "true";
    const messageNode = make("span", "toast-message", message);
    node.appendChild(messageNode);
    if (actionLabel && typeof onAction === "function") {
      const action = make("button", "toast-action", actionLabel);
      action.type = "button";
      action.addEventListener("click", async () => {
        action.disabled = true;
        window.clearTimeout(timer);
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
    els.toastRegion.appendChild(node);
    const timer = window.setTimeout(() => node.remove(), actionLabel ? 8500 : 4200);
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
  const PROJECT_ACCENTS = ["#6975e8", "#239b8a", "#bd8242", "#a16ac8", "#477fbb", "#c56579"];

  function setQuickTaskType(type) {
    const normalizedType = String(type || "").toLowerCase();
    state.quickTaskType = Object.hasOwn(TASK_TYPE_LABELS, normalizedType) ? normalizedType : "";
    $$("[data-task-type]", els.quickTaskType).forEach((button) => {
      const selected = button.dataset.taskType === state.quickTaskType;
      button.setAttribute("aria-pressed", String(selected));
    });
  }

  function taskDescriptionExcerpt(description, limit = 112) {
    const plainText = String(description || "")
      .replace(/```[\s\S]*?```/g, " ")
      .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
      .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
      .replace(/[`*_~>#]/g, "")
      .replace(/\s+/g, " ")
      .trim();
    if (!plainText) return "";
    return plainText.length > limit ? `${plainText.slice(0, limit - 1).trimEnd()}…` : plainText;
  }

  function projectAccent(slug) {
    let hash = 0;
    for (const char of String(slug || "")) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
    return PROJECT_ACCENTS[hash % PROJECT_ACCENTS.length];
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

    const metadata = make("div", "task-card-meta");
    const projectChip = make("span", `task-project-chip${project ? "" : " task-project-chip-empty"}`);
    const projectMark = make("span", "task-project-mark");
    if (project) projectMark.style.backgroundColor = projectAccent(project);
    projectChip.appendChild(projectMark);
    projectChip.appendChild(make("span", "task-project-name", project ? projectLabel(project) : "Без проекта"));
    metadata.appendChild(projectChip);
    if (typeTag) {
      metadata.appendChild(make("span", `task-type-chip task-type-${typeTag.toLowerCase()}`, TASK_TYPE_LABELS[typeTag.toLowerCase()]));
    }
    card.appendChild(metadata);

    const excerpt = taskDescriptionExcerpt(task.description);
    if (excerpt) card.appendChild(make("p", "task-card-excerpt", excerpt));

    if (hiddenTags.length) {
      const tagRow = make("div", "task-tags");
      hiddenTags.slice(0, 2).forEach((tag) => tagRow.appendChild(make("span", "tag-pill", tag)));
      if (hiddenTags.length > 2) tagRow.appendChild(make("span", "tag-pill tag-pill-more", `+${hiddenTags.length - 2}`));
      card.appendChild(tagRow);
    }

    const footer = make("div", "task-card-footer");
    const metrics = make("span", "task-card-metrics");
    if (task.attachments_count) {
      const attachment = make("span", "attachment-mini", `↗ ${task.attachments_count}`);
      attachment.setAttribute("aria-label", `Вложений: ${task.attachments_count}`);
      metrics.appendChild(attachment);
    }
    footer.appendChild(metrics);
    footer.appendChild(make("time", "task-updated", formatDate(task.updated_at)));
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

  function renderBoard() {
    const visibleTasks = state.tasks.filter(matchesFilters);
    els.totalCount.textContent = pluralTasks(state.tasks.length);
    els.filterSummary.textContent = state.search || state.tag || state.project
      ? `Показано: ${visibleTasks.length} из ${state.tasks.length}`
      : "";

    for (const status of STATUSES) {
      const column = $(`.board-column[data-column="${status}"]`);
      const list = $(`.task-list[data-status="${status}"]`);
      const statusTasks = visibleTasks.filter((task) => task.status === status);
      $(`#count-${status}`).textContent = String(statusTasks.length);
      list.replaceChildren();

      let tasksToRender = statusTasks;
      if (status === "done" && !state.doneExpanded) {
        const mostRecent = [...statusTasks]
          .sort((a, b) => String(b.closed_at || b.updated_at).localeCompare(String(a.closed_at || a.updated_at)))
          .slice(0, 5);
        tasksToRender = mostRecent.sort((a, b) => Number(a.position) - Number(b.position));
        els.toggleDone.hidden = statusTasks.length <= 5;
        els.toggleDone.textContent = `Показать все (${statusTasks.length})`;
        els.toggleDone.setAttribute("aria-expanded", "false");
      } else if (status === "done") {
        els.toggleDone.hidden = statusTasks.length <= 5;
        els.toggleDone.textContent = "Свернуть";
        els.toggleDone.setAttribute("aria-expanded", "true");
      }

      tasksToRender.forEach((task) => list.appendChild(makeTaskCard(task)));
      column.classList.toggle("is-empty", tasksToRender.length === 0);
    }

    const doingCount = state.tasks.filter((task) => task.status === "doing").length;
    const overLimit = doingCount > state.wipLimit;
    $(".board-column[data-column='doing']").classList.toggle("wip-over-limit", overLimit);
    els.wipWarning.hidden = !overLimit;
    renderFocusBar();
  }

  function renderFocusBar() {
    const task = state.tasks.find((item) => item.id === state.focusTaskId);
    if (!task) {
      if (state.focusTaskId !== null) {
        state.focusTaskId = null;
        writeStorage("flowboard-focus-task", "");
      }
      els.focusBar.hidden = true;
      els.focusTask.textContent = "◎ В фокус";
      return;
    }
    els.focusBar.hidden = false;
    els.focusTitle.textContent = task.title;
    const project = projectForTask(task);
    els.focusProject.textContent = project ? `${projectLabel(project)} · ${STATUS_LABELS[task.status]}` : STATUS_LABELS[task.status];
    els.focusDone.disabled = task.status === "done";
    els.focusDone.textContent = task.status === "done" ? "Уже готово" : "Завершить";
    if (state.selectedTask && state.selectedTask.id === task.id) els.focusTask.textContent = "Снять с фокуса";
  }

  function setFocusedTask(taskId) {
    state.focusTaskId = taskId || null;
    writeStorage("flowboard-focus-task", state.focusTaskId ? String(state.focusTaskId) : "");
    renderBoard();
    if (state.selectedTask) {
      els.focusTask.textContent = state.selectedTask.id === state.focusTaskId ? "Снять с фокуса" : "◎ В фокус";
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
    renderBoard();
  }

  function openPanel() {
    els.overlay.hidden = false;
    els.panel.classList.add("is-open");
    els.panel.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function closePanel() {
    els.panel.classList.remove("is-open");
    els.panel.setAttribute("aria-hidden", "true");
    els.attachmentList.querySelectorAll(".attachment-preview").forEach((image) => {
      if (image.dataset.objectUrl) URL.revokeObjectURL(image.dataset.objectUrl);
    });
    els.overlay.hidden = true;
    document.body.style.overflow = "";
    state.selectedTask = null;
    state.previewVisible = false;
    els.descriptionPreview.hidden = true;
    els.taskDescription.hidden = false;
    els.togglePreview.textContent = "Предпросмотр";
  }

  async function openTaskPanel(taskId) {
    try {
      const task = await api(`/api/tasks/${taskId}`);
      state.selectedTask = task;
      els.taskId.value = String(task.id);
      els.taskTitle.value = task.title;
      els.taskStatus.value = task.status;
      els.taskTags.value = task.tags || "";
      els.taskDescription.value = task.description || "";
      els.descriptionPreview.replaceChildren();
      els.descriptionPreview.hidden = true;
      els.taskDescription.hidden = false;
      els.togglePreview.textContent = "Предпросмотр";
      state.previewVisible = false;
      els.closeTask.textContent = task.status === "done" ? "↶ Вернуть в работу" : "✓ Закрыть задачу";
      els.closeTask.dataset.action = task.status === "done" ? "reopen" : "close";
      els.taskMeta.textContent = `Создана: ${formatDateTime(task.created_at)} · Изменена: ${formatDateTime(task.updated_at)}${task.closed_at ? ` · Закрыта: ${formatDateTime(task.closed_at)}` : ""}`;
      renderAttachments(task.attachments || []);
      els.focusTask.textContent = state.focusTaskId === task.id ? "Снять с фокуса" : "◎ В фокус";
      openPanel();
      window.setTimeout(() => els.taskTitle.focus({ preventScroll: true }), 100);
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function refreshSelectedTask() {
    if (state.selectedTask) await openTaskPanel(state.selectedTask.id);
  }

  function renderAttachments(attachments) {
    els.attachmentList.querySelectorAll(".attachment-preview").forEach((image) => {
      if (image.dataset.objectUrl) URL.revokeObjectURL(image.dataset.objectUrl);
    });
    els.attachmentList.replaceChildren();
    els.attachmentCount.textContent = String(attachments.length);
    attachments.forEach((attachment) => {
      const item = make("li", "attachment-item");
      const extension = attachment.filename.includes(".") ? attachment.filename.split(".").pop().toLowerCase() : "FILE";
      const isPreviewableImage = ["png", "jpg", "jpeg", "gif", "webp", "avif"].includes(extension);
      if (isPreviewableImage) {
        const preview = make("img", "attachment-preview");
        preview.alt = `Предпросмотр: ${attachment.filename}`;
        preview.loading = "lazy";
        item.appendChild(preview);
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
          .catch(() => preview.remove());
      } else {
        item.appendChild(make("span", "attachment-file-icon", extension.slice(0, 4) || "FILE"));
      }
      const details = make("span", "attachment-file-details");
      const link = make("a", "", attachment.filename);
      link.href = `/api/files/${attachment.id}`;
      link.title = "Скачать файл";
      details.appendChild(link);
      details.appendChild(make("small", "", `${formatBytes(attachment.size)} · ${formatDate(attachment.created_at)}`));
      item.appendChild(details);
      const remove = make("button", "attachment-remove", "×");
      remove.type = "button";
      remove.setAttribute("aria-label", `Удалить вложение ${attachment.filename}`);
      remove.addEventListener("click", () => removeAttachment(attachment.id, attachment.filename));
      item.appendChild(remove);
      els.attachmentList.appendChild(item);
    });
  }

  async function requestMarkdownPreview() {
    const requestId = ++state.previewRequest;
    try {
      const result = await api("/api/preview-markdown", { method: "POST", body: { text: els.taskDescription.value } });
      if (requestId !== state.previewRequest || !state.previewVisible) return;
      els.descriptionPreview.innerHTML = result.html;
    } catch (error) {
      toast(`Не удалось построить предпросмотр: ${error.message}`, "error");
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

  async function handleTaskSave(event) {
    event.preventDefault();
    const taskId = Number(els.taskId.value);
    if (!taskId) return;
    els.saveTask.disabled = true;
    try {
      const previous = {
        title: state.selectedTask.title,
        description: state.selectedTask.description || "",
        status: state.selectedTask.status,
        position: state.selectedTask.position,
        tags: state.selectedTask.tags || "",
      };
      const updated = await api(`/api/tasks/${taskId}`, {
        method: "PATCH",
        body: {
          title: els.taskTitle.value,
          status: els.taskStatus.value,
          tags: els.taskTags.value,
          description: els.taskDescription.value,
        },
      });
      await loadTasks();
      await openTaskPanel(updated.id);
      toast("Изменения сохранены", "success", "Отменить", () => restoreTaskDetails(taskId, previous));
    } catch (error) {
      toast(error.message, "error");
    } finally {
      els.saveTask.disabled = false;
    }
  }

  async function handleCloseTask() {
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
      body: { title: snapshot.title, description: snapshot.description || "", tags: snapshot.tags || "" },
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

  async function handleDeleteTask() {
    const task = state.selectedTask;
    if (!task) return;
    if (!window.confirm(`Удалить задачу «${task.title}» вместе со всеми вложениями?`)) return;
    try {
      const files = await snapshotAttachmentFiles(task.attachments || []);
      const snapshot = {
        title: task.title,
        description: task.description || "",
        tags: task.tags || "",
        status: task.status,
        position: task.position,
      };
      const wasFocused = state.focusTaskId === task.id;
      await api(`/api/tasks/${task.id}`, { method: "DELETE" });
      closePanel();
      await loadTasks();
      toast("Задача удалена", "success", "Восстановить", () => restoreDeletedTask(snapshot, files, wasFocused));
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function uploadFiles(fileList) {
    const task = state.selectedTask;
    const files = Array.from(fileList || []);
    if (!task || files.length === 0) return;
    const data = new FormData();
    files.forEach((file) => data.append("files", file, file.name));
    els.chooseFiles.disabled = true;
    try {
      const uploaded = await api(`/api/tasks/${task.id}/files`, { method: "POST", body: data });
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

  async function removeAttachment(attachmentId, filename) {
    if (!window.confirm(`Удалить вложение «${filename}»?`)) return;
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
      await api(`/api/tasks/${taskId}`, {
        method: "PATCH",
        body: { status: list.dataset.status, position },
      });
      await loadTasks();
      if (previousState) {
        toast("Положение задачи изменено", "success", "Отменить", () => restoreTaskState(taskId, previousState));
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

  function addProject() {
    const raw = window.prompt("Ключ нового проекта (латиница, цифры и дефис), например storefront:");
    if (raw === null) return;
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
      await loadTasks();
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
  els.addProject.addEventListener("click", addProject);
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

  els.taskForm.addEventListener("submit", handleTaskSave);
  els.closePanel.addEventListener("click", closePanel);
  els.overlay.addEventListener("click", closePanel);
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
  els.attachmentInput.addEventListener("change", () => uploadFiles(els.attachmentInput.files));
  els.toggleDone.addEventListener("click", () => { state.doneExpanded = !state.doneExpanded; renderBoard(); });

  els.togglePreview.addEventListener("click", async () => {
    state.previewVisible = !state.previewVisible;
    els.descriptionPreview.hidden = !state.previewVisible;
    els.taskDescription.hidden = state.previewVisible;
    els.togglePreview.textContent = state.previewVisible ? "Редактировать" : "Предпросмотр";
    if (state.previewVisible) await requestMarkdownPreview();
  });
  els.taskDescription.addEventListener("input", () => {
    if (state.previewVisible) requestMarkdownPreview();
  });

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

  document.addEventListener("keydown", (event) => {
    const tag = event.target && event.target.tagName;
    const isTyping = ["INPUT", "TEXTAREA", "SELECT"].includes(tag) || event.target?.isContentEditable;
    if (event.key === "Escape") {
      if (els.shortcutsDialog.open) els.shortcutsDialog.close();
      else if (els.projectDialog.open) els.projectDialog.close();
      else if (!els.overlay.hidden) closePanel();
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
  applyDensity(state.density);

  initializeSortables();
  initialize();
})();
