import hashlib
from pathlib import Path

from app.ai_guidelines import AI_TASK_GUIDELINES_RESOURCE, read_ai_task_guidelines

EXPECTED_GUIDELINES_SHA256 = "8206cbc5264c0ae47db4d8034d8b13e6b920d20d883993c2f61ffb84cbb2c91b"


def test_ai_task_guidelines_are_available_independently_of_working_directory(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    guidelines = read_ai_task_guidelines()

    assert guidelines.startswith(
        "# Регламент формирования групп задач для Flowboard\n"
    )
    assert "**Версия:** 1.0" in guidelines
    assert "kanban_export: true" in guidelines
    assert "<!-- kanban-task-start -->" in guidelines
    assert "<!-- kanban-task-end -->" in guidelines
    assert hashlib.sha256(guidelines.encode("utf-8")).hexdigest() == EXPECTED_GUIDELINES_SHA256


def test_guidelines_are_included_in_the_docker_build_context():
    repository_root = Path(__file__).parents[1]
    resource_path = repository_root / "app" / AI_TASK_GUIDELINES_RESOURCE
    dockerfile = (repository_root / "Dockerfile").read_text(encoding="utf-8")

    assert resource_path.is_file()
    assert "COPY app ./app" in dockerfile
    assert "chmod -R a-w /app/app/resources" in dockerfile
