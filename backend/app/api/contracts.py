"""Pydantic request/response models for the v1 API (kept separate from
`app/schemas/definition.py`, which is the Service Definition DSL, not the HTTP contract)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

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
    # SPEC.md §4.3 "Многоэтапность" (docs/IMPLEMENTATION_PLAN.md §7): stage keys already
    # submitted, and whether the stage `checkpoint` currently points at is still open for
    # editing — see app/api/applications._stage_open. Appended, not replacing anything.
    completed_stages: list[str] = Field(default_factory=list)
    stage_open: bool = True


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


# ---------------------------------------------------------------------------
# Constructor / registry API (SPEC.md §5.1/§5.2; docs/IMPLEMENTATION_PLAN.md §9
# "Registry/constructor"). Served by `app/api/admin_definitions.py`.
# ---------------------------------------------------------------------------


class DefinitionListItem(BaseModel):
    id: uuid.UUID
    service_id: uuid.UUID
    slug: str
    status: str
    version: int
    title: str
    updated_at: datetime


class DefinitionListOut(BaseModel):
    items: list[DefinitionListItem]


class DefinitionDetailOut(BaseModel):
    id: uuid.UUID
    service_id: uuid.UUID
    org_id: uuid.UUID
    slug: str
    status: str
    version: int
    definition: dict
    created_by: uuid.UUID | None
    published_at: datetime | None
    updated_at: datetime


class CreateDefinitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # `org_id` is required even though SPEC.md's endpoint sketch only lists
    # `{slug, definition}`: `service_definitions.org_id` is a NOT NULL FK
    # (`app/models/service_definition.py`) with no default, so the caller must supply
    # it — same requirement the existing `/admin/definitions/import` endpoint already
    # has (`app/api/definitions.py`).
    org_id: uuid.UUID
    slug: str
    definition: dict


class UpdateDefinitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: dict


class PublishDefinitionOut(BaseModel):
    id: uuid.UUID
    service_id: uuid.UUID
    slug: str
    status: str
    version: int
    published_at: datetime | None
    # See `app/api/admin_definitions.py` module docstring: the draft row that was
    # published is deleted as part of the same transaction, not kept around.
    draft_deleted: bool = True


class DuplicateDefinitionOut(BaseModel):
    id: uuid.UUID
    service_id: uuid.UUID
    slug: str
    status: str
    version: int


# ---------------------------------------------------------------------------
# AI layer (SPEC.md §7.1 "Подбор меры", §7.2 "Генератор услуги из документа", §7.3).
# Served by `app/api/admin_definitions.py` (generate) and `app/api/intake.py` (match).
# ---------------------------------------------------------------------------


class GenerateDefinitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    # See `CreateDefinitionRequest.org_id` docstring — same NOT NULL FK constraint.
    org_id: uuid.UUID
    # Optional: derived from the generated `meta.title` (transliterated, deduplicated)
    # when omitted, so a plain `{text, org_id}` request still works end to end.
    slug: str | None = None


class GenerateDefinitionOut(BaseModel):
    id: uuid.UUID
    warnings: list[str]
    degraded: bool


class IntakeMatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str


class IntakeMatchItem(BaseModel):
    slug: str
    title: str
    why: str


class IntakeMatchOut(BaseModel):
    items: list[IntakeMatchItem]
    method: str  # "llm" | "keyword"
    degraded: bool


# ---------------------------------------------------------------------------
# Content: карта проектов / аналитика / инструменты и материалы (SPEC.md §4.5-4.7).
# Served by `app/api/content.py`. Public read-only — no auth.
# ---------------------------------------------------------------------------


class MapProjectOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    organization: str  # Organization.short_name
    name: str
    region_code: str
    locality: str | None
    lat: Decimal
    lng: Decimal
    industry: str | None
    amount: Decimal | None
    period_start: date | None
    period_end: date | None
    status: str
    description: str | None
    is_demo: bool


class MapProjectListOut(BaseModel):
    items: list[MapProjectOut]


class MapRegionSummary(BaseModel):
    region_code: str
    count: int
    amount: Decimal


class MapSummaryOut(BaseModel):
    total_count: int
    total_amount: Decimal
    by_region: list[MapRegionSummary]


class AnalyticsMaterialOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    organization: str  # Organization.short_name
    type: str
    title: str
    description: str | None
    source: str | None
    period: str | None
    url: str | None
    embed_allowed: bool


class AnalyticsMaterialListOut(BaseModel):
    items: list[AnalyticsMaterialOut]


class KnowledgeItemOut(BaseModel):
    id: uuid.UUID
    category: str
    title: str
    description: str | None
    content: str | None
    url: str | None


class KnowledgeItemListOut(BaseModel):
    items: list[KnowledgeItemOut]
