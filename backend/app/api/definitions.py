"""`POST /api/v1/admin/definitions/import` — minimal public import surface for Service
Definitions (SPEC.md §6 "make seed создает Definitions через тот же публичный API
конструктора, а не прямыми INSERT"; docs/IMPLEMENTATION_PLAN.md §10 "Definitions
загружаются через общий import/service API").

This is intentionally NOT the full registry/constructor (Этап 4 — reorder, duplicate,
version+1 publish, live preview, session undo/redo): that is later work. It is the
smallest endpoint that lets `app/seed` — and, later, a JSON-import feature in the
constructor — create Definitions through the same Pydantic validation path the runtime
enforces (`app.schemas.definition.ServiceDefinition`), instead of writing JSONB rows
directly into `service_definitions`.

Idempotent by `slug`: importing an already-present slug is a no-op that returns the
existing row (`created: false`) rather than adding a duplicate — `make seed` must be
safely re-runnable.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.api.errors import ApiError
from app.db import get_session
from app.models import ServiceDefinition, ServiceStatus, UserRole
from app.schemas.definition import ServiceDefinition as ServiceDefinitionSchema

router = APIRouter(tags=["definitions"])


class ImportDefinitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    org_id: uuid.UUID
    slug: str
    status: ServiceStatus = ServiceStatus.PUBLISHED
    definition: dict


class ImportDefinitionOut(BaseModel):
    id: uuid.UUID
    service_id: uuid.UUID
    slug: str
    version: int
    status: ServiceStatus
    created: bool


@router.post("/admin/definitions/import", response_model=ImportDefinitionOut)
async def import_definition(
    payload: ImportDefinitionRequest,
    admin_user_id: uuid.UUID = Depends(require_role(UserRole.ADMIN, UserRole.AUTHOR)),
    session: AsyncSession = Depends(get_session),
) -> ImportDefinitionOut:
    try:
        ServiceDefinitionSchema.model_validate(payload.definition)
    except ValidationError as exc:
        # `include_context=False`: pydantic's default `errors()` embeds the raw
        # exception object raised inside `@model_validator` (e.g. the `ValueError` from
        # `ServiceDefinitionSchema.references`) in `ctx.error`, which `JSONResponse`
        # cannot serialize and would otherwise turn this 422 into an unhandled 500.
        raise ApiError(
            422,
            "invalid_definition",
            "Service Definition failed schema validation",
            {"errors": exc.errors(include_context=False, include_url=False)},
        ) from exc

    existing = await session.scalar(select(ServiceDefinition).where(ServiceDefinition.slug == payload.slug))
    if existing is not None:
        return ImportDefinitionOut(
            id=existing.id,
            service_id=existing.service_id,
            slug=existing.slug,
            version=existing.version,
            status=existing.status,
            created=False,
        )

    row = ServiceDefinition(
        org_id=payload.org_id,
        slug=payload.slug,
        status=payload.status,
        version=1,
        definition=payload.definition,
        created_by=admin_user_id,
        published_at=datetime.now(timezone.utc) if payload.status == ServiceStatus.PUBLISHED else None,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return ImportDefinitionOut(
        id=row.id, service_id=row.service_id, slug=row.slug, version=row.version, status=row.status, created=True
    )
