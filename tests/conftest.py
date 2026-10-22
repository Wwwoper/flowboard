from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    data_dir = tmp_path / "tracker-data"
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_MB", 1)
    monkeypatch.setattr(settings, "WIP_LIMIT", 3)
    with TestClient(app) as test_client:
        yield test_client
