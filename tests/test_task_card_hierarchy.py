from __future__ import annotations


def test_task_card_information_order_and_optional_sections(client):
    script = client.get("/static/app.js").text
    assert "function makeTaskCard(task)" in script
    card_builder = script.split("function makeTaskCard(task)", 1)[1].split(
        "function columnTagLabel(tag)", 1
    )[0]

    markers = (
        'top.appendChild(make("div", "task-card-title", task.title));',
        'const excerpt = taskDescriptionExcerpt(task.description);',
        'if (excerpt) card.appendChild(make("p", "task-card-excerpt", excerpt));',
        "if (project || typeTag) {",
        "if (hiddenTags.length) {",
        'const footer = make("div", "task-card-footer");',
    )
    positions = [card_builder.index(marker) for marker in markers]
    assert positions == sorted(positions)

    # Missing projects and types must not leave a blank metadata row or placeholder chip.
    assert 'project ? projectLabel(project) : "Без проекта"' not in card_builder
    assert "if (project || typeTag) {" in card_builder

    # The metrics wrapper is created only when at least one attachment exists.
    attachment_branch = card_builder.split("if (task.attachments_count) {", 1)[1].split(
        "\n    }", 1
    )[0]
    assert 'const metrics = make("span", "task-card-metrics");' in attachment_branch
    date_position = card_builder.index('footer.appendChild(make("time", "task-updated", formatDate(task.updated_at)));')
    attachment_position = card_builder.index("if (task.attachments_count) {")
    assert date_position < attachment_position
    assert "task.description =" not in card_builder


def test_task_card_excerpt_and_long_labels_remain_compact_and_wrappable(client):
    script = client.get("/static/app.js").text
    assert "function taskDescriptionExcerpt(description, limit = 112)" in script

    css = client.get("/static/style.css").text
    assert "-webkit-line-clamp: 2" in css
    assert "overflow-wrap: anywhere" in css
    assert ".task-project-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }" in css
