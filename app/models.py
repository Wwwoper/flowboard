"""Pydantic request and response models."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TaskStatus = Literal["todo", "doing", "waiting", "done"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskCreate(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    result: str = Field(default="", max_length=5000)
    tags: str = Field(default="", max_length=1000)
    workset_id: int | None = Field(default=None, gt=0)

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
    result: str | None = Field(default=None, max_length=5000)
    status: TaskStatus | None = None
    position: float | None = None
    tags: str | None = Field(default=None, max_length=1000)
    workset_id: int | None = Field(default=None, gt=0)

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


class TaskSettingsRead(BaseModel):
    require_result_to_close: bool


class TaskSettingsPatch(StrictModel):
    require_result_to_close: bool | None = None


class ArchiveSettingsRead(BaseModel):
    archive_enabled: bool
    archive_after_days: Literal[7, 30, 60, 90]


class ArchiveSettingsPatch(StrictModel):
    archive_enabled: bool | None = None
    archive_after_days: Literal[7, 30, 60, 90] | None = None


class TaskSummary(BaseModel):
    id: int
    title: str
    description: str
    result: str = ""
    status: TaskStatus
    position: float
    tags: str
    created_at: str
    updated_at: str
    closed_at: str | None
    archived_at: str | None = None
    attachments_count: int = 0
    workset_id: int | None = None


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


class WorksetCreate(StrictModel):
    project_slug: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=100)

    @field_validator("project_slug")
    @classmethod
    def validate_project_slug(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
            raise ValueError("Некорректный ключ проекта")
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Название рабочего набора не может быть пустым")
        return value


class WorksetPatch(StrictModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Название рабочего набора не может быть пустым")
        return value


class WorksetTaskAdd(StrictModel):
    task_id: int = Field(gt=0)


class WorksetRead(BaseModel):
    id: int
    project_slug: str
    name: str
    status: Literal["active", "completed"]
    created_at: str
    updated_at: str
    completed_at: str | None
    task_count: int
    done_count: int


class WorksetEventRead(BaseModel):
    id: int
    workset_id: int | None
    project_slug: str
    workset_name: str
    task_id: int | None
    task_title: str
    task_status: TaskStatus | None = None
    task_closed_at: str | None = None
    task_count: int | None = None
    done_count: int | None = None
    task_exists: bool = False
    event_type: str
    created_at: str


class WorksetHistoryTaskRead(BaseModel):
    task_id: int
    task_title: str
    status: TaskStatus | None = None
    closed_at: str | None = None
    added_at: str
    removed_at: str | None = None
    removal_reason: Literal["removed", "deleted"] | None = None
    exists: bool


class WorksetHistoryItemRead(BaseModel):
    id: int
    project_slug: str
    name: str
    status: Literal["active", "completed", "deleted"]
    created_at: str | None = None
    completed_at: str | None = None
    duration_seconds: int | None = None
    task_count: int
    done_count: int
    added_count: int
    removed_count: int
    deleted_count: int
    members: list[WorksetHistoryTaskRead]
    removed_tasks: list[WorksetHistoryTaskRead]
    deleted_tasks: list[WorksetHistoryTaskRead]


class WorksetHistoryRead(BaseModel):
    worksets: list[WorksetHistoryItemRead]
    events: list[WorksetEventRead]
    has_more: bool
    next_offset: int | None = None
