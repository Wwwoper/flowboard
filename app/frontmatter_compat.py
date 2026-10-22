"""Thin adapter for python-frontmatter, with a small offline-safe fallback.

Production installations use python-frontmatter. The fallback keeps local tests usable in
restricted build environments where that wheel cannot be installed; it relies on PyYAML,
which is also a dependency of python-frontmatter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

try:  # pragma: no cover - exercised in ordinary installs with python-frontmatter available
    import frontmatter as _frontmatter
except ImportError:  # pragma: no branch - build image may be deliberately offline
    import yaml

    FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)

    @dataclass
    class Post:
        content: str
        metadata: dict[str, Any]

        def __init__(self, content: str, **metadata: Any) -> None:
            self.content = content
            self.metadata = metadata

    def loads(text: str) -> Post:
        match = FRONTMATTER_RE.match(text)
        if not match:
            return Post(text)
        metadata = yaml.safe_load(match.group(1)) or {}
        if not isinstance(metadata, dict):
            raise ValueError("Frontmatter должен содержать YAML-объект")
        return Post(text[match.end() :], **metadata)

    def dumps(post: Post) -> str:
        header = yaml.safe_dump(
            post.metadata, allow_unicode=True, sort_keys=False, default_flow_style=False
        ).rstrip()
        return f"---\n{header}\n---\n{post.content}"
else:
    Post = _frontmatter.Post
    loads = _frontmatter.loads
    dumps = _frontmatter.dumps
