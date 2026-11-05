from __future__ import annotations

from pathlib import Path


def test_create_project_uses_themed_dialog_with_inline_validation_and_no_browser_prompt(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    for fragment in (
        'id="create-project-dialog"',
        'id="create-project-form"',
        'id="create-project-key"',
        'id="create-project-help"',
        'id="create-project-error"',
        'id="cancel-create-project"',
        'id="submit-create-project"',
        'class="app-modal create-project-dialog"',
        'value="__create_project__">＋ Создать проект…</option>',
        'Используйте латинские буквы, цифры и дефис. Например: storefront.',
    ):
        assert fragment in html
    assert "/static/themed-controls.css?v=0.1.16" in html
    assert "/static/app.js?v=0.5.62" in html

    script = client.get("/static/app.js").text
    assert "window.prompt(" not in script
    assert "function openCreateProjectDialog()" in script
    assert "if (els.projectFilter.value === CREATE_PROJECT_OPTION)" in script
    assert (
        'els.projectFilter.closest(".theme-select")?.querySelector(".theme-select-trigger")?.focus'
        in script
    )
    assert "async function createProjectFromDialog(event)" in script
    assert "if (createProjectBusy) return;" in script
    assert "Проект с таким ключом уже существует." in script
    assert "Введите ключ проекта." in script
    assert "Не удалось создать проект. Проверьте введённые данные и попробуйте ещё раз." in script
    assert 'if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug))' in script
    assert 'if (createProjectBusy) event.preventDefault();' in script
    assert "if (createProjectDialog.open) return;" in script

    controls = client.get("/static/themed-controls.css").text
    for selector in (
        ".app-modal",
        ".app-modal::backdrop",
        ".create-project-dialog",
        ".create-project-form",
        ".create-project-error[hidden]",
        ".create-project-actions",
    ):
        assert selector in controls


def test_column_add_controls_are_hidden_without_removing_the_existing_flow(client):
    html = client.get("/").text
    script = (Path(__file__).parents[1] / "app/static/app.js").read_text()
    assert html.count('class="column-add" hidden data-add-status=') == 3
    assert '$$("[data-add-status]").forEach' in script
    assert 'button.dataset.addStatus' in script


def test_project_creation_message_points_to_project_settings(client):
    script = (Path(__file__).parents[1] / "app/static/app.js").read_text()
    assert "Проект «${projectLabel(slug)}» создан." in script
    assert "Управление проектами" in script
    assert "Переименовать проект" in script
