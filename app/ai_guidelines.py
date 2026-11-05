"""Access to the immutable AI task-authoring guidelines shipped with Flowboard."""

from importlib.resources import files


AI_TASK_GUIDELINES_RESOURCE = "resources/ai-task-guidelines.md"
AI_TASK_GUIDELINES_BASE_VERSION = "1.0"
AI_TASK_GUIDELINES_OVERRIDE_KEY = "ai_task_guidelines_override"


def read_ai_task_guidelines() -> str:
    """Return the bundled task-authoring guidelines, independent of the CWD."""
    return files("app").joinpath(*AI_TASK_GUIDELINES_RESOURCE.split("/")).read_text(
        encoding="utf-8"
    )
