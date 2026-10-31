import pytest

from app.task_types import normalize_task_type, split_legacy_tags, validate_custom_tags


def test_task_type_aliases_accept_english_codes_and_russian_labels():
    assert normalize_task_type("BUG") == "bug"
    assert normalize_task_type("ФУНКЦИЯ") == "feature"
    assert normalize_task_type("Документация") == "docs"
    assert normalize_task_type("Рефакторинг") == "refactor"
    assert normalize_task_type("custom-tag") == ""


def test_legacy_type_tags_are_removed_without_reordering_custom_tags():
    assert split_legacy_tags("backend, bug, Документация, backend, tests") == (
        ["backend", "backend", "tests"],
        ["bug", "docs"],
    )


def test_custom_tag_validation_rejects_reserved_type_names():
    for value in ("bug", "BUG", "Ошибка", "ФУНКЦИЯ", "docs", "Рефакторинг"):
        with pytest.raises(ValueError):
            validate_custom_tags(value)
    assert validate_custom_tags("backend, needs-review") == "backend, needs-review"
