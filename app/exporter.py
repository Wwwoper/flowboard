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
                "result": task.get("result") or "",
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
    *,
    worksets: list[dict[str, Any]] | None = None,
    workset_memberships: list[dict[str, Any]] | None = None,
    workset_events: list[dict[str, Any]] | None = None,
) -> bytes:
    """Package JSON task data and every attachment into one portable archive."""
    manifest = {
        "format_version": 1,
        "exported_at": utc_now(),
        "tasks": [],
        "worksets": worksets or [],
        "workset_memberships": workset_memberships or [],
        "workset_events": workset_events or [],
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


def _unique_export_filename(filename: str, used_names: set[str]) -> str:
    """Return a flat, collision-free filename safe to use at the archive root."""
    raw_name = str(filename or "attachment").replace("\\", "/")
    basename = raw_name.rsplit("/", 1)[-1]
    basename = "".join(character for character in basename if character.isprintable()).strip()
    if basename in {"", ".", ".."}:
        basename = "attachment"
    basename = basename[:255]
    candidate = basename
    index = 2
    while candidate.casefold() in used_names:
        dot_index = basename.rfind(".")
        suffix = basename[dot_index:] if 0 < dot_index < len(basename) - 1 else ""
        stem = basename[: -len(suffix)] if suffix else basename
        extra = f" ({index})"
        candidate = f"{stem[: max(1, 255 - len(suffix) - len(extra))]}{extra}{suffix}"
        index += 1
    used_names.add(candidate.casefold())
    return candidate


def build_task_zip_export(
    task: dict[str, Any],
    attachments: list[dict[str, Any]],
    attachment_paths: dict[int, Path],
) -> bytes:
    """Package one task as a portable Markdown file with sibling attachment files."""
    from urllib.parse import quote

    markdown_filename = f"task-{task['id']}.md"
    used_names = {markdown_filename.casefold()}
    export_names: list[tuple[dict[str, Any], str]] = []
    for attachment in attachments:
        export_names.append(
            (attachment, _unique_export_filename(attachment["filename"], used_names))
        )

    filenames = [filename for _, filename in export_names]
    metadata: dict[str, Any] = {
        "title": task["title"],
        "result": task.get("result") or "",
        "status": task["status"],
        "tags": _tags(task["tags"]),
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
        "attachments": filenames,
        "flowboard_export_format": "single-task-v1",
    }
    if task.get("closed_at"):
        metadata["closed_at"] = task["closed_at"]

    # Keep description Markdown intact while separating generated document chrome.
    # Import uses these markers to retrieve only the original description.
    status_label = STATUS_LABELS.get(task["status"], task["status"])
    description = str(task.get("description") or "").strip("\r\n")
    lines = [
        f"# {task['title']}",
        "",
        f"**Статус:** {status_label}",
    ]
    tags = _tags(task["tags"])
    if tags:
        rendered_tags = ", ".join("`" + tag.replace("`", "\\`") + "`" for tag in tags)
        lines.append(f"**Теги:** {rendered_tags}")
    lines.extend(["", "## Описание", "", "<!-- flowboard-description-start -->", ""])
    if description:
        lines.append(description)
    lines.extend(
        [
            "",
            "<!-- flowboard-description-end -->",
            "",
            "## Результат выполнения",
            "",
            "<!-- flowboard-result-start -->",
            "",
        ]
    )
    result = str(task.get("result") or "").strip("\r\n")
    if result:
        lines.append(result)
    lines.extend(["", "<!-- flowboard-result-end -->", "", "## Вложения", ""])
    if filenames:
        for filename in filenames:
            label = filename.replace("\\", "\\\\").replace("[", r"\[").replace("]", r"\]")
            lines.append(f"- [{label}]({quote(filename, safe='')})")
    else:
        lines.append("_Нет вложений._")

    body = "\n".join(lines).rstrip("\n") + "\n"
    markdown = frontmatter.dumps(frontmatter.Post(body, **metadata))
    if not markdown.endswith("\n"):
        markdown += "\n"

    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(markdown_filename, markdown.encode("utf-8"))
        for attachment, filename in export_names:
            path = attachment_paths.get(int(attachment["id"]))
            if path is None or not path.is_file():
                raise FileNotFoundError(f"Вложение «{attachment['filename']}» не найдено")
            archive.write(path, arcname=filename)
    return output.getvalue()


def export_filename(extension: str) -> str:
    date = datetime.now(UTC).date().isoformat()
    return f"tasks-{date}.{extension}"
