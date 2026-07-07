"""`POST /api/v1/admin/applications/{id}/status` (SPEC.md §8 bpm_submit/bpm_status,
§5.4 "смена статуса (имитация решения BPM)").

This is the admin-side half of the mock BPM integration: it never lets an application
jump to an arbitrary status, it only accepts a transition the Service Definition's
`transitions` explicitly allow from the current status — the same
`app.engine.runtime.transition` guard `app/api/applications.py`'s `submit` endpoint
uses, reached here through `app.integrations.bpm.MockBpmAdapter.change_status`
(SPEC.md §8 "один интерфейс шины, разные системы за ней").
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.api.errors import ApiError
from app.db import get_session
from app.integrations.bpm import MockBpmAdapter
from app.models import Application, AuditLog
from app.models import ServiceDefinition as ServiceDefinitionModel
from app.models import UserRole
from app.schemas.definition import ServiceDefinition as ServiceDefinitionSchema

router = APIRouter(tags=["admin"])

_bpm = MockBpmAdapter()


class AdminStatusChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str
    comment: str | None = None


class AdminStatusChangeOut(BaseModel):
    id: uuid.UUID
    status: str
    timeline: list
    mock: bool = True
    disclaimer: str = "Статус изменён имитацией внутренней BPM дочерней организации, а не реальным BPM."


async def _load_definition(
    session: AsyncSession, service_id: uuid.UUID, version: int
) -> ServiceDefinitionModel:
    stmt = select(ServiceDefinitionModel).where(
        ServiceDefinitionModel.service_id == service_id,
        ServiceDefinitionModel.version == version,
    )
    row = await session.scalar(stmt)
    if row is None:  # pragma: no cover - guarded by the composite FK, defensive only
        raise ApiError(500, "definition_missing", "Referenced service definition version is missing", {})
    return row


@router.post("/admin/applications/{application_id}/status", response_model=AdminStatusChangeOut)
async def change_application_status(
    application_id: uuid.UUID,
    payload: AdminStatusChangeRequest,
    admin_user_id: uuid.UUID = Depends(require_role(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> AdminStatusChangeOut:
    application = await session.get(Application, application_id)
    if application is None:
        raise ApiError(404, "not_found", "Application not found", {})

    definition_row = await _load_definition(session, application.service_id, application.service_version)
    definition = ServiceDefinitionSchema.model_validate(definition_row.definition)

    try:
        result = await _bpm.change_status(definition, application.status, payload.target, application.data)
    except ValueError as exc:
        raise ApiError(
            422,
            "invalid_transition",
            "Service definition does not allow this status transition",
            {"from": application.status, "to": payload.target},
        ) from exc

    before_status = application.status
    application.status = result.status
    application.timeline = [
        *application.timeline,
        {
            "status": result.status,
            "at": datetime.now(timezone.utc).isoformat(),
            "event": "admin_status_change",
            "comment": payload.comment,
        },
    ]
    session.add(
        AuditLog(
            user_id=admin_user_id,
            action="application_status_change",
            entity_type="application",
            entity_id=application.id,
            before={"status": before_status},
            after={"status": result.status},
        )
    )
    await session.commit()
    await session.refresh(application)
    return AdminStatusChangeOut(id=application.id, status=application.status, timeline=application.timeline)
