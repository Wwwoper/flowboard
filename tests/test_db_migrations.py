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


def test_initialize_database_preserves_workset_event_ids_without_foreign_keys(tmp_path):
    db_path = tmp_path / "legacy-worksets.db"
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
            CREATE TABLE worksets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_slug TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT NULL
            );
            CREATE TABLE workset_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workset_id INTEGER NULL REFERENCES worksets(id) ON DELETE SET NULL,
                project_slug TEXT NOT NULL,
                workset_name TEXT NOT NULL,
                task_id INTEGER NULL REFERENCES tasks(id) ON DELETE SET NULL,
                task_title TEXT NOT NULL DEFAULT '',
                event_type TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            INSERT INTO tasks (id, title, created_at, updated_at)
            VALUES (17, 'Historical task', '2026-01-01', '2026-01-01');
            INSERT INTO worksets (
                id, project_slug, name, status, created_at, updated_at
            ) VALUES (9, 'history', 'Historical set', 'active', '2026-01-01', '2026-01-01');
            INSERT INTO workset_events (
                id, workset_id, project_slug, workset_name, task_id, task_title,
                event_type, created_at
            ) VALUES (
                23, 9, 'history', 'Historical set', 17, 'Historical task',
                'task_added', '2026-01-01T00:00:00Z'
            );
            """
        )
        connection.commit()
    finally:
        connection.close()

    initialize_database(db_path)

    connection = sqlite3.connect(db_path)
    try:
        event = connection.execute(
            "SELECT id, workset_id, task_id, task_title FROM workset_events"
        ).fetchone()
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(workset_events)")
        }
        foreign_keys = connection.execute("PRAGMA foreign_key_list(workset_events)").fetchall()
    finally:
        connection.close()

    assert event == (23, 9, 17, "Historical task")
    assert {"task_status", "task_closed_at", "task_count", "done_count"} <= columns
    assert foreign_keys == []


def test_legacy_task_types_are_migrated_with_backup_and_idempotently(tmp_path):
    db_path = tmp_path / "legacy-types.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                result TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'todo',
                position REAL NOT NULL DEFAULT 0,
                tags TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                closed_at TEXT NULL,
                archived_at TEXT NULL
            );
            INSERT INTO tasks (title, tags, created_at, updated_at) VALUES
                ('Bug task', 'backend, bug, needs-review', '2026-01-01', '2026-01-01'),
                ('Docs task', 'docs, writing', '2026-01-01', '2026-01-01'),
                ('Plain task', 'backend', '2026-01-01', '2026-01-01');
            """
        )
        connection.commit()
    finally:
        connection.close()

    initialize_database(db_path)
    backup_path = db_path.with_name(db_path.name + ".pre-task-type-migration.bak")
    assert backup_path.is_file()
    backup_connection = sqlite3.connect(backup_path)
    try:
        backup_columns = {
            row[1] for row in backup_connection.execute("PRAGMA table_info(tasks)")
        }
        original_tags = backup_connection.execute(
            "SELECT tags FROM tasks WHERE id = 1"
        ).fetchone()[0]
    finally:
        backup_connection.close()
    assert "task_type" not in backup_columns
    assert original_tags == "backend, bug, needs-review"

    connection = sqlite3.connect(db_path)
    try:
        migrated = connection.execute(
            "SELECT title, tags, task_type FROM tasks ORDER BY id"
        ).fetchall()
        report = connection.execute(
            "SELECT value FROM app_settings WHERE key = 'task_type_migration_report'"
        ).fetchone()[0]
    finally:
        connection.close()

    assert migrated == [
        ("Bug task", "backend, needs-review", "bug"),
        ("Docs task", "writing", "docs"),
        ("Plain task", "backend", ""),
    ]
    assert '"migrated": 2' in report
    assert '"removed": 2' in report
    assert '"backup_created": true' in report
    assert '"backup_file": "legacy-types.db.pre-task-type-migration.bak"' in report

    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        migrated_again = connection.execute(
            "SELECT title, tags, task_type FROM tasks ORDER BY id"
        ).fetchall()
    finally:
        connection.close()
    assert migrated_again == migrated
    assert backup_path.is_file()


def test_task_type_migration_preserves_existing_type_and_reports_conflicts(tmp_path):
    db_path = tmp_path / "partially-migrated.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                result TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'todo',
                position REAL NOT NULL DEFAULT 0,
                tags TEXT NOT NULL DEFAULT '',
                task_type TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                closed_at TEXT NULL,
                archived_at TEXT NULL
            );
            INSERT INTO tasks (title, tags, task_type, created_at, updated_at)
            VALUES ('Conflict', 'backend, docs', 'bug', '2026-01-01', '2026-01-01');
            INSERT INTO tasks (title, tags, task_type, created_at, updated_at)
            VALUES (
                'Multiple legacy types', 'feature, refactor, tests', '',
                '2026-01-01', '2026-01-01'
            );
            """
        )
        connection.commit()
    finally:
        connection.close()

    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT title, tags, task_type FROM tasks ORDER BY id"
        ).fetchall()
        report = connection.execute(
            "SELECT value FROM app_settings WHERE key = 'task_type_migration_report'"
        ).fetchone()[0]
    finally:
        connection.close()

    assert rows == [
        ("Conflict", "backend", "bug"),
        ("Multiple legacy types", "tests", "feature"),
    ]
    assert '"task_id": 1' in report
    assert '"existing_type": "bug"' in report
    assert '"task_id": 2' in report
    assert '"legacy_types": ["feature", "refactor"]' in report
