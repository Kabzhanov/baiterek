"""Pydantic request/response models for the v1 API (kept separate from
`app/schemas/definition.py`, which is the Service Definition DSL, not the HTTP contract)."""
from __future__ import annotations

import uuid

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
