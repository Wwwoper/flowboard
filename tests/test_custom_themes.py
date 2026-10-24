from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
THEME_MANAGER = ROOT / "app" / "static" / "theme-manager.js"
GITHUB_THEME = ROOT / "app" / "static" / "github-theme.css"
THEME_EXAMPLE = ROOT / "docs" / "themes" / "purple-night.json"

COLOR_KEYS = {
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
}


def test_custom_theme_controls_and_script_are_served(client):
    html = client.get("/").text
    for element_id in (
        "theme-import-file",
        "import-theme-button",
        "export-theme-button",
        "reset-theme-button",
        "custom-theme-status",
    ):
        assert f'id="{element_id}"' in html
    assert '/static/theme-manager.js?v=0.1.0' in html
    assert '/static/app.js?v=0.5.10' in html
    assert '/static/github-theme.css?v=0.2.0' in html

    response = client.get("/static/theme-manager.js")
    assert response.status_code == 200
    assert "function validateTheme(value)" in response.text
    assert 'const MAX_FILE_BYTES = 256 * 1024;' in response.text


def test_custom_theme_manager_only_accepts_known_hex_color_tokens():
    script = THEME_MANAGER.read_text()
    for key in COLOR_KEYS:
        assert f'"{key}"' in script
    assert 'const HEX_COLOR = /^#(?:[\\da-f]{3}|[\\da-f]{6})$/i;' in script
    assert "Unknown" not in script
    assert "eval(" not in script
    assert "new Function(" not in script
    assert "localStorage.setItem(STORAGE_KEY, JSON.stringify(theme))" in script
    assert "localStorage.removeItem(STORAGE_KEY)" in script
    assert "applyCurrentPalette" in script
    assert "downloadTheme" in script


def test_all_customizable_tokens_have_light_and_dark_defaults():
    css = GITHUB_THEME.read_text()
    blocks = re.findall(r":root[^\{]*\{([^}]*)\}", css)
    assert len(blocks) >= 2
    for block in blocks[:2]:
        defined = set(re.findall(r"--([a-z-]+)\s*:", block))
        assert COLOR_KEYS <= defined


def test_example_custom_theme_uses_supported_schema():
    theme = json.loads(THEME_EXAMPLE.read_text())
    assert theme["version"] == 1
    assert theme["name"] == "Purple Night"
    assert set(theme["colors"]) == {"light", "dark"}
    assert theme["colors"]["light"]
    assert theme["colors"]["dark"]
    for palette in theme["colors"].values():
        assert set(palette) <= COLOR_KEYS
        assert all(
            re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", color)
            for color in palette.values()
        )


def test_theme_actions_are_connected_to_ui_and_theme_mode_toggle():
    script = (ROOT / "app" / "static" / "app.js").read_text()
    assert 'els.importThemeButton.addEventListener("click"' in script
    assert 'els.exportThemeButton.addEventListener("click"' in script
    assert 'els.resetThemeButton.addEventListener("click"' in script
    assert 'window.FlowboardThemeManager?.applyCurrentPalette()' in script
    assert 'updateThemeManagerControls();' in script
    assert 'finally {\n      els.themeImportFile.value = "";' in script


def test_theme_manager_import_persistence_and_reset_in_node():
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is unavailable")

    runtime_test = r'''
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const managerPath = process.argv[1];
const store = new Map();
const storage = {
  getItem(key) { return store.has(key) ? store.get(key) : null; },
  setItem(key, value) { store.set(key, String(value)); },
  removeItem(key) { store.delete(key); },
};
function boot(mode = "light") {
  const variables = new Map();
  const root = {
    dataset: { theme: mode },
    style: {
      setProperty(key, value) { variables.set(key, value); },
      removeProperty(key) { variables.delete(key); },
    },
  };
  const window = { setTimeout(callback) { callback(); } };
  const document = { documentElement: root };
  const context = { window, document, localStorage: storage, console };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(managerPath, "utf8"), context, { filename: managerPath });
  return { manager: window.FlowboardThemeManager, root, variables };
}
(async () => {
  const first = boot("light");
  const theme = {
    name: "Runtime Test",
    version: 1,
    colors: {
      light: { accent: "#123abc", "gh-primary": "#456789" },
      dark: { accent: "#abcdef", "gh-primary": "#fedcba" },
    },
  };
  await first.manager.importFile({ size: 100, text: async () => JSON.stringify(theme) });
  assert.equal(first.variables.get("--accent"), "#123abc");
  assert.equal(first.manager.hasCustomTheme(), true);
  assert.equal(first.manager.getCustomThemeName(), "Runtime Test");

  const reloaded = boot("dark");
  assert.equal(reloaded.variables.get("--accent"), "#abcdef");
  assert.equal(reloaded.variables.get("--gh-primary"), "#fedcba");

  const invalidTheme = {
    ...theme,
    colors: { light: { accent: "red" }, dark: { accent: "#fff" } },
  };
  await assert.rejects(
    first.manager.importFile({ size: 100, text: async () => JSON.stringify(invalidTheme) }),
    /формате #RGB или #RRGGBB/,
  );
  await assert.rejects(
    first.manager.importFile({ size: 300000, text: async () => "{}" }),
    /256 КБ/,
  );
  first.manager.resetTheme();
  assert.equal(first.manager.hasCustomTheme(), false);
  assert.equal(store.has("flowboard-custom-theme"), false);
  assert.equal(first.variables.has("--accent"), false);
})().catch((error) => { console.error(error); process.exitCode = 1; });
'''
    result = subprocess.run(
        [node, "-e", runtime_test, str(THEME_MANAGER)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
