"""Versioned single-task transfer archive validation."""

from __future__ import annotations

import io
import json
import stat
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from app.config import MAX_TASK_TEXT_LENGTH, STATUSES, settings
from app.importer import ParsedTask, normalize_timestamp
from app.task_types import normalize_task_type, split_legacy_tags

MAX_ARCHIVE_SIZE = 50 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 101
MAX_MANIFEST_SIZE = 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_SIZE = 100 * 1024 * 1024


@dataclass(frozen=True)
class ImportedAttachment:
    filename: str
    content: bytes
    created_at: str | None


@dataclass(frozen=True)
class ParsedTaskArchive:
    task: ParsedTask
    attachments: tuple[ImportedAttachment, ...]


def _invalid(message: str) -> ValueError:
    return ValueError(f"Некорректный архив задачи: {message}")


def _required_string(value: Any, field: str, *, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid(f"поле task.{field} должно быть непустой строкой")
    if len(value) > max_length:
        raise _invalid(f"поле task.{field} превышает допустимую длину")
    return value.strip()


def parse_task_archive(raw: bytes) -> ParsedTaskArchive:
    """Validate and parse a flowboard-task-v1 ZIP without extracting paths."""
    if len(raw) > MAX_ARCHIVE_SIZE:
        raise _invalid("размер ZIP превышает 50 МБ")
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except (zipfile.BadZipFile, OSError) as error:
        raise _invalid("файл не является корректным ZIP") from error

    with archive:
        infos = archive.infolist()
        if not infos or len(infos) > MAX_ARCHIVE_ENTRIES:
            raise _invalid("недопустимое количество файлов в ZIP")
        names = [info.filename for info in infos]
        info_by_name = {info.filename: info for info in infos}
        if len(names) != len(set(names)):
            raise _invalid("ZIP содержит повторяющиеся имена файлов")
        if "task.json" not in names:
            raise _invalid("не найден task.json")
        total_size = 0
        for info in infos:
            path = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in info.filename
                or not info.filename
                or stat.S_ISLNK(mode)
                or info.is_dir()
            ):
                raise _invalid("ZIP содержит небезопасный путь")
            if info.flag_bits & 0x1:
                raise _invalid("зашифрованные ZIP-файлы не поддерживаются")
            total_size += info.file_size
        if total_size > MAX_TOTAL_UNCOMPRESSED_SIZE:
            raise _invalid("распакованный размер ZIP превышает 100 МБ")

        if info_by_name["task.json"].file_size > MAX_MANIFEST_SIZE:
            raise _invalid("размер task.json превышает 1 МБ")
        try:
            manifest = json.loads(archive.read("task.json").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, RuntimeError) as error:
            raise _invalid("task.json должен содержать корректный UTF-8 JSON") from error
        if not isinstance(manifest, dict):
            raise _invalid("корень task.json должен быть объектом")
        if manifest.get("format") != "flowboard-task":
            raise _invalid("неподдерживаемый формат")
        version = manifest.get("format_version")
        if isinstance(version, bool) or not isinstance(version, int) or version != 1:
            raise _invalid("неподдерживаемая версия формата")
        task_data = manifest.get("task")
        if not isinstance(task_data, dict):
            raise _invalid("поле task должно быть объектом")

        title = _required_string(task_data.get("title"), "title", max_length=200)
        description = task_data.get("description", "")
        result = task_data.get("result", "")
        if not isinstance(description, str) or len(description) > MAX_TASK_TEXT_LENGTH:
            raise _invalid("поле task.description должно быть строкой длиной до 30000 символов")
        if not isinstance(result, str) or len(result) > MAX_TASK_TEXT_LENGTH:
            raise _invalid("поле task.result должно быть строкой длиной до 30000 символов")
        status = task_data.get("status", "todo")
        if not isinstance(status, str) or status not in STATUSES:
            raise _invalid("поле task.status содержит неизвестный статус")
        tags = task_data.get("tags", [])
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise _invalid("поле task.tags должно быть массивом строк")
        if any("," in tag for tag in tags):
            raise _invalid("значения task.tags не должны содержать запятые")
        if sum(len(tag) for tag in tags) > 1000:
            raise _invalid("суммарная длина task.tags превышает 1000 символов")
        ordinary_tags, legacy_types = split_legacy_tags(", ".join(tag.strip() for tag in tags))
        task_type_value = task_data.get("task_type", "")
        if not isinstance(task_type_value, str):
            raise _invalid("поле task.task_type должно быть строкой")
        task_type = normalize_task_type(task_type_value) or (
            legacy_types[0] if legacy_types else ""
        )
        if task_type_value and (not task_type or task_type_value.strip() != task_type):
            raise _invalid("поле task.task_type содержит неизвестный тип")

        def read_timestamp(source: dict[str, Any], field: str) -> str | None:
            value = source.get(field)
            if value is None:
                return None
            normalized = normalize_timestamp(value)
            if normalized is None:
                raise _invalid(f"поле {field} должно быть датой ISO 8601 или null")
            return normalized

        closed_at = read_timestamp(task_data, "closed_at")
        if status == "done" and closed_at is None:
            from app.importer import utc_now

            closed_at = utc_now()
        if status != "done":
            closed_at = None

        attachments_data = manifest.get("attachments", [])
        if not isinstance(attachments_data, list):
            raise _invalid("поле attachments должно быть массивом")
        declared_paths: set[str] = set()
        imported_attachments: list[ImportedAttachment] = []
        expected_names = {"task.json"}
        for item in attachments_data:
            if not isinstance(item, dict):
                raise _invalid("каждое вложение должно быть объектом")
            path_value = item.get("path")
            filename = _required_string(
                item.get("filename"), "attachments.filename", max_length=255
            )
            if not isinstance(path_value, str):
                raise _invalid("путь вложения должен быть строкой")
            path = PurePosixPath(path_value)
            if (
                path.is_absolute()
                or ".." in path.parts
                or len(path.parts) < 2
                or path.parts[0] != "attachments"
            ):
                raise _invalid("путь вложения выходит за пределы attachments/")
            if path_value in declared_paths:
                raise _invalid("манифест содержит повторяющийся путь вложения")
            declared_paths.add(path_value)
            expected_names.add(path_value)
            size = item.get("size")
            if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                raise _invalid("размер вложения должен быть неотрицательным целым числом")
            if size > settings.max_file_size_bytes:
                raise _invalid(f"вложение «{filename}» превышает лимит размера файла")
            if info_by_name[path_value].file_size != size:
                raise _invalid(f"размер вложения «{filename}» не совпадает с манифестом")
            try:
                content = archive.read(path_value)
            except (
                KeyError,
                RuntimeError,
                EOFError,
                NotImplementedError,
                zlib.error,
                zipfile.BadZipFile,
            ) as error:
                raise _invalid(f"файл вложения «{filename}» отсутствует или повреждён") from error
            if len(content) != size:
                raise _invalid(f"размер вложения «{filename}» не совпадает с манифестом")
            imported_attachments.append(
                ImportedAttachment(
                    filename=filename,
                    content=content,
                    created_at=read_timestamp(item, "created_at"),
                )
            )
        if set(names) != expected_names:
            raise _invalid("состав ZIP не совпадает со списком вложений в манифесте")

    return ParsedTaskArchive(
        task=ParsedTask(
            title=title,
            description=description,
            result=result,
            status=status,
            tags=", ".join(ordinary_tags),
            task_type=task_type,
            created_at=read_timestamp(task_data, "created_at"),
            updated_at=read_timestamp(task_data, "updated_at"),
            closed_at=closed_at,
        ),
        attachments=tuple(imported_attachments),
    )
