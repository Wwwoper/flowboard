"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    """Small settings object kept mutable to simplify isolated tests."""

    DATA_DIR = Path(os.getenv("TRACKER_DATA_DIR", str(BASE_DIR / "data"))).expanduser()
    MAX_FILE_SIZE_MB = max(1, int(os.getenv("TRACKER_MAX_FILE_SIZE_MB", "20")))
    WIP_LIMIT = max(1, int(os.getenv("TRACKER_WIP_LIMIT", "3")))

    @property
    def db_path(self) -> Path:
        return Path(self.DATA_DIR) / "tracker.db"

    @property
    def attachments_dir(self) -> Path:
        return Path(self.DATA_DIR) / "attachments"

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


settings = Settings()
STATUSES = ("todo", "doing", "waiting", "done")
STATUS_LABELS = {
    "todo": "К выполнению",
    "doing": "В работе",
    "waiting": "Ожидает",
    "done": "Готово",
}
