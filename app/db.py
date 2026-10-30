"""SQLite setup and FastAPI database dependency."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from pathlib import Path

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
    description TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'doing', 'waiting', 'done')),
    position REAL NOT NULL DEFAULT 0,
    tags TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    closed_at TEXT NULL,
    archived_at TEXT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status_position ON tasks(status, position, id);
CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON tasks(updated_at);
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    size INTEGER NOT NULL CHECK (size >= 0),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attachments_task_id ON attachments(task_id);

CREATE TABLE IF NOT EXISTS worksets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_slug TEXT NOT NULL,
    name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT NULL
);
CREATE INDEX IF NOT EXISTS idx_worksets_project_status
    ON worksets(project_slug, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS workset_memberships (
    workset_id INTEGER NOT NULL REFERENCES worksets(id) ON DELETE CASCADE,
    task_id INTEGER NOT NULL UNIQUE REFERENCES tasks(id) ON DELETE CASCADE,
    added_at TEXT NOT NULL,
    PRIMARY KEY (workset_id, task_id)
);
CREATE INDEX IF NOT EXISTS idx_workset_memberships_workset
    ON workset_memberships(workset_id, task_id);

CREATE TABLE IF NOT EXISTS workset_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workset_id INTEGER NULL,
    project_slug TEXT NOT NULL,
    workset_name TEXT NOT NULL,
    task_id INTEGER NULL,
    task_title TEXT NOT NULL DEFAULT '',
    task_status TEXT NULL,
    task_closed_at TEXT NULL,
    task_count INTEGER NULL,
    done_count INTEGER NULL,
    event_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_workset_events_project_created
    ON workset_events(project_slug, created_at DESC, id DESC);
"""


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Create a connection with row objects and foreign-key enforcement."""
    path = Path(db_path) if db_path is not None else settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialize_database(db_path: str | Path | None = None) -> None:
    """Create the schema when the application starts."""
    connection = connect(db_path)
    try:
        connection.executescript(SCHEMA)
        connection.execute("BEGIN IMMEDIATE")
        # Existing databases predate task archiving. Add the nullable column in-place
        # instead of rebuilding the table, preserving task IDs and attachment links.
        task_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
        }
        if "archived_at" not in task_columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN archived_at TEXT NULL")
        if "result" not in task_columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN result TEXT NOT NULL DEFAULT ''")

        # Event identifiers are historical snapshots, not live relationships. Keep
        # them when a task or workset is physically deleted.
        event_foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(workset_events)"
        ).fetchall()
        if event_foreign_keys:
            connection.execute("DROP INDEX IF EXISTS idx_workset_events_project_created")
            connection.execute("ALTER TABLE workset_events RENAME TO workset_events_legacy")
            connection.execute(
                """
                CREATE TABLE workset_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workset_id INTEGER NULL,
                    project_slug TEXT NOT NULL,
                    workset_name TEXT NOT NULL,
                    task_id INTEGER NULL,
                    task_title TEXT NOT NULL DEFAULT '',
                    task_status TEXT NULL,
                    task_closed_at TEXT NULL,
                    task_count INTEGER NULL,
                    done_count INTEGER NULL,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO workset_events (
                    id, workset_id, project_slug, workset_name, task_id, task_title,
                    event_type, created_at
                )
                SELECT id, workset_id, project_slug, workset_name, task_id, task_title,
                       event_type, created_at
                FROM workset_events_legacy
                """
            )
            connection.execute("DROP TABLE workset_events_legacy")

        event_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(workset_events)").fetchall()
        }
        for column, declaration in (
            ("task_status", "TEXT NULL"),
            ("task_closed_at", "TEXT NULL"),
            ("task_count", "INTEGER NULL"),
            ("done_count", "INTEGER NULL"),
        ):
            if column not in event_columns:
                connection.execute(
                    f"ALTER TABLE workset_events ADD COLUMN {column} {declaration}"
                )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_workset_events_project_created "
            "ON workset_events(project_slug, created_at DESC, id DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_workset_events_workset "
            "ON workset_events(workset_id, id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_archived_at ON tasks(archived_at)"
        )
        connection.executemany(
            "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
            [
                ("archive_enabled", "true"),
                ("archive_after_days", "30"),
                ("require_result_to_close", "false"),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Yield a request-scoped database connection."""
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()
