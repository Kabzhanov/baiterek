"""Pydantic request/response models for the v1 API (kept separate from
`app/schemas/definition.py`, which is the Service Definition DSL, not the HTTP contract)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ServiceSummary(BaseModel):
    id: uuid.UUID
    slug: str
    meta: dict


class CreateApplicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_id: uuid.UUID


class ApplicationOut(BaseModel):
    id: uuid.UUID
    service_id: uuid.UUID
    service_version: int
    status: str
    revision: int
    number: str | None
    checkpoint: dict
    data: dict


class PatchDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_delta: dict = Field(default_factory=dict)
    checkpoint: dict | None = None
    expected_revision: int


class DraftPatchOut(BaseModel):
    id: uuid.UUID
    revision: int
    checkpoint: dict
    screen: dict


class ResumeOut(BaseModel):
    id: uuid.UUID
    service_id: uuid.UUID
    service_version: int
    status: str
    revision: int
    data: dict
    checkpoint: dict
    definition: dict
    screen: dict


class SubmitOut(BaseModel):
    id: uuid.UUID
    number: str
    status: str
    timeline: list


class CabinetServiceInfo(BaseModel):
    slug: str
    title: str


class CabinetApplicationItem(BaseModel):
    id: uuid.UUID
    number: str | None
    status: str
    service: CabinetServiceInfo
    service_version: int
    checkpoint: dict
    # Заполненные видимые поля / все видимые поля, 0-100 (SPEC "Обязательное расширение" §2:
    # «Заявка … заполнена на 60% — Продолжить»). Считается движком правил, см. cabinet.py.
    progress_percent: int
    # meta.labels_plain из Definition — человеческие подписи статусов для бейджей в ЛК.
    labels_plain: dict[str, str]
    updated_at: datetime


class CabinetNotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str
    created_at: datetime
    read_at: datetime | None


class CabinetApplicationDetail(CabinetApplicationItem):
    created_at: datetime
    timeline: list
    # Файловый контур ещё не реализован (IMPLEMENTATION_PLAN §8) — пока всегда пустой список,
    # но поле уже в контракте, чтобы фронту не пришлось менять форму ответа позже.
    documents: list
    notifications: list[CabinetNotificationOut]


class CabinetListOut(BaseModel):
    items: list[CabinetApplicationItem]
