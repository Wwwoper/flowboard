"""FastAPI routes for the single-user Kanban Tracker."""

from __future__ import annotations

import asyncio
import math
import re
import shutil
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePath, PureWindowsPath
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import connect, get_db, initialize_database
from app.exporter import build_markdown_export, build_zip_export, export_filename
from app.importer import ParsedTask, parse_markdown_file, utc_now
from app.markdown import render_safe_markdown
from app.models import (
    ArchiveSettingsPatch,
    ArchiveSettingsRead,
    AttachmentRead,
    ImportResult,
    ImportSkipped,
    MarkdownPreviewRequest,
    TaskCreate,
    TaskDetail,
    TaskPatch,
    TaskSettingsPatch,
    TaskSettingsRead,
    TaskSummary,
    WorksetCreate,
    WorksetEventRead,
    WorksetPatch,
    WorksetRead,
    WorksetTaskAdd,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
ATTACHMENT_EXTENSION_RE = re.compile(r"\.[A-Za-z0-9]{1,10}$")
PROJECT_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


ARCHIVE_SETTING_DEFAULTS = {"archive_enabled": "true", "archive_after_days": "30"}
TASK_SETTING_DEFAULTS = {"require_result_to_close": "false"}
ARCHIVE_INTERVAL_SECONDS = 60 * 60


def _archive_settings(connection: sqlite3.Connection) -> dict[str, Any]:
    rows = {
        row["key"]: row["value"]
        for row in connection.execute(
            "SELECT key, value FROM app_settings WHERE key IN (?, ?)",
            ("archive_enabled", "archive_after_days"),
        ).fetchall()
    }
    enabled = rows.get("archive_enabled", ARCHIVE_SETTING_DEFAULTS["archive_enabled"]) == "true"
    try:
        after_days = int(rows.get("archive_after_days", ARCHIVE_SETTING_DEFAULTS["archive_after_days"]))
    except ValueError:
        after_days = 30
    if after_days not in {7, 30, 60, 90}:
        after_days = 30
    return {"archive_enabled": enabled, "archive_after_days": after_days}


def _task_settings(connection: sqlite3.Connection) -> dict[str, bool]:
    row = connection.execute(
        "SELECT value FROM app_settings WHERE key = ?", ("require_result_to_close",)
    ).fetchone()
    value = row["value"] if row else TASK_SETTING_DEFAULTS["require_result_to_close"]
    return {"require_result_to_close": value == "true"}


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _archive_due_completed_tasks(
    connection: sqlite3.Connection, *, now: datetime | None = None
) -> int:
    """Move completed tasks to the archive after the configured inactivity period."""
    preferences = _archive_settings(connection)
    if not preferences["archive_enabled"]:
        return 0
    current_time = now or datetime.now(UTC)
    cutoff = current_time - timedelta(days=preferences["archive_after_days"])
    candidates = connection.execute(
        """
        SELECT id, closed_at, updated_at FROM tasks
        WHERE status = 'done' AND archived_at IS NULL AND closed_at IS NOT NULL
        """
    ).fetchall()
    due_ids = []
    for task in candidates:
        closed_at = _parse_timestamp(task["closed_at"])
        updated_at = _parse_timestamp(task["updated_at"])
        activity = max((value for value in (closed_at, updated_at) if value is not None), default=None)
        if activity is not None and activity <= cutoff:
            due_ids.append(int(task["id"]))
    if not due_ids:
        return 0
    archived_at = current_time.isoformat(timespec="seconds").replace("+00:00", "Z")
    connection.executemany(
        "UPDATE tasks SET archived_at = ? WHERE id = ? AND archived_at IS NULL AND status = 'done'",
        [(archived_at, task_id) for task_id in due_ids],
    )
    connection.commit()
    return len(due_ids)


async def _archive_scheduler() -> None:
    """Periodically archive eligible tasks even if the board remains open."""
    while True:
        await asyncio.sleep(ARCHIVE_INTERVAL_SECONDS)
        connection = connect()
        try:
            _archive_due_completed_tasks(connection)
        finally:
            connection.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    settings.attachments_dir.mkdir(parents=True, exist_ok=True)
    connection = connect()
    try:
        _archive_due_completed_tasks(connection)
    finally:
        connection.close()
    scheduler = asyncio.create_task(_archive_scheduler())
    try:
        yield
    finally:
        scheduler.cancel()
        try:
            await scheduler
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Kanban Tracker",
    description="Лёгкий личный канбан-трекер с импортом Markdown и резервным экспортом.",
    version="0.1.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def disable_api_response_cache(request, call_next):
    """Keep task lists and details fresh after mutations in the single-user UI."""
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def _task_rows(
    connection: sqlite3.Connection, *, archived: bool | None = None
) -> list[dict[str, Any]]:
    where_clause = "WHERE t.archived_at IS NOT NULL" if archived is True else (
        "WHERE t.archived_at IS NULL" if archived is False else ""
    )
    order_clause = (
        "ORDER BY t.archived_at DESC, t.id DESC"
        if archived is True
        else """ORDER BY CASE t.status
            WHEN 'todo' THEN 0 WHEN 'doing' THEN 1 WHEN 'waiting' THEN 2 ELSE 3 END,
            t.position, t.id"""
    )
    rows = connection.execute(
        f"""
        SELECT t.*, COUNT(a.id) AS attachments_count, wm.workset_id
        FROM tasks AS t
        LEFT JOIN attachments AS a ON a.task_id = t.id
        LEFT JOIN workset_memberships AS wm ON wm.task_id = t.id
        {where_clause}
        GROUP BY t.id
        {order_clause}
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _task_row(connection: sqlite3.Connection, task_id: int) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT t.*, COUNT(a.id) AS attachments_count, wm.workset_id
        FROM tasks AS t
        LEFT JOIN attachments AS a ON a.task_id = t.id
        LEFT JOIN workset_memberships AS wm ON wm.task_id = t.id
        WHERE t.id = ?
        GROUP BY t.id
        """,
        (task_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def _require_task(connection: sqlite3.Connection, task_id: int) -> dict[str, Any]:
    task = _task_row(connection, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task


def _project_slug(tags: str) -> str:
    for tag in str(tags or "").split(","):
        match = re.fullmatch(
            r"project:([a-z0-9]+(?:-[a-z0-9]+)*)", tag.strip(), re.IGNORECASE
        )
        if match:
            return match.group(1).lower()
    return ""


def _require_workset(connection: sqlite3.Connection, workset_id: int) -> dict[str, Any]:
    row = connection.execute("SELECT * FROM worksets WHERE id = ?", (workset_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Рабочий набор не найден")
    return dict(row)


def _record_workset_event(
    connection: sqlite3.Connection,
    workset: dict[str, Any],
    event_type: str,
    *,
    task: dict[str, Any] | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO workset_events (
            workset_id, project_slug, workset_name, task_id, task_title, event_type, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            workset["id"],
            workset["project_slug"],
            workset["name"],
            task["id"] if task else None,
            task["title"] if task else "",
            event_type,
            utc_now(),
        ),
    )


def _workset_summary(connection: sqlite3.Connection, workset_id: int) -> WorksetRead:
    workset = _require_workset(connection, workset_id)
    counts = connection.execute(
        """
        SELECT COUNT(*) AS task_count,
               SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) AS done_count
        FROM workset_memberships AS wm
        JOIN tasks AS t ON t.id = wm.task_id
        WHERE wm.workset_id = ?
        """,
        (workset_id,),
    ).fetchone()
    return WorksetRead(
        **workset,
        task_count=int(counts["task_count"] or 0),
        done_count=int(counts["done_count"] or 0),
    )


def _sync_workset_state(connection: sqlite3.Connection, workset_id: int) -> None:
    workset = connection.execute("SELECT * FROM worksets WHERE id = ?", (workset_id,)).fetchone()
    if workset is None:
        return
    counts = connection.execute(
        """
        SELECT COUNT(*) AS task_count,
               SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) AS done_count
        FROM workset_memberships AS wm
        JOIN tasks AS t ON t.id = wm.task_id
        WHERE wm.workset_id = ?
        """,
        (workset_id,),
    ).fetchone()
    task_count = int(counts["task_count"] or 0)
    # Empty sets created intentionally stay active. Explicitly removing their final
    # member deletes them; deleting a task from the project is handled separately.
    if task_count == 0:
        return
    completed = int(counts["done_count"] or 0) == task_count
    new_status = "completed" if completed else "active"
    updated_at = utc_now()
    if new_status == workset["status"]:
        connection.execute(
            "UPDATE worksets SET updated_at = ? WHERE id = ?", (updated_at, workset_id)
        )
        return
    completed_at = utc_now() if completed else None
    connection.execute(
        "UPDATE worksets SET status = ?, completed_at = ?, updated_at = ? WHERE id = ?",
        (new_status, completed_at, updated_at, workset_id),
    )
    _record_workset_event(
        connection,
        dict(workset),
        "completed" if completed else "reactivated",
    )


def _add_task_to_workset(
    connection: sqlite3.Connection, workset_id: int, task: dict[str, Any]
) -> None:
    workset = _require_workset(connection, workset_id)
    if workset["status"] != "active":
        raise HTTPException(
            status_code=409, detail="В завершённый набор нельзя добавлять задачи"
        )
    if not workset["project_slug"] or _project_slug(task["tags"]) != workset["project_slug"]:
        raise HTTPException(
            status_code=409, detail="Задача должна принадлежать проекту рабочего набора"
        )
    existing = connection.execute(
        "SELECT workset_id FROM workset_memberships WHERE task_id = ?", (task["id"],)
    ).fetchone()
    if existing:
        if int(existing["workset_id"]) == workset_id:
            return
        raise HTTPException(
            status_code=409,
            detail="Задача уже входит в другой рабочий набор",
        )
    try:
        connection.execute(
            "INSERT INTO workset_memberships (workset_id, task_id, added_at) VALUES (?, ?, ?)",
            (workset_id, task["id"], utc_now()),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="Не удалось добавить задачу в набор"
        ) from exc
    _record_workset_event(connection, workset, "task_added", task=task)
    _sync_workset_state(connection, workset_id)


def _attachments_for_task(connection: sqlite3.Connection, task_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT id, task_id, filename, stored_name, size, created_at
        FROM attachments WHERE task_id = ? ORDER BY id
        """,
        (task_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _create_task(connection: sqlite3.Connection, task: ParsedTask) -> int:
    now = utc_now()
    created = task.created_at or now
    updated = task.updated_at or created
    closed = task.closed_at if task.status == "done" else None
    if task.status == "done" and not closed:
        closed = now
    position_row = connection.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 FROM tasks WHERE status = ?", (task.status,)
    ).fetchone()
    position = float(position_row[0])
    cursor = connection.execute(
        """
        INSERT INTO tasks (title, description, result, status, position, tags, created_at,
                           updated_at, closed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task.title,
            task.description,
            task.result,
            task.status,
            position,
            task.tags,
            created,
            updated,
            closed,
        ),
    )
    return int(cursor.lastrowid)


def _task_summary(task: dict[str, Any]) -> TaskSummary:
    return TaskSummary(**{key: task[key] for key in TaskSummary.model_fields if key in task})


def _get_attachment_path(task_id: int, stored_name: str) -> Path:
    root = settings.attachments_dir.resolve()
    path = (settings.attachments_dir / str(task_id) / stored_name).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(status_code=404, detail="Вложение не найдено")
    return path


def _remove_empty_attachment_dir(task_id: int) -> None:
    directory = settings.attachments_dir / str(task_id)
    try:
        directory.rmdir()
    except OSError:
        # The directory is non-empty or the filesystem refused the cleanup.
        pass


def _clean_filename(raw_filename: str | None) -> str:
    raw = (raw_filename or "file").replace("\x00", "")
    # Browsers normally send a basename; also strip paths supplied by non-browser clients.
    filename = PurePath(raw).name
    filename = PureWindowsPath(filename).name
    filename = re.sub(r"[\x00-\x1f\x7f]", "", filename).strip()
    return filename[:255] or "file"


def _stored_extension(filename: str) -> str:
    suffix = Path(filename).suffix
    return suffix.lower() if ATTACHMENT_EXTENSION_RE.fullmatch(suffix) else ""


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    # Always revalidate the HTML so new asset version query strings reach browsers.
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/api/tasks", response_model=list[TaskSummary])
def list_tasks(connection: sqlite3.Connection = Depends(get_db)) -> list[TaskSummary]:
    _archive_due_completed_tasks(connection)
    return [_task_summary(task) for task in _task_rows(connection, archived=False)]


@app.get("/api/archive/tasks", response_model=list[TaskSummary])
def list_archived_tasks(connection: sqlite3.Connection = Depends(get_db)) -> list[TaskSummary]:
    _archive_due_completed_tasks(connection)
    return [_task_summary(task) for task in _task_rows(connection, archived=True)]


@app.get("/api/worksets", response_model=list[WorksetRead])
def list_worksets(
    project: str, connection: sqlite3.Connection = Depends(get_db)
) -> list[WorksetRead]:
    if not PROJECT_SLUG_RE.fullmatch(project):
        raise HTTPException(status_code=422, detail="Некорректный ключ проекта")
    rows = connection.execute(
        "SELECT id FROM worksets WHERE project_slug = ? "
        "ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, updated_at DESC, id DESC",
        (project,),
    ).fetchall()
    return [_workset_summary(connection, int(row["id"])) for row in rows]


@app.post("/api/worksets", response_model=WorksetRead, status_code=201)
def create_workset(
    payload: WorksetCreate, connection: sqlite3.Connection = Depends(get_db)
) -> WorksetRead:
    now = utc_now()
    cursor = connection.execute(
        "INSERT INTO worksets (project_slug, name, status, created_at, updated_at) "
        "VALUES (?, ?, 'active', ?, ?)",
        (payload.project_slug, payload.name, now, now),
    )
    workset = _require_workset(connection, int(cursor.lastrowid))
    _record_workset_event(connection, workset, "created")
    connection.commit()
    return _workset_summary(connection, int(cursor.lastrowid))


@app.patch("/api/worksets/{workset_id}", response_model=WorksetRead)
def rename_workset(
    workset_id: int,
    payload: WorksetPatch,
    connection: sqlite3.Connection = Depends(get_db),
) -> WorksetRead:
    workset = _require_workset(connection, workset_id)
    if workset["name"] != payload.name:
        connection.execute(
            "UPDATE worksets SET name = ?, updated_at = ? WHERE id = ?",
            (payload.name, utc_now(), workset_id),
        )
        updated = _require_workset(connection, workset_id)
        _record_workset_event(connection, updated, "renamed")
    connection.commit()
    return _workset_summary(connection, workset_id)


@app.post("/api/worksets/{workset_id}/tasks", response_model=WorksetRead, status_code=200)
def add_workset_task(
    workset_id: int,
    payload: WorksetTaskAdd,
    connection: sqlite3.Connection = Depends(get_db),
) -> WorksetRead:
    task = _require_task(connection, payload.task_id)
    _add_task_to_workset(connection, workset_id, task)
    connection.commit()
    return _workset_summary(connection, workset_id)


@app.delete("/api/worksets/{workset_id}/tasks/{task_id}")
def remove_workset_task(
    workset_id: int,
    task_id: int,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, bool]:
    workset = _require_workset(connection, workset_id)
    task = _require_task(connection, task_id)
    membership = connection.execute(
        "SELECT 1 FROM workset_memberships WHERE workset_id = ? AND task_id = ?",
        (workset_id, task_id),
    ).fetchone()
    if membership is None:
        raise HTTPException(status_code=404, detail="Задача не входит в этот рабочий набор")
    _record_workset_event(connection, workset, "task_removed", task=task)
    connection.execute(
        "DELETE FROM workset_memberships WHERE workset_id = ? AND task_id = ?",
        (workset_id, task_id),
    )
    remaining = connection.execute(
        "SELECT COUNT(*) FROM workset_memberships WHERE workset_id = ?", (workset_id,)
    ).fetchone()[0]
    if remaining == 0:
        # An intentionally emptied set is no longer useful; event snapshots remain
        # available in the project's history after the set row is removed.
        _record_workset_event(connection, workset, "deleted_empty")
        connection.execute("DELETE FROM worksets WHERE id = ?", (workset_id,))
        deleted = True
    else:
        _sync_workset_state(connection, workset_id)
        deleted = False
    connection.commit()
    return {"deleted": deleted}


@app.get("/api/worksets/history", response_model=list[WorksetEventRead])
def workset_history(
    project: str, connection: sqlite3.Connection = Depends(get_db)
) -> list[WorksetEventRead]:
    if not PROJECT_SLUG_RE.fullmatch(project):
        raise HTTPException(status_code=422, detail="Некорректный ключ проекта")
    rows = connection.execute(
        "SELECT * FROM workset_events WHERE project_slug = ? "
        "ORDER BY created_at DESC, id DESC LIMIT 300",
        (project,),
    ).fetchall()
    return [WorksetEventRead(**dict(row)) for row in rows]


@app.get("/api/archive/settings", response_model=ArchiveSettingsRead)
def get_archive_settings(connection: sqlite3.Connection = Depends(get_db)) -> ArchiveSettingsRead:
    return ArchiveSettingsRead(**_archive_settings(connection))


@app.patch("/api/archive/settings", response_model=ArchiveSettingsRead)
def update_archive_settings(
    payload: ArchiveSettingsPatch, connection: sqlite3.Connection = Depends(get_db)
) -> ArchiveSettingsRead:
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        if value is None:
            raise HTTPException(status_code=400, detail=f"Настройка {key} не может быть null")
        stored_value = str(value).lower() if isinstance(value, bool) else str(value)
        connection.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, stored_value),
        )
    connection.commit()
    _archive_due_completed_tasks(connection)
    return ArchiveSettingsRead(**_archive_settings(connection))


@app.get("/api/task-settings", response_model=TaskSettingsRead)
def get_task_settings(connection: sqlite3.Connection = Depends(get_db)) -> TaskSettingsRead:
    return TaskSettingsRead(**_task_settings(connection))


@app.patch("/api/task-settings", response_model=TaskSettingsRead)
def update_task_settings(
    payload: TaskSettingsPatch, connection: sqlite3.Connection = Depends(get_db)
) -> TaskSettingsRead:
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        if value is None:
            raise HTTPException(status_code=400, detail=f"Настройка {key} не может быть null")
        connection.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value).lower()),
        )
    connection.commit()
    return TaskSettingsRead(**_task_settings(connection))


@app.post("/api/archive/completed")
def archive_all_completed(connection: sqlite3.Connection = Depends(get_db)) -> dict[str, int]:
    archived_at = utc_now()
    cursor = connection.execute(
        "UPDATE tasks SET archived_at = ? WHERE status = 'done' AND archived_at IS NULL",
        (archived_at,),
    )
    connection.commit()
    return {"archived": cursor.rowcount}


@app.post("/api/archive/tasks/{task_id}", response_model=TaskSummary)
def archive_task(task_id: int, connection: sqlite3.Connection = Depends(get_db)) -> TaskSummary:
    task = _require_task(connection, task_id)
    if task["status"] != "done":
        raise HTTPException(status_code=409, detail="Архивировать можно только завершённые задачи")
    if task["archived_at"]:
        return _task_summary(task)
    connection.execute(
        "UPDATE tasks SET archived_at = ? WHERE id = ? AND archived_at IS NULL",
        (utc_now(), task_id),
    )
    connection.commit()
    return _task_summary(_require_task(connection, task_id))


@app.post("/api/archive/tasks/{task_id}/restore", response_model=TaskSummary)
def restore_archived_task(
    task_id: int, connection: sqlite3.Connection = Depends(get_db)
) -> TaskSummary:
    task = _require_task(connection, task_id)
    if not task["archived_at"]:
        raise HTTPException(status_code=409, detail="Задача не находится в архиве")
    row = connection.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 FROM tasks "
        "WHERE status = 'done' AND archived_at IS NULL"
    ).fetchone()
    connection.execute(
        "UPDATE tasks SET archived_at = NULL, position = ? WHERE id = ?",
        (float(row[0]), task_id),
    )
    connection.commit()
    return _task_summary(_require_task(connection, task_id))


@app.post("/api/tasks", response_model=TaskSummary, status_code=201)
def create_task(
    payload: TaskCreate, connection: sqlite3.Connection = Depends(get_db)
) -> TaskSummary:
    if payload.workset_id is not None:
        workset = _require_workset(connection, payload.workset_id)
        if workset["status"] != "active":
            raise HTTPException(status_code=409, detail="В завершённый набор нельзя добавлять задачи")
        if _project_slug(payload.tags) != workset["project_slug"]:
            raise HTTPException(
                status_code=409, detail="Задача должна принадлежать проекту рабочего набора"
            )
    title = payload.title
    now = utc_now()
    position_row = connection.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 FROM tasks WHERE status = 'todo'"
    ).fetchone()
    cursor = connection.execute(
        """
        INSERT INTO tasks (title, description, result, status, position, tags, created_at,
                           updated_at, closed_at)
        VALUES (?, ?, ?, 'todo', ?, ?, ?, ?, NULL)
        """,
        (
            title,
            payload.description,
            payload.result,
            float(position_row[0]),
            payload.tags,
            now,
            now,
        ),
    )
    task = _require_task(connection, int(cursor.lastrowid))
    if payload.workset_id is not None:
        _add_task_to_workset(connection, payload.workset_id, task)
        task = _require_task(connection, int(cursor.lastrowid))
    connection.commit()
    return _task_summary(task)


@app.get("/api/tasks/{task_id}", response_model=TaskDetail)
def get_task(task_id: int, connection: sqlite3.Connection = Depends(get_db)) -> TaskDetail:
    task = _require_task(connection, task_id)
    attachments = [
        AttachmentRead(
            id=item["id"],
            task_id=item["task_id"],
            filename=item["filename"],
            size=item["size"],
            created_at=item["created_at"],
        )
        for item in _attachments_for_task(connection, task_id)
    ]
    base = _task_summary(task).model_dump()
    return TaskDetail(
        **base,
        description_html=render_safe_markdown(task["description"]),
        attachments=attachments,
    )


@app.patch("/api/tasks/{task_id}", response_model=TaskSummary)
def patch_task(
    task_id: int,
    payload: TaskPatch,
    connection: sqlite3.Connection = Depends(get_db),
) -> TaskSummary:
    current = _require_task(connection, task_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return _task_summary(current)

    for field in ("title", "status", "position"):
        if field in changes and changes[field] is None:
            raise HTTPException(status_code=400, detail=f"Поле {field} не может быть null")
    if "position" in changes and not math.isfinite(changes["position"]):
        raise HTTPException(status_code=400, detail="Позиция должна быть конечным числом")

    current_workset_id = current.get("workset_id")
    requested_workset_id = changes.get("workset_id", current_workset_id)
    workset_changed = "workset_id" in changes and requested_workset_id != current_workset_id
    if (
        current_workset_id is not None
        and requested_workset_id is not None
        and workset_changed
    ):
        raise HTTPException(
            status_code=409,
            detail="Сначала удалите задачу из прежнего рабочего набора",
        )
    new_workset = None
    if requested_workset_id is not None and workset_changed:
        new_workset = _require_workset(connection, int(requested_workset_id))
        if new_workset["status"] != "active":
            raise HTTPException(
                status_code=409,
                detail="В завершённый набор нельзя добавлять задачи",
            )
        new_tags = changes.get("tags", current["tags"])
        if _project_slug(new_tags or "") != new_workset["project_slug"]:
            raise HTTPException(
                status_code=409,
                detail="Задача должна принадлежать проекту рабочего набора",
            )

    new_status = changes.get("status", current["status"])
    if "tags" in changes and current_workset_id is not None:
        workset = _require_workset(connection, int(current_workset_id))
        if (
            not workset_changed
            and _project_slug(changes["tags"] or "") != workset["project_slug"]
        ):
            raise HTTPException(
                status_code=409,
                detail="Сначала удалите задачу из рабочего набора, чтобы изменить её проект",
            )
    blocked_close = False
    if current["status"] != "done" and new_status == "done":
        if _task_settings(connection)["require_result_to_close"]:
            result = changes.get("result", current["result"] or "")
            if not str(result or "").strip():
                blocked_close = True
                changes.pop("status", None)
                new_status = current["status"]
                if not changes:
                    raise HTTPException(
                        status_code=409,
                        detail="Перед закрытием задачи заполните поле «Результат выполнения».",
                    )
    assignments: dict[str, Any] = {}
    for field in ("title", "description", "result", "status", "position", "tags"):
        if field in changes:
            value = changes[field]
            if field in ("description", "result", "tags") and value is None:
                value = ""
            assignments[field] = value

    if "status" in changes and new_status != current["status"] and "position" not in changes:
        row = connection.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM tasks WHERE status = ?", (new_status,)
        ).fetchone()
        assignments["position"] = float(row[0])

    now = utc_now()
    closed_at = current["closed_at"]
    if current["status"] != "done" and new_status == "done":
        closed_at = now
    elif current["status"] == "done" and new_status != "done":
        closed_at = None
        if current.get("archived_at"):
            assignments["archived_at"] = None

    if workset_changed and current_workset_id is not None:
        old_workset = _require_workset(connection, int(current_workset_id))
        _record_workset_event(connection, old_workset, "task_removed", task=current)
        connection.execute(
            "DELETE FROM workset_memberships WHERE workset_id = ? AND task_id = ?",
            (current_workset_id, task_id),
        )
        remaining = connection.execute(
            "SELECT COUNT(*) FROM workset_memberships WHERE workset_id = ?",
            (current_workset_id,),
        ).fetchone()[0]
        if remaining == 0:
            _record_workset_event(connection, old_workset, "deleted_empty")
            connection.execute("DELETE FROM worksets WHERE id = ?", (current_workset_id,))
        else:
            _sync_workset_state(connection, int(current_workset_id))

    update_fields = [f"{field} = ?" for field in assignments]
    values = list(assignments.values())
    update_fields.extend(["updated_at = ?", "closed_at = ?"])
    values.extend([now, closed_at, task_id])
    connection.execute(f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ?", values)
    if new_workset is not None:
        updated_task = _require_task(connection, task_id)
        _add_task_to_workset(connection, int(requested_workset_id), updated_task)
    elif not workset_changed and "status" in changes and current_workset_id is not None:
        _sync_workset_state(connection, int(current_workset_id))
    connection.commit()
    if blocked_close:
        raise HTTPException(
            status_code=409,
            detail="Перед закрытием задачи заполните поле «Результат выполнения».",
        )
    return _task_summary(_require_task(connection, task_id))


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, connection: sqlite3.Connection = Depends(get_db)) -> Response:
    task = _require_task(connection, task_id)
    workset_id = task.get("workset_id")
    workset = _require_workset(connection, int(workset_id)) if workset_id is not None else None
    if workset is not None:
        _record_workset_event(connection, workset, "task_deleted", task=task)
    connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    if workset is not None:
        remaining = connection.execute(
            "SELECT COUNT(*) FROM workset_memberships WHERE workset_id = ?", (workset_id,)
        ).fetchone()[0]
        if remaining == 0:
            _record_workset_event(connection, workset, "deleted_empty")
            connection.execute("DELETE FROM worksets WHERE id = ?", (workset_id,))
        else:
            _sync_workset_state(connection, int(workset_id))
    connection.commit()
    shutil.rmtree(settings.attachments_dir / str(task_id), ignore_errors=True)
    return Response(status_code=204)


@app.post("/api/tasks/{task_id}/files", response_model=list[AttachmentRead], status_code=201)
async def upload_attachments(
    task_id: int,
    files: list[UploadFile] = File(...),
    connection: sqlite3.Connection = Depends(get_db),
) -> list[AttachmentRead]:
    _require_task(connection, task_id)
    if not files:
        raise HTTPException(status_code=400, detail="Выберите хотя бы один файл")

    prepared: list[tuple[UploadFile, str, bytes]] = []
    for upload in files:
        filename = _clean_filename(upload.filename)
        content = await upload.read(settings.max_file_size_bytes + 1)
        if len(content) > settings.max_file_size_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Файл {filename} превышает лимит {settings.MAX_FILE_SIZE_MB} МБ",
            )
        prepared.append((upload, filename, content))

    directory = settings.attachments_dir / str(task_id)
    directory.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []
    inserted_ids: list[int] = []
    try:
        for _, filename, content in prepared:
            stored_name = f"{uuid.uuid4().hex}{_stored_extension(filename)}"
            path = directory / stored_name
            saved_paths.append(path)
            path.write_bytes(content)
            cursor = connection.execute(
                """
                INSERT INTO attachments (task_id, filename, stored_name, size, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (task_id, filename, stored_name, len(content), utc_now()),
            )
            inserted_ids.append(int(cursor.lastrowid))
        connection.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (utc_now(), task_id))
        connection.commit()
    except Exception:
        connection.rollback()
        for path in saved_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                # Keep rolling back other files; the original upload error is re-raised.
                pass
        _remove_empty_attachment_dir(task_id)
        raise

    if inserted_ids:
        placeholders = ",".join("?" for _ in inserted_ids)
        rows = connection.execute(
            f"""
            SELECT id, task_id, filename, size, created_at
            FROM attachments WHERE id IN ({placeholders}) ORDER BY id
            """,
            inserted_ids,
        ).fetchall()
        return [AttachmentRead(**dict(row)) for row in rows]
    return []


@app.get("/api/files/{attachment_id}")
def download_attachment(
    attachment_id: int, connection: sqlite3.Connection = Depends(get_db)
) -> FileResponse:
    row = connection.execute(
        "SELECT id, task_id, filename, stored_name FROM attachments WHERE id = ?", (attachment_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Вложение не найдено")
    path = _get_attachment_path(int(row["task_id"]), row["stored_name"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл вложения отсутствует на диске")
    return FileResponse(path, filename=row["filename"], content_disposition_type="attachment")


@app.delete("/api/files/{attachment_id}", status_code=204)
def delete_attachment(
    attachment_id: int, connection: sqlite3.Connection = Depends(get_db)
) -> Response:
    row = connection.execute(
        "SELECT id, task_id, stored_name FROM attachments WHERE id = ?", (attachment_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Вложение не найдено")
    path = _get_attachment_path(int(row["task_id"]), row["stored_name"])
    connection.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
    connection.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (utc_now(), row["task_id"]))
    connection.commit()
    path.unlink(missing_ok=True)
    _remove_empty_attachment_dir(int(row["task_id"]))
    return Response(status_code=204)


@app.post("/api/import", response_model=ImportResult)
async def import_markdown(
    files: list[UploadFile] = File(...), connection: sqlite3.Connection = Depends(get_db)
) -> ImportResult:
    if not files:
        raise HTTPException(status_code=400, detail="Выберите хотя бы один Markdown-файл")

    created = 0
    skipped: list[ImportSkipped] = []
    for upload in files:
        filename = _clean_filename(upload.filename)
        if not filename.lower().endswith(".md"):
            skipped.append(
                ImportSkipped(filename=filename, reason="поддерживаются только файлы .md")
            )
            continue
        raw = await upload.read(10 * 1024 * 1024 + 1)
        if len(raw) > 10 * 1024 * 1024:
            skipped.append(
                ImportSkipped(filename=filename, reason="Markdown-файл превышает лимит 10 МБ")
            )
            continue
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            skipped.append(
                ImportSkipped(filename=filename, reason="файл должен быть в кодировке UTF-8")
            )
            continue

        parsed_tasks, skipped_records = parse_markdown_file(filename, content)
        for parsed in parsed_tasks:
            _create_task(connection, parsed)
            created += 1
        skipped.extend(
            ImportSkipped(filename=record.filename, reason=record.reason, line=record.line)
            for record in skipped_records
        )
    connection.commit()
    return ImportResult(created=created, skipped=skipped)


@app.get("/api/export")
def export_tasks(format: str = "md", connection: sqlite3.Connection = Depends(get_db)) -> Response:
    if format not in {"md", "zip"}:
        raise HTTPException(status_code=400, detail="Поддерживаемые форматы: md, zip")
    tasks = _task_rows(connection)
    attachments_by_task = {
        task["id"]: _attachments_for_task(connection, task["id"]) for task in tasks
    }
    if format == "md":
        content = build_markdown_export(tasks, attachments_by_task)
        filename = export_filename("md")
        media_type = "text/markdown; charset=utf-8"
    else:
        worksets = [
            dict(row)
            for row in connection.execute("SELECT * FROM worksets ORDER BY id").fetchall()
        ]
        memberships = [
            dict(row)
            for row in connection.execute(
                "SELECT workset_id, task_id, added_at FROM workset_memberships ORDER BY workset_id, task_id"
            ).fetchall()
        ]
        events = [
            dict(row)
            for row in connection.execute("SELECT * FROM workset_events ORDER BY id").fetchall()
        ]
        content = build_zip_export(
            tasks,
            attachments_by_task,
            worksets=worksets,
            workset_memberships=memberships,
            workset_events=events,
        )
        filename = export_filename("zip")
        media_type = "application/zip"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/tasks/{task_id}/export")
def export_one_task(
    task_id: int, connection: sqlite3.Connection = Depends(get_db)
) -> Response:
    # Import locally to avoid coupling this endpoint to the export module's import layout.
    from app.exporter import build_task_zip_export

    task = _require_task(connection, task_id)
    attachments = _attachments_for_task(connection, task_id)
    attachment_paths: dict[int, Path] = {}
    for attachment in attachments:
        path = _get_attachment_path(task_id, attachment["stored_name"])
        if not path.is_file():
            raise HTTPException(
                status_code=404,
                detail=(
                    "Не удалось экспортировать задачу: вложение "
                    f"«{attachment['filename']}» отсутствует на диске"
                ),
            )
        attachment_paths[int(attachment["id"])] = path
    try:
        content = build_task_zip_export(task, attachments, attachment_paths)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="task-{task_id}.zip"'},
    )


@app.post("/api/preview-markdown")
def preview_markdown(payload: MarkdownPreviewRequest) -> dict[str, str]:
    return {"html": render_safe_markdown(payload.text)}


@app.get("/api/config", include_in_schema=False)
def public_config() -> dict[str, int]:
    return {"wip_limit": settings.WIP_LIMIT, "max_file_size_mb": settings.MAX_FILE_SIZE_MB}


@app.get("/api/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}
