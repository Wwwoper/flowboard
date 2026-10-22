"""Markdown and portable ZIP export."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Any

from app import frontmatter_compat as frontmatter
from app.config import STATUS_LABELS, STATUSES, settings


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _tags(value: str) -> list[str]:
    return [tag.strip() for tag in value.split(",") if tag.strip()]


def build_markdown_export(
    tasks: list[dict[str, Any]], attachments_by_task: dict[int, list[dict[str, Any]]]
) -> bytes:
    """Create a human-readable Markdown file, also supported by this app's importer."""
    header = frontmatter.dumps(
        frontmatter.Post("", kanban_export=True, exported_at=utc_now())
    ).rstrip()
    lines = [header, "", "# Экспорт канбан-трекера", ""]
    for status in STATUSES:
        lines.extend([f"## {STATUS_LABELS[status]}", ""])
        status_tasks = [task for task in tasks if task["status"] == status]
        if not status_tasks:
            lines.extend(["_Нет задач._", ""])
            continue
        for task in status_tasks:
            task_attachments = attachments_by_task.get(task["id"], [])
            metadata: dict[str, Any] = {
                "title": task["title"],
                "status": task["status"],
                "tags": _tags(task["tags"]),
                "created_at": task["created_at"],
                "updated_at": task["updated_at"],
                "attachments": [attachment["filename"] for attachment in task_attachments],
            }
            if task["closed_at"]:
                metadata["closed_at"] = task["closed_at"]
            post = frontmatter.Post(task["description"] or "", **metadata)
            lines.append("<!-- kanban-task-start -->")
            lines.append(frontmatter.dumps(post).rstrip())
            lines.append("<!-- kanban-task-end -->")
            lines.append("")
    return ("\n".join(lines).rstrip() + "\n").encode("utf-8")


def build_zip_export(
    tasks: list[dict[str, Any]],
    attachments_by_task: dict[int, list[dict[str, Any]]],
) -> bytes:
    """Package JSON task data and every attachment into one portable archive."""
    manifest = {
        "format_version": 1,
        "exported_at": utc_now(),
        "tasks": [],
    }
    for task in tasks:
        item = dict(task)
        item["attachments"] = [
            {
                "id": attachment["id"],
                "filename": attachment["filename"],
                "stored_name": attachment["stored_name"],
                "size": attachment["size"],
                "created_at": attachment["created_at"],
                "archive_path": f"attachments/{task['id']}/{attachment['stored_name']}",
            }
            for attachment in attachments_by_task.get(task["id"], [])
        ]
        manifest["tasks"].append(item)

    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "tasks.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        for task in tasks:
            for attachment in attachments_by_task.get(task["id"], []):
                path = settings.attachments_dir / str(task["id"]) / attachment["stored_name"]
                if path.is_file():
                    archive.write(
                        path, arcname=f"attachments/{task['id']}/{attachment['stored_name']}"
                    )
    return output.getvalue()


def export_filename(extension: str) -> str:
    date = datetime.now(UTC).date().isoformat()
    return f"tasks-{date}.{extension}"
