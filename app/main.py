"""FastAPI routes for the single-user Kanban Tracker."""

from __future__ import annotations

import math
import re
import shutil
import sqlite3
import uuid
from contextlib import asynccontextmanager
from pathlib import Path, PurePath, PureWindowsPath
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import get_db, initialize_database
from app.exporter import build_markdown_export, build_zip_export, export_filename
from app.importer import ParsedTask, parse_markdown_file, utc_now
from app.markdown import render_safe_markdown
from app.models import (
    AttachmentRead,
    ImportResult,
    ImportSkipped,
    MarkdownPreviewRequest,
    TaskCreate,
    TaskDetail,
    TaskPatch,
    TaskSummary,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
ATTACHMENT_EXTENSION_RE = re.compile(r"\.[A-Za-z0-9]{1,10}$")


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    settings.attachments_dir.mkdir(parents=True, exist_ok=True)
    yield


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


def _task_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT t.*, COUNT(a.id) AS attachments_count
        FROM tasks AS t
        LEFT JOIN attachments AS a ON a.task_id = t.id
        GROUP BY t.id
        ORDER BY CASE t.status
            WHEN 'todo' THEN 0 WHEN 'doing' THEN 1 WHEN 'waiting' THEN 2 ELSE 3 END,
            t.position, t.id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _task_row(connection: sqlite3.Connection, task_id: int) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT t.*, COUNT(a.id) AS attachments_count
        FROM tasks AS t
        LEFT JOIN attachments AS a ON a.task_id = t.id
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
        INSERT INTO tasks (title, description, status, position, tags, created_at,
                           updated_at, closed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (task.title, task.description, task.status, position, task.tags, created, updated, closed),
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
    return [_task_summary(task) for task in _task_rows(connection)]


@app.post("/api/tasks", response_model=TaskSummary, status_code=201)
def create_task(
    payload: TaskCreate, connection: sqlite3.Connection = Depends(get_db)
) -> TaskSummary:
    title = payload.title
    now = utc_now()
    position_row = connection.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 FROM tasks WHERE status = 'todo'"
    ).fetchone()
    cursor = connection.execute(
        """
        INSERT INTO tasks (title, description, status, position, tags, created_at,
                           updated_at, closed_at)
        VALUES (?, ?, 'todo', ?, ?, ?, ?, NULL)
        """,
        (title, payload.description, float(position_row[0]), payload.tags, now, now),
    )
    connection.commit()
    task = _require_task(connection, int(cursor.lastrowid))
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

    new_status = changes.get("status", current["status"])
    assignments: dict[str, Any] = {}
    for field in ("title", "description", "status", "position", "tags"):
        if field in changes:
            value = changes[field]
            if field in ("description", "tags") and value is None:
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

    update_fields = [f"{field} = ?" for field in assignments]
    values = list(assignments.values())
    update_fields.extend(["updated_at = ?", "closed_at = ?"])
    values.extend([now, closed_at, task_id])
    connection.execute(f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ?", values)
    connection.commit()
    return _task_summary(_require_task(connection, task_id))


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, connection: sqlite3.Connection = Depends(get_db)) -> Response:
    _require_task(connection, task_id)
    connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
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
            path.write_bytes(content)
            saved_paths.append(path)
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
            path.unlink(missing_ok=True)
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
        content = build_zip_export(tasks, attachments_by_task)
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
