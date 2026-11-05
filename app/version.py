"""Application version and source revision information."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_METADATA = tomllib.loads(
    (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
)
APP_VERSION = PROJECT_METADATA["project"]["version"]


def _get_build_id() -> str:
    """Return the checked-out Git revision, or a clear fallback outside Git."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        return "local"
    return result.stdout.strip() or "local"


BUILD_ID = _get_build_id()
