(() => {
  "use strict";

  const STORAGE_KEY = "flowboard-custom-theme";
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
  let activeTheme = readSavedTheme();

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

  function readSavedTheme() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? validateTheme(JSON.parse(raw)) : null;
    } catch {
      return null;
    }
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

    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(theme));
    } catch {
      throw new Error("Не удалось сохранить тему в браузере. Проверьте доступность локального хранилища.");
    }

    activeTheme = theme;
    applyCurrentPalette();
    return { name: theme.name };
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
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      throw new Error("Не удалось удалить сохранённую тему из браузера.");
    }
    activeTheme = null;
    applyCurrentPalette();
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
    downloadTheme,
    getCustomThemeName,
    hasCustomTheme,
    importFile,
    resetTheme,
  };
})();
