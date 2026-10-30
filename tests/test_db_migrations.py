from __future__ import annotations

import sqlite3

from app.db import initialize_database


def test_initialize_database_adds_result_to_existing_tasks(tmp_path):
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'todo',
                position REAL NOT NULL DEFAULT 0,
                tags TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                closed_at TEXT NULL
            );
            INSERT INTO tasks (title, description, status, position, tags, created_at, updated_at)
            VALUES (
                'Legacy task', 'Existing description', 'done', 0, 'legacy',
                '2026-01-01', '2026-01-02'
            );
            """
        )
        connection.commit()
    finally:
        connection.close()

    initialize_database(db_path)

    connection = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)")}
        workset_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        task = connection.execute(
            "SELECT title, description, result, status, tags FROM tasks WHERE id = 1"
        ).fetchone()
    finally:
        connection.close()

    assert "result" in columns
    assert {"worksets", "workset_memberships", "workset_events"} <= workset_tables
    assert task == ("Legacy task", "Existing description", "", "done", "legacy")
