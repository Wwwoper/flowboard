"""Markdown import support for task frontmatter and checklist files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app import frontmatter_compat as frontmatter
from app.config import STATUSES

CHECKBOX_RE = re.compile(r"^\s*-\s+\[([ xX])\]\s+(.+?)\s*$")
TASK_DESCRIPTION_RE = re.compile(
    r"(?s)<!-- flowboard-description-start -->\r?\n(.*?)\r?\n"
    r"<!-- flowboard-description-end -->"
)
EXPORTED_TASK_RE = re.compile(
    r"(?ms)^<!-- kanban-task-start -->\s*\n---\s*\n"
    r"(?P<meta>.*?)\n---\s*\n(?P<body>.*?)\n<!-- kanban-task-end -->"
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_timestamp(value: Any) -> str | None:
    """Return a normalized UTC timestamp, or None when the value is invalid."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_status(value: Any) -> str:
    return value if isinstance(value, str) and value in STATUSES else "todo"


def normalize_tags(value: Any) -> str:
    if isinstance(value, list | tuple | set):
        items = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(items)
    if isinstance(value, str):
        return ", ".join(part.strip() for part in value.split(",") if part.strip())
    return ""


@dataclass(frozen=True)
class ParsedTask:
    title: str
    description: str = ""
    status: str = "todo"
    tags: str = ""
    created_at: str | None = None
    updated_at: str | None = None
    closed_at: str | None = None


@dataclass(frozen=True)
class SkippedRecord:
    filename: str
    reason: str
    line: int | None = None


def _task_from_metadata(
    metadata: dict[str, Any], body: str, filename: str
) -> tuple[ParsedTask | None, SkippedRecord | None]:
    title_value = metadata.get("title")
    title = title_value.strip() if isinstance(title_value, str) else ""
    if not title:
        return None, SkippedRecord(filename, "не указан непустой title")
    if len(title) > 200:
        return None, SkippedRecord(filename, "заголовок длиннее 200 символов")

    if metadata.get("flowboard_export_format") == "single-task-v1":
        description_match = TASK_DESCRIPTION_RE.search(body)
        if description_match is None:
            return None, SkippedRecord(
                filename, "в экспортном Markdown не найдено описание задачи"
            )
        description = description_match.group(1).strip("\r\n")
    else:
        description = body.strip()
    if len(description) > 5000:
        return None, SkippedRecord(filename, "описание длиннее 5000 символов")

    status = normalize_status(metadata.get("status"))
    closed_at = normalize_timestamp(metadata.get("closed_at"))
    if status == "done" and closed_at is None:
        closed_at = utc_now()
    if status != "done":
        closed_at = None

    return (
        ParsedTask(
            title=title,
            description=description,
            status=status,
            tags=normalize_tags(metadata.get("tags")),
            created_at=normalize_timestamp(metadata.get("created_at")),
            updated_at=normalize_timestamp(metadata.get("updated_at")),
            closed_at=closed_at,
        ),
        None,
    )


def _parse_export_bundle(
    content: str, filename: str
) -> tuple[list[ParsedTask], list[SkippedRecord]]:
    tasks: list[ParsedTask] = []
    skipped: list[SkippedRecord] = []
    for match in EXPORTED_TASK_RE.finditer(content):
        raw_metadata = match.group("meta")
        body = match.group("body").strip()
        try:
            post = frontmatter.loads(f"---\n{raw_metadata}\n---\n{body}")
        except Exception:  # Bad records are reported individually; later records still import.
            skipped.append(SkippedRecord(filename, "не удалось разобрать метаданные задачи"))
            continue
        task, reason = _task_from_metadata(dict(post.metadata), post.content, filename)
        if task is not None:
            tasks.append(task)
        elif reason is not None:
            skipped.append(reason)
    if not tasks and not skipped:
        skipped.append(SkippedRecord(filename, "в экспортном Markdown не найдено задач"))
    return tasks, skipped


def parse_markdown_file(
    filename: str, content: str
) -> tuple[list[ParsedTask], list[SkippedRecord]]:
    """Parse one Markdown file, returning task records and per-file skip reasons."""
    if not filename.lower().endswith(".md"):
        return [], [SkippedRecord(filename, "поддерживаются только файлы .md")]
    if not content.strip():
        return [], [SkippedRecord(filename, "пустой файл")]

    try:
        post = frontmatter.loads(content)
    except Exception:
        post = None

    if post is not None and post.metadata.get("kanban_export") is True:
        return _parse_export_bundle(post.content, filename)

    if post is not None and "title" in post.metadata:
        task, reason = _task_from_metadata(dict(post.metadata), post.content, filename)
        return ([task] if task else []), ([reason] if reason else [])

    tasks: list[ParsedTask] = []
    skipped: list[SkippedRecord] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        match = CHECKBOX_RE.match(line)
        if not match:
            continue
        title = match.group(2).strip()
        if not title:
            skipped.append(SkippedRecord(filename, "пустой пункт чек-листа", line_number))
            continue
        if len(title) > 200:
            skipped.append(SkippedRecord(filename, "заголовок длиннее 200 символов", line_number))
            continue
        status = "done" if match.group(1).lower() == "x" else "todo"
        tasks.append(
            ParsedTask(
                title=title,
                status=status,
                closed_at=utc_now() if status == "done" else None,
            )
        )

    if not tasks and not skipped:
        skipped.append(
            SkippedRecord(filename, "не найден frontmatter с title или пункты чек-листа")
        )
    return tasks, skipped
