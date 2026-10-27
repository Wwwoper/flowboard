from __future__ import annotations

import re


def test_quick_add_uses_russian_labels_and_preserves_technical_type_values(client):
    html = client.get("/").text
    expected = {
        "bug": ("Ошибка", "Ошибка — технический тег bug"),
        "feature": ("Функция", "Функция — технический тег feature"),
        "docs": ("Документация", "Документация — технический тег docs"),
        "refactor": ("Рефакторинг", "Рефакторинг — технический тег refactor"),
    }

    for technical_value, (label, title) in expected.items():
        match = re.search(
            rf'<button[^>]*data-task-type="{technical_value}"[^>]*title="([^"]+)"[^>]*>([^<]+)</button>',
            html,
        )
        assert match is not None
        assert match.group(1) == title
        assert match.group(2) == label


def test_task_type_labels_are_shared_across_cards_editor_filters_and_archive(client):
    script = client.get("/static/app.js").text
    expected = {
        "bug": "Ошибка",
        "feature": "Функция",
        "docs": "Документация",
        "refactor": "Рефакторинг",
    }

    for technical_value, label in expected.items():
        assert f'{technical_value}: "{label}"' in script
    assert "TASK_TYPE_LABELS[taskType.toLowerCase()]" in script
    create_task = script.split("async function createTask(", 1)[1].split("async function undoCreation(", 1)[0]
    assert "taskType," in create_task
    assert "Object.keys(TASK_TYPE_LABELS).forEach(addChoice);" in script
    assert 'const order = ["bug", "feature", "docs", "refactor"];' in script
