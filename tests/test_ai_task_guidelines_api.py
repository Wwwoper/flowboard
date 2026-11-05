from __future__ import annotations

import json
import sqlite3

from fastapi.testclient import TestClient

from app import main
from app.ai_guidelines import AI_TASK_GUIDELINES_BASE_VERSION, read_ai_task_guidelines
from app.config import settings
from app.main import AI_TASK_GUIDELINES_OVERRIDE_KEY, app


def test_read_returns_immutable_base_without_creating_override(client):
    response = client.get("/api/ai-task-guidelines")

    assert response.status_code == 200
    assert f"**Версия:** {AI_TASK_GUIDELINES_BASE_VERSION}" in read_ai_task_guidelines()
    assert response.json() == {
        "text": read_ai_task_guidelines(),
        "source": "base",
        "base_version": AI_TASK_GUIDELINES_BASE_VERSION,
        "updated_at": None,
    }
    with sqlite3.connect(settings.db_path) as connection:
        assert connection.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (AI_TASK_GUIDELINES_OVERRIDE_KEY,),
        ).fetchone() is None


def test_save_and_read_preserve_exact_markdown_and_unicode(client):
    content = "# Пользовательская редакция\r\n\r\nТекст **без потерь** — 日本語 🧭\n"

    response = client.put("/api/ai-task-guidelines", json={"text": content})

    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == content
    assert payload["source"] == "user"
    assert payload["base_version"] == AI_TASK_GUIDELINES_BASE_VERSION
    assert payload["updated_at"]

    reread = client.get("/api/ai-task-guidelines")
    assert reread.status_code == 200
    assert reread.json() == payload

    with sqlite3.connect(settings.db_path) as connection:
        rows = connection.execute(
            "SELECT key, value FROM app_settings WHERE key = ?",
            (AI_TASK_GUIDELINES_OVERRIDE_KEY,),
        ).fetchall()
    assert len(rows) == 1
    assert content == json.loads(rows[0][1])["text"]


def test_save_updates_only_override_key_and_survives_app_restart(client):
    client.patch("/api/task-settings", json={"require_result_to_close": True})
    client.patch("/api/archive/settings", json={"archive_after_days": 60})
    content = "## Сохранённая редакция\n"
    assert client.put("/api/ai-task-guidelines", json={"text": content}).status_code == 200

    with TestClient(app) as restarted_client:
        response = restarted_client.get("/api/ai-task-guidelines")

    assert response.status_code == 200
    assert response.json()["text"] == content
    assert response.json()["source"] == "user"
    with sqlite3.connect(settings.db_path) as connection:
        values = dict(connection.execute("SELECT key, value FROM app_settings"))
    assert values["require_result_to_close"] == "true"
    assert values["archive_after_days"] == "60"
    assert AI_TASK_GUIDELINES_OVERRIDE_KEY in values


def test_reset_deletes_only_override_and_returns_base(client):
    client.patch("/api/task-settings", json={"require_result_to_close": True})
    client.put("/api/ai-task-guidelines", json={"text": "Переопределение\n"})

    response = client.delete("/api/ai-task-guidelines")

    assert response.status_code == 200
    assert response.json() == {
        "text": read_ai_task_guidelines(),
        "source": "base",
        "base_version": AI_TASK_GUIDELINES_BASE_VERSION,
        "updated_at": None,
    }
    with sqlite3.connect(settings.db_path) as connection:
        values = dict(connection.execute("SELECT key, value FROM app_settings"))
    assert AI_TASK_GUIDELINES_OVERRIDE_KEY not in values
    assert values["require_result_to_close"] == "true"


def test_save_rejects_blank_wrong_type_and_oversized_text(client):
    assert client.put("/api/ai-task-guidelines", json={"text": " \n\t "}).status_code == 422
    assert client.put("/api/ai-task-guidelines", json={"text": 123}).status_code == 422
    assert client.put("/api/ai-task-guidelines", json={"text": True}).status_code == 422
    assert client.put("/api/ai-task-guidelines", json={"text": None}).status_code == 422
    assert client.put("/api/ai-task-guidelines", json={"text": "x" * 30001}).status_code == 422


def test_base_resource_failure_returns_safe_http_error(client, monkeypatch):
    def fail_read():
        raise OSError("/private/container/path/ai-task-guidelines.md missing")

    monkeypatch.setattr(main, "read_ai_task_guidelines", fail_read)
    response = client.get("/api/ai-task-guidelines")

    assert response.status_code == 503
    assert response.json() == {"detail": "Встроенный регламент временно недоступен"}
    assert "/private/" not in response.text


def test_database_connection_failure_returns_safe_http_error(client, monkeypatch):
    def fail_connect():
        raise sqlite3.OperationalError("/private/database/path is locked")

    monkeypatch.setattr(main, "connect", fail_connect)
    response = client.get("/api/ai-task-guidelines")

    assert response.status_code == 503
    assert response.json() == {"detail": "Хранилище регламента временно недоступно"}
    assert "/private/" not in response.text


def test_database_write_failure_rolls_back_and_returns_safe_http_error(client, monkeypatch):
    real_connect = main.connect

    class FailingConnection:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, sql, parameters=()):
            if sql.startswith("INSERT INTO app_settings"):
                raise sqlite3.OperationalError("sensitive database detail")
            return self.connection.execute(sql, parameters)

        def __getattr__(self, name):
            return getattr(self.connection, name)

    monkeypatch.setattr(main, "connect", lambda: FailingConnection(real_connect()))
    response = client.put("/api/ai-task-guidelines", json={"text": "Не должно сохраниться"})

    assert response.status_code == 503
    assert "sensitive database detail" not in response.text
    with sqlite3.connect(settings.db_path) as connection:
        assert connection.execute(
            "SELECT 1 FROM app_settings WHERE key = ?",
            (AI_TASK_GUIDELINES_OVERRIDE_KEY,),
        ).fetchone() is None


def test_database_read_failure_returns_safe_http_error(client, monkeypatch):
    real_connect = main.connect

    class FailingConnection:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, sql, parameters=()):
            if sql.startswith("SELECT value FROM app_settings"):
                raise sqlite3.OperationalError("sensitive read failure")
            return self.connection.execute(sql, parameters)

        def __getattr__(self, name):
            return getattr(self.connection, name)

    monkeypatch.setattr(main, "connect", lambda: FailingConnection(real_connect()))
    response = client.get("/api/ai-task-guidelines")

    assert response.status_code == 503
    assert response.json() == {"detail": "Не удалось прочитать настройки регламента"}
    assert "sensitive read failure" not in response.text


def test_reset_does_not_delete_override_when_base_resource_is_unavailable(client, monkeypatch):
    client.put("/api/ai-task-guidelines", json={"text": "Сохранённый текст"})

    def fail_read():
        raise OSError("resource unavailable")

    monkeypatch.setattr(main, "read_ai_task_guidelines", fail_read)
    response = client.delete("/api/ai-task-guidelines")

    assert response.status_code == 503
    with sqlite3.connect(settings.db_path) as connection:
        row = connection.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (AI_TASK_GUIDELINES_OVERRIDE_KEY,),
        ).fetchone()
    assert json.loads(row[0])["text"] == "Сохранённый текст"
