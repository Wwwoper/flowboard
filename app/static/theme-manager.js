(() => {
  "use strict";

  const STORAGE_KEY = "flowboard-theme-library";
  const LEGACY_STORAGE_KEY = "flowboard-custom-theme";
  const BUILTIN_THEME_ID = "builtin";
  const MAX_FILE_BYTES = 256 * 1024;
  const MODES = ["light", "dark"];
  const COLOR_KEYS = [
    "page",
    "surface",
    "surface-soft",
    "ink",
    "ink-soft",
    "muted",
    "line",
    "line-strong",
    "accent",
    "accent-dark",
    "accent-pale",
    "green",
    "orange",
    "red",
    "gh-column",
    "gh-control",
    "gh-control-hover",
    "gh-blue-bg",
    "gh-blue-fg",
    "gh-green-bg",
    "gh-green-fg",
    "gh-yellow-bg",
    "gh-yellow-fg",
    "gh-red-bg",
    "gh-red-fg",
    "gh-purple-bg",
    "gh-purple-fg",
    "gh-primary",
    "gh-primary-hover",
    "gh-primary-ink",
    "gh-brand-start",
    "gh-brand-end",
    "gh-marker-todo",
    "gh-marker-doing",
    "gh-marker-waiting",
    "gh-marker-done",
  ];
  const COLOR_KEY_SET = new Set(COLOR_KEYS);
  const HEX_COLOR = /^#(?:[\da-f]{3}|[\da-f]{6})$/i;
  let library = readSavedLibrary();
  let activeThemeId = library.activeId;
  let activeTheme = library.themes.find((theme) => theme.id === activeThemeId) || null;

  function isObject(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function validateTheme(value) {
    if (!isObject(value)) {
      throw new Error("Файл темы должен содержать JSON-объект.");
    }
    if (value.version !== 1) {
      throw new Error("Неизвестная версия темы. Поддерживается version: 1.");
    }
    if (typeof value.name !== "string" || !value.name.trim() || value.name.trim().length > 60) {
      throw new Error("Укажите название темы длиной от 1 до 60 символов.");
    }
    if (!isObject(value.colors) || Object.keys(value.colors).some((mode) => !MODES.includes(mode))) {
      throw new Error("Поле colors должно содержать палитры light и dark.");
    }

    const colors = {};
    for (const mode of MODES) {
      const palette = value.colors[mode];
      if (!isObject(palette) || Object.keys(palette).length === 0) {
        throw new Error(`Добавьте хотя бы один цвет в палитру colors.${mode}.`);
      }
      colors[mode] = {};
      for (const [key, color] of Object.entries(palette)) {
        if (!COLOR_KEY_SET.has(key)) {
          throw new Error(`Неизвестный параметр цвета: ${key}.`);
        }
        if (typeof color !== "string" || !HEX_COLOR.test(color)) {
          throw new Error(`Цвет «${key}» должен быть в формате #RGB или #RRGGBB.`);
        }
        colors[mode][key] = color.toLowerCase();
      }
    }

    return {
      name: value.name.trim(),
      version: 1,
      colors,
    };
  }

  function createThemeId(name, themes) {
    const base = name
      .toLocaleLowerCase("en")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "theme";
    const existingIds = new Set(themes.map((theme) => theme.id));
    let id = base;
    let suffix = 2;
    while (existingIds.has(id)) id = `${base}-${suffix++}`;
    return id;
  }

  function readSavedLibrary() {
    let raw = null;
    try {
      raw = localStorage.getItem(STORAGE_KEY);
    } catch {
      return { themes: [], activeId: BUILTIN_THEME_ID };
    }

    if (raw) {
      try {
        const saved = JSON.parse(raw);
        if (isObject(saved) && Array.isArray(saved.themes)) {
          const themes = [];
          const seenIds = new Set();
          for (const entry of saved.themes) {
            try {
              if (!isObject(entry) || typeof entry.id !== "string"
                  || !/^[a-z0-9][a-z0-9-]{0,79}$/.test(entry.id)
                  || seenIds.has(entry.id)) continue;
              const theme = validateTheme(entry);
              themes.push({ id: entry.id, ...theme });
              seenIds.add(entry.id);
            } catch {
              // Ignore invalid saved entries without losing the rest of the library.
            }
          }
          const requestedId = typeof saved.activeId === "string" ? saved.activeId : BUILTIN_THEME_ID;
          const activeId = requestedId === BUILTIN_THEME_ID
            || themes.some((theme) => theme.id === requestedId)
            ? requestedId
            : BUILTIN_THEME_ID;
          return { themes, activeId };
        }
      } catch {
        // Try migrating the previous single-theme storage format below.
      }
    }

    try {
      const legacyRaw = localStorage.getItem(LEGACY_STORAGE_KEY);
      if (legacyRaw) {
        const theme = validateTheme(JSON.parse(legacyRaw));
        const migratedTheme = { id: createThemeId(theme.name, []), ...theme };
        const migrated = { themes: [migratedTheme], activeId: migratedTheme.id };
        try {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(migrated));
        } catch {
          // The in-memory migration still works if storage is unavailable.
        }
        return migrated;
      }
    } catch {
      // No valid legacy theme is available.
    }

    return { themes: [], activeId: BUILTIN_THEME_ID };
  }

  function persistLibrary(nextLibrary) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(nextLibrary));
    } catch {
      throw new Error("Не удалось сохранить библиотеку тем в браузере. Проверьте доступное место в хранилище.");
    }
  }

  function getThemes() {
    return library.themes.map(({ id, name }) => ({ id, name }));
  }

  function getActiveThemeId() {
    return activeThemeId;
  }

  function getThemeName(themeId) {
    if (themeId === BUILTIN_THEME_ID) return "Стандартная палитра Flowboard";
    return library.themes.find((theme) => theme.id === themeId)?.name || "";
  }

  function selectTheme(themeId) {
    if (themeId !== BUILTIN_THEME_ID && !library.themes.some((theme) => theme.id === themeId)) {
      throw new Error("Выбранная тема не найдена в библиотеке.");
    }
    const nextLibrary = { themes: library.themes, activeId: themeId };
    persistLibrary(nextLibrary);
    library = nextLibrary;
    activeThemeId = themeId;
    activeTheme = library.themes.find((theme) => theme.id === activeThemeId) || null;
    applyCurrentPalette();
    return { id: activeThemeId, name: getThemeName(activeThemeId) };
  }

  function deleteTheme(themeId) {
    const theme = library.themes.find((entry) => entry.id === themeId);
    if (!theme) throw new Error("Выбранная пользовательская тема не найдена.");
    const nextLibrary = {
      themes: library.themes.filter((entry) => entry.id !== themeId),
      activeId: activeThemeId === themeId ? BUILTIN_THEME_ID : activeThemeId,
    };
    persistLibrary(nextLibrary);
    library = nextLibrary;
    activeThemeId = nextLibrary.activeId;
    activeTheme = library.themes.find((entry) => entry.id === activeThemeId) || null;
    applyCurrentPalette();
    return { id: themeId, name: theme.name };
  }

  function clearPaletteOverrides() {
    const root = document.documentElement;
    for (const key of COLOR_KEYS) root.style.removeProperty(`--${key}`);
  }

  function applyCurrentPalette() {
    const root = document.documentElement;
    clearPaletteOverrides();
    if (!activeTheme) return;

    const mode = root.dataset.theme === "dark" ? "dark" : "light";
    const palette = activeTheme.colors[mode];
    for (const [key, color] of Object.entries(palette)) {
      root.style.setProperty(`--${key}`, color);
    }
  }

  async function importFile(file) {
    if (!file) throw new Error("Выберите JSON-файл темы.");
    if (file.size > MAX_FILE_BYTES) {
      throw new Error("Файл темы слишком большой. Максимальный размер — 256 КБ.");
    }

    let candidate;
    try {
      candidate = JSON.parse(await file.text());
    } catch {
      throw new Error("Не удалось прочитать JSON. Проверьте синтаксис файла.");
    }
    const theme = validateTheme(candidate);

    const matchingIndex = library.themes.findIndex(
      (entry) => entry.name.toLocaleLowerCase("en") === theme.name.toLocaleLowerCase("en"),
    );
    const id = matchingIndex >= 0 ? library.themes[matchingIndex].id : createThemeId(theme.name, library.themes);
    const savedTheme = { id, ...theme };
    const nextThemes = [...library.themes];
    if (matchingIndex >= 0) nextThemes[matchingIndex] = savedTheme;
    else nextThemes.push(savedTheme);

    const nextLibrary = { themes: nextThemes, activeId: id };
    persistLibrary(nextLibrary);
    library = nextLibrary;
    activeThemeId = id;
    activeTheme = savedTheme;
    applyCurrentPalette();
    return { id, name: theme.name, updated: matchingIndex >= 0 };
  }

  function readBuiltInPalette(mode) {
    const root = document.documentElement;
    const originalMode = root.dataset.theme === "dark" ? "dark" : "light";
    clearPaletteOverrides();
    root.dataset.theme = mode;
    const computed = window.getComputedStyle(root);
    const palette = {};
    for (const key of COLOR_KEYS) {
      const value = computed.getPropertyValue(`--${key}`).trim();
      if (HEX_COLOR.test(value)) palette[key] = value.toLowerCase();
    }
    root.dataset.theme = originalMode;
    return palette;
  }

  function createExportTheme() {
    if (activeTheme) {
      return JSON.parse(JSON.stringify(activeTheme));
    }
    return {
      name: "Flowboard GitHub",
      version: 1,
      colors: {
        light: readBuiltInPalette("light"),
        dark: readBuiltInPalette("dark"),
      },
    };
  }

  function downloadTheme() {
    const theme = createExportTheme();
    const blob = new Blob([`${JSON.stringify(theme, null, 2)}\n`], {
      type: "application/json;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const slug = theme.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    link.href = url;
    link.download = `${slug || "flowboard-theme"}.json`;
    link.hidden = true;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
    return theme.name;
  }

  function resetTheme() {
    return selectTheme(BUILTIN_THEME_ID);
  }

  function hasCustomTheme() {
    return Boolean(activeTheme);
  }

  function getCustomThemeName() {
    return activeTheme?.name || "";
  }

  // Run before stylesheets are loaded to avoid showing the default palette on refresh.
  applyCurrentPalette();

  window.FlowboardThemeManager = {
    applyCurrentPalette,
    deleteTheme,
    downloadTheme,
    getActiveThemeId,
    getCustomThemeName,
    getThemeName,
    getThemes,
    hasCustomTheme,
    importFile,
    resetTheme,
    selectTheme,
  };
})();
