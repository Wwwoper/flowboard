"""Safe Markdown rendering for the task detail panel."""

from __future__ import annotations

import re

import bleach
from markdown_it import MarkdownIt
from markdown_it.token import Token

MARKDOWN = MarkdownIt("default", {"html": False, "linkify": False, "typographer": False})
ALLOWED_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "input",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "ul",
}
ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "rel"],
    "input": ["type", "checked", "data-task-checkbox", "aria-label"],
}


def _render_task_list_checkboxes(state) -> None:
    """Convert Markdown task markers inside list items to controlled checkbox HTML."""
    list_item_depth = 0
    for token in state.tokens:
        if token.type == "list_item_open":
            list_item_depth += 1
            continue
        if token.type == "list_item_close":
            list_item_depth = max(0, list_item_depth - 1)
            continue
        if token.type != "inline" or not list_item_depth or not token.children:
            continue

        match = re.match(r"^\[([ xX])\](?:[ \t]+|$)", token.content)
        if not match:
            continue

        line_number = token.map[0] if token.map else 0
        checked = match.group(1).lower() == "x"
        label = "Снять отметку" if checked else "Отметить пункт списка"
        checkbox = Token("html_inline", "", 0)
        checkbox.content = (
            f'<input type="checkbox" data-task-checkbox="{line_number}" '
            f'aria-label="{label}"{" checked" if checked else ""}> '
        )
        children: list[Token] = []
        state.md.inline.parse(token.content[match.end() :], state.md, state.env, children)
        token.content = token.content[match.end() :]
        token.children = [checkbox, *children]


MARKDOWN.core.ruler.after("inline", "task-list-checkboxes", _render_task_list_checkboxes)


def render_safe_markdown(source: str) -> str:
    """Render Markdown with raw HTML disabled and sanitize the result as defense in depth."""
    rendered = MARKDOWN.render(source or "")
    return bleach.clean(
        rendered,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols={"http", "https", "mailto"},
        strip=True,
    )
