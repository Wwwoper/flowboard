"""Shared task type definitions and legacy tag conversion."""

from __future__ import annotations


TASK_TYPE_ALIASES = {
    "bug": "bug",
    "ошибка": "bug",
    "feature": "feature",
    "функция": "feature",
    "docs": "docs",
    "документация": "docs",
    "refactor": "refactor",
    "рефакторинг": "refactor",
}


def normalize_task_type(value: object) -> str:
    normalized = str(value or "").strip().casefold().replace("ё", "е")
    return TASK_TYPE_ALIASES.get(normalized, "")


def split_legacy_tags(value: object) -> tuple[list[str], list[str]]:
    """Return ordinary tags and recognized legacy type tags, preserving order."""
    tags: list[str] = []
    legacy_types: list[str] = []
    for raw_tag in str(value or "").split(","):
        tag = raw_tag.strip()
        if not tag:
            continue
        task_type = normalize_task_type(tag)
        if task_type:
            if task_type not in legacy_types:
                legacy_types.append(task_type)
            continue
        tags.append(tag)
    return tags, legacy_types


def validate_custom_tags(value: object) -> str:
    """Reject tags that collide with a built-in type name in either language."""
    tags = str(value or "")
    for tag in tags.split(","):
        if normalize_task_type(tag):
            raise ValueError(
                "Название тега зарезервировано для "
                "типа задачи"
            )
    return tags
