from __future__ import annotations

import json
import shutil
import subprocess

import pytest


def test_task_card_information_order_and_optional_sections(client):
    script = client.get("/static/app.js").text
    assert "function makeTaskCard(task)" in script
    card_builder = script.split("function makeTaskCard(task)", 1)[1].split(
        "function columnTagLabel(tag)", 1
    )[0]

    markers = (
        'top.appendChild(make("div", "task-card-title", task.title));',
        'const excerpt = taskDescriptionExcerpt(task.description, task.title);',
        'if (excerpt) card.appendChild(make("p", "task-card-excerpt", excerpt));',
        "if ((project && project !== state.project) || typeTag) {",
        "if (hiddenTags.length) {",
        'const footer = make("div", "task-card-footer");',
    )
    positions = [card_builder.index(marker) for marker in markers]
    assert positions == sorted(positions)

    # Missing projects and types must not leave a blank metadata row or placeholder chip.
    assert 'project ? projectLabel(project) : "Без проекта"' not in card_builder
    assert "if ((project && project !== state.project) || typeTag) {" in card_builder
    assert "if (project && project !== state.project) {" in card_builder

    # The metrics wrapper is created only when at least one attachment exists.
    attachment_branch = card_builder.split("if (task.attachments_count) {", 1)[1].split(
        "\n    }", 1
    )[0]
    assert 'const metrics = make("span", "task-card-metrics");' in attachment_branch
    assert 'updated.title = `Последнее изменение: ${updatedDateTime}`;' in card_builder
    assert 'updated.setAttribute("aria-label", `Последнее изменение: ${updatedDateTime}`);' in card_builder
    assert 'make("span", "attachment-mini-icon", "📎")' in card_builder
    assert 'attachment.setAttribute("aria-label", `${task.attachments_count} ${pluralAttachments(task.attachments_count)}`);' in card_builder
    assert 'const attachment = make("span", "attachment-mini");' in card_builder
    assert 'attachment.setAttribute("role", "img");' in card_builder
    date_position = card_builder.index('footer.appendChild(updated);')
    attachment_position = card_builder.index("if (task.attachments_count) {")
    assert date_position < attachment_position
    assert "task.description =" not in card_builder


def test_task_card_excerpt_and_long_labels_remain_compact_and_wrappable(client):
    script = client.get("/static/app.js").text
    assert 'function taskDescriptionExcerpt(description, title = "", limit = 112)' in script

    css = client.get("/static/style.css").text
    assert "-webkit-line-clamp: 2" in css
    assert "overflow-wrap: anywhere" in css
    assert ".task-project-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }" in css


def test_task_description_excerpt_preserves_text_and_removes_only_confirmed_duplicate(client):
    if not shutil.which("node"):
        pytest.skip("Node.js is required to exercise the frontend excerpt function")

    script = client.get("/static/app.js").text
    function = script.split("function taskDescriptionExcerpt(", 1)[1].split(
        "function projectAccent(", 1
    )[0]
    cases = [
        ("Задача: Исправить авторизацию\nПроверить токен.", "Исправить авторизацию", 112),
        ("Задача: проверить авторизацию\nОстальное.", "Исправить авторизацию", 112),
        ("Обычная фраза: Задача: проверить авторизацию", "Исправить авторизацию", 112),
        ("C# и snake_case, #важно", "", 112),
        ("```python\nprint('hello')\n```", "", 112),
        ("- Первый пункт\n- Второй пункт", "", 112),
        ("[Ссылка](https://example.com)", "", 112),
        ("**Выделенный** и `код`", "", 112),
        ("   ", "", 112),
        ("x" * 150, "", 112),
    ]
    payload = json.dumps(cases, ensure_ascii=False)
    node_script = (
        "function taskDescriptionExcerpt("
        + function
        + "\nconst cases = "
        + payload
        + ";\nconsole.log(JSON.stringify(cases.map(([description, title, limit]) => "
        + "taskDescriptionExcerpt(description, title, limit))));"
    )
    result = subprocess.run(
        ["node", "-e", node_script], check=True, capture_output=True, text=True
    )
    excerpts = json.loads(result.stdout)
    assert excerpts[0] == "Проверить токен."
    assert excerpts[1] == "Задача: проверить авторизацию Остальное."
    assert excerpts[2] == "Обычная фраза: Задача: проверить авторизацию"
    assert excerpts[3] == "C# и snake_case, #важно"
    assert excerpts[4] == "print('hello')"
    assert excerpts[5] == "Первый пункт Второй пункт"
    assert excerpts[6] == "Ссылка"
    assert excerpts[7] == "Выделенный и код"
    assert excerpts[8] == ""
    assert len(excerpts[9]) == 112 and excerpts[9].endswith("…")


def test_attachment_count_accessible_pluralization(client):
    if not shutil.which("node"):
        pytest.skip("Node.js is required to exercise the frontend pluralization function")

    script = client.get("/static/app.js").text
    function = script.split("function pluralAttachments(", 1)[1].split(
        "function pluralTasks(", 1
    )[0]
    node_script = (
        "function pluralAttachments("
        + function
        + "\nconsole.log(JSON.stringify([1, 2, 4, 5, 11, 21, 24, 25].map("
        + "(count) => `${count} ${pluralAttachments(count)}`)));"
    )
    result = subprocess.run(
        ["node", "-e", node_script], check=True, capture_output=True, text=True
    )
    assert json.loads(result.stdout) == [
        "1 вложение",
        "2 вложения",
        "4 вложения",
        "5 вложений",
        "11 вложений",
        "21 вложение",
        "24 вложения",
        "25 вложений",
    ]
