from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.ai_guidelines import AI_TASK_GUIDELINES_OVERRIDE_KEY, read_ai_task_guidelines
from app.config import settings
from app.main import app


@pytest.mark.parametrize(
    "stored_value",
    [
        "not-json",
        json.dumps({"text": 123, "updated_at": "2026-11-05T12:00:00Z"}),
        json.dumps({"text": "  \n", "updated_at": "2026-11-05T12:00:00Z"}),
        json.dumps({"text": "x" * 30_001, "updated_at": "2026-11-05T12:00:00Z"}),
        json.dumps({"text": "valid text", "updated_at": "  "}),
    ],
)
def test_api_rejects_corrupt_or_invalid_saved_override(client, stored_value):
    with sqlite3.connect(settings.db_path) as connection:
        connection.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
            (AI_TASK_GUIDELINES_OVERRIDE_KEY, stored_value),
        )

    response = client.get("/api/ai-task-guidelines")

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Не удалось прочитать пользовательскую редакцию регламента"
    }


def test_clean_app_start_and_fresh_client_read_bundled_document(client):
    response = client.get("/api/ai-task-guidelines")
    assert response.status_code == 200
    assert response.json()["source"] == "base"
    assert response.json()["text"] == read_ai_task_guidelines()

    with TestClient(app) as fresh_client:
        fresh_response = fresh_client.get("/api/ai-task-guidelines")

    assert fresh_response.status_code == 200
    assert fresh_response.json()["source"] == "base"
    assert fresh_response.json()["text"] == read_ai_task_guidelines()


def test_saved_guidelines_are_available_after_a_new_client_session(client):
    content = "# Сохранено на сервере\n\nТекст переживает новую сессию.\n"
    saved = client.put("/api/ai-task-guidelines", json={"text": content})
    assert saved.status_code == 200

    with TestClient(app) as fresh_client:
        response = fresh_client.get("/api/ai-task-guidelines")

    assert response.status_code == 200
    assert response.json()["source"] == "user"
    assert response.json()["text"] == content
