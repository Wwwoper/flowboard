from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_api_client_is_loaded_before_the_application():
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    api_client_index = html.index('/static/api-client.js?v=0.1.0')
    app_index = html.index('/static/app.js?v=__FLOWBOARD_VERSION__')
    assert api_client_index < app_index

    app_script = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert "window.FlowboardApi.createClient()" in app_script
    assert "apiClient.requestBlob(" in app_script
    assert "fetch(" not in app_script
    assert "void queueTaskMove(move).catch(" in app_script
    assert "void loadTasks().catch(" in app_script
    assert "void focusResultField(Number(match[1])).catch(" in app_script
