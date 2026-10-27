from __future__ import annotations


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
        'aria-label="Создать проект" title="Создать проект"',
        'Используйте латинские буквы, цифры и дефис. Например: storefront.',
    ):
        assert fragment in html
    assert "/static/themed-controls.css?v=0.1.7" in html
    assert "/static/app.js?v=0.5.24" in html

    script = client.get("/static/app.js").text
    assert "window.prompt(" not in script
    assert "function openCreateProjectDialog()" in script
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
