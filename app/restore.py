"""Restore a ZIP backup created by GET /api/export?format=zip.

Example: uv run python -m app.restore backups/tasks-2026-10-22.zip --data-dir ./data-restored
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from app.config import STATUSES
from app.db import connect, initialize_database


def _safe_member_name(name: str) -> str:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"Недопустимый путь в ZIP: {name}")
    return path.as_posix()


def _read_manifest(archive: zipfile.ZipFile) -> dict[str, Any]:
    try:
        manifest = json.loads(archive.read("tasks.json"))
    except KeyError as exc:
        raise ValueError("В архиве отсутствует tasks.json") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("tasks.json повреждён или имеет неверную кодировку") from exc
    if manifest.get("format_version") != 1 or not isinstance(manifest.get("tasks"), list):
        raise ValueError("Неподдерживаемая версия формата резервной копии")
    return manifest


def restore_backup(archive_path: Path, data_dir: Path, *, replace: bool = False) -> int:
    """Restore tasks and attachments into an isolated directory, then atomically swap it in."""
    archive_path = archive_path.expanduser().resolve()
    target = data_dir.expanduser().resolve()
    if not archive_path.is_file():
        raise ValueError(f"Архив не найден: {archive_path}")
    if target == archive_path or target in archive_path.parents:
        raise ValueError("Каталог данных не должен совпадать с путём архива или содержать его")

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        has_content = any(target.iterdir())
        if has_content and not replace:
            raise FileExistsError(
                f"Каталог {target} не пуст. Укажите другой --data-dir или явно добавьте --replace."
            )

    with zipfile.ZipFile(archive_path, "r") as archive:
        for info in archive.infolist():
            _safe_member_name(info.filename)
        manifest = _read_manifest(archive)
        task_items = manifest["tasks"]
        seen_ids: set[int] = set()
        for task in task_items:
            task_id = task.get("id")
            if not isinstance(task_id, int) or task_id <= 0 or task_id in seen_ids:
                raise ValueError("В tasks.json обнаружен некорректный или повторяющийся ID задачи")
            seen_ids.add(task_id)
            if task.get("status") not in STATUSES:
                raise ValueError(f"Неизвестный статус задачи {task_id}")
            result = task.get("result", "")
            if not isinstance(result, str) or len(result) > 5000:
                raise ValueError(
                    f"Некорректный результат выполнения задачи {task_id}"
                )
            if (
                not isinstance(task.get("title"), str)
                or not task["title"].strip()
                or len(task["title"]) > 200
            ):
                raise ValueError(f"Некорректный заголовок задачи {task_id}")

        staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.restore-", dir=target.parent))
        try:
            db_path = staging / "tracker.db"
            attachments_root = staging / "attachments"
            initialize_database(db_path)
            connection = connect(db_path)
            try:
                for task in task_items:
                    connection.execute(
                        """
                        INSERT INTO tasks (
                            id, title, description, result, status, position, tags,
                            created_at, updated_at, closed_at, archived_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            task["id"],
                            task["title"],
                            task.get("description", ""),
                            task.get("result", ""),
                            task["status"],
                            float(task.get("position", 0)),
                            task.get("tags", ""),
                            task["created_at"],
                            task["updated_at"],
                            task.get("closed_at"),
                            task.get("archived_at"),
                        ),
                    )
                    for attachment in task.get("attachments", []):
                        stored_name = attachment.get("stored_name")
                        if (
                            not isinstance(stored_name, str)
                            or Path(stored_name).name != stored_name
                        ):
                            raise ValueError(f"Некорректное имя вложения для задачи {task['id']}")
                        expected_prefix = f"attachments/{task['id']}/"
                        member = attachment.get("archive_path")
                        expected_member = f"{expected_prefix}{stored_name}"
                        if member != expected_member:
                            raise ValueError(f"Некорректный путь вложения для задачи {task['id']}")
                        safe_member = _safe_member_name(member)
                        try:
                            content = archive.read(safe_member)
                        except KeyError as exc:
                            raise ValueError(f"В архиве отсутствует файл {safe_member}") from exc
                        destination = attachments_root / str(task["id"]) / stored_name
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(content)
                        connection.execute(
                            """
                            INSERT INTO attachments (
                                id, task_id, filename, stored_name, size, created_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                attachment["id"],
                                task["id"],
                                attachment["filename"],
                                stored_name,
                                len(content),
                                attachment["created_at"],
                            ),
                        )
                workset_items = manifest.get("worksets", [])
                membership_items = manifest.get("workset_memberships", [])
                event_items = manifest.get("workset_events", [])
                if not all(
                    isinstance(items, list)
                    for items in (workset_items, membership_items, event_items)
                ):
                    raise ValueError("Некорректные данные рабочих наборов в резервной копии")
                workset_ids: set[int] = set()
                for workset in workset_items:
                    workset_id = workset.get("id")
                    project_slug = workset.get("project_slug")
                    name = workset.get("name")
                    status = workset.get("status")
                    if (
                        not isinstance(workset_id, int)
                        or isinstance(workset_id, bool)
                        or workset_id <= 0
                        or workset_id in workset_ids
                        or not isinstance(project_slug, str)
                        or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", project_slug)
                        or not isinstance(name, str)
                        or not name.strip()
                        or len(name) > 100
                        or status not in {"active", "completed"}
                    ):
                        raise ValueError(
                            "В резервной копии обнаружен некорректный рабочий набор"
                        )
                    workset_ids.add(workset_id)
                    connection.execute(
                        """
                        INSERT INTO worksets (
                            id, project_slug, name, status, created_at, updated_at, completed_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            workset_id,
                            project_slug,
                            name.strip(),
                            status,
                            workset.get("created_at", ""),
                            workset.get("updated_at", ""),
                            workset.get("completed_at"),
                        ),
                    )
                for membership in membership_items:
                    workset_id = membership.get("workset_id")
                    task_id = membership.get("task_id")
                    if (
                        not isinstance(workset_id, int)
                        or isinstance(workset_id, bool)
                        or not isinstance(task_id, int)
                        or isinstance(task_id, bool)
                        or workset_id not in workset_ids
                        or task_id not in seen_ids
                    ):
                        raise ValueError("Некорректная связь задачи с рабочим набором")
                    connection.execute(
                        """
                        INSERT INTO workset_memberships (workset_id, task_id, added_at)
                        VALUES (?, ?, ?)
                        """,
                        (workset_id, task_id, membership.get("added_at", "")),
                    )
                event_ids: set[int] = set()
                for event in event_items:
                    event_id = event.get("id")
                    workset_id = event.get("workset_id")
                    task_id = event.get("task_id")
                    if (
                        not isinstance(event_id, int)
                        or isinstance(event_id, bool)
                        or event_id <= 0
                        or event_id in event_ids
                        or (
                            workset_id is not None
                            and (
                                not isinstance(workset_id, int)
                                or isinstance(workset_id, bool)
                                or workset_id <= 0
                            )
                        )
                        or (
                            task_id is not None
                            and (
                                not isinstance(task_id, int)
                                or isinstance(task_id, bool)
                                or task_id <= 0
                            )
                        )
                        or (
                            event.get("task_status") is not None
                            and (
                                not isinstance(event.get("task_status"), str)
                                or event["task_status"] not in {"todo", "doing", "waiting", "done"}
                            )
                        )
                        or not isinstance(event.get("task_title", ""), str)
                        or (
                            event.get("task_closed_at") is not None
                            and not isinstance(event.get("task_closed_at"), str)
                        )
                        or any(
                            event.get(field) is not None
                            and (
                                not isinstance(event[field], int)
                                or isinstance(event[field], bool)
                                or event[field] < 0
                            )
                            for field in ("task_count", "done_count")
                        )
                        or (
                            event.get("task_count") is not None
                            and event.get("done_count") is not None
                            and event["done_count"] > event["task_count"]
                        )
                        or not isinstance(event.get("project_slug"), str)
                        or not re.fullmatch(
                            r"[a-z0-9]+(?:-[a-z0-9]+)*", event["project_slug"]
                        )
                        or not isinstance(event.get("workset_name"), str)
                        or not isinstance(event.get("event_type"), str)
                    ):
                        raise ValueError(
                            "В резервной копии обнаружено некорректное событие рабочего набора"
                        )
                    event_ids.add(event_id)
                    connection.execute(
                        """
                        INSERT INTO workset_events (
                            id, workset_id, project_slug, workset_name, task_id,
                            task_title, task_status, task_closed_at, task_count, done_count,
                            event_type, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event_id,
                            workset_id,
                            event["project_slug"],
                            event["workset_name"],
                            task_id,
                            event.get("task_title", ""),
                            event.get("task_status"),
                            event.get("task_closed_at"),
                            event.get("task_count"),
                            event.get("done_count"),
                            event["event_type"],
                            event.get("created_at", ""),
                        ),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

            if target.exists():
                if any(target.iterdir()) and not replace:
                    raise FileExistsError(
                        f"Каталог {target} стал непустым; восстановление отменено"
                    )
                old_path = target.parent / f".{target.name}.old-{uuid4().hex}"
                if any(target.iterdir()):
                    target.rename(old_path)
                    try:
                        staging.rename(target)
                    except Exception:
                        old_path.rename(target)
                        raise
                    shutil.rmtree(old_path, ignore_errors=True)
                else:
                    target.rmdir()
                    staging.rename(target)
            else:
                staging.rename(target)
        except Exception:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            raise

    return len(task_items)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Восстановить канбан-трекер из ZIP-резервной копии"
    )
    parser.add_argument("archive", type=Path, help="ZIP-файл, полученный через экспорт")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data-restored"),
        help="каталог для восстановленных данных",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="разрешить замену непустого каталога данных",
    )
    args = parser.parse_args()
    try:
        restored_count = restore_backup(args.archive, args.data_dir, replace=args.replace)
    except (ValueError, zipfile.BadZipFile, OSError, sqlite3.Error) as error:
        parser.error(str(error))
    print(f"Восстановлено задач: {restored_count}")
    print(f"Данные: {args.data_dir.resolve()}")
    print("Для запуска укажите этот каталог через TRACKER_DATA_DIR.")


if __name__ == "__main__":
    main()
