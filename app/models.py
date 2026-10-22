"""Pydantic request and response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TaskStatus = Literal["todo", "doing", "waiting", "done"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskCreate(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    tags: str = Field(default="", max_length=1000)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Заголовок не может быть пустым")
        return value


class TaskPatch(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus | None = None
    position: float | None = None
    tags: str | None = Field(default=None, max_length=1000)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("Заголовок не может быть пустым")
        return value


class AttachmentRead(BaseModel):
    id: int
    task_id: int
    filename: str
    size: int
    created_at: str


class TaskSummary(BaseModel):
    id: int
    title: str
    description: str
    status: TaskStatus
    position: float
    tags: str
    created_at: str
    updated_at: str
    closed_at: str | None
    attachments_count: int = 0


class TaskDetail(TaskSummary):
    description_html: str
    attachments: list[AttachmentRead]


class ImportSkipped(BaseModel):
    filename: str
    reason: str
    line: int | None = None


class ImportResult(BaseModel):
    created: int
    skipped: list[ImportSkipped]


class MarkdownPreviewRequest(StrictModel):
    text: str = Field(default="", max_length=5000)
