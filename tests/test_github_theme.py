from __future__ import annotations


def test_github_theme_stylesheet_is_loaded(client):
    response = client.get("/")

    assert response.status_code == 200
    assert 'href="/static/github-theme.css?v=0.2.2"' in response.text


def test_github_theme_stylesheet_defines_light_and_dark_palettes(client):
    response = client.get("/static/github-theme.css")

    assert response.status_code == 200
    css = response.text
    assert ':root:not([data-theme="dark"])' in css
    assert ':root[data-theme="dark"]' in css
    assert "--page: #ffffff" in css
    assert "--page: #0d1117" in css
    assert "--line: #d0d7de" in css
    assert "--line: #30363d" in css
    assert ".board-column" in css
    assert ".task-card" in css
    assert ".task-panel" in css
    assert '[data-theme="dark"] .board-column' in css
    assert '[data-theme="dark"] .text-field' in css
    assert '[data-theme="dark"] .task-more-menu' in css
