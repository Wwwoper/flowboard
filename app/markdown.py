"""Safe Markdown rendering for the task detail panel."""

from __future__ import annotations

import bleach
from markdown_it import MarkdownIt

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
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "ul",
}
ALLOWED_ATTRIBUTES = {"a": ["href", "title", "rel"]}


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
