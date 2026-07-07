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

    # SPEC.md §4.3 "Многоэтапность" / docs/IMPLEMENTATION_PLAN.md §7 "approval этапа I
    # открывает этап II": once the admin has moved the application to a non-terminal
    # status, advance `checkpoint` onto the next stage that has not been submitted yet
    # (if any) — that is what makes `_stage_open` (app/api/applications.py) true for it,
    # so the applicant can PATCH/submit it. Idempotent: once `checkpoint` already sits on
    # that next stage, `next_stage.key == current_stage_key` and this is a no-op, so a
    # multi-call admin walk (submitted -> in_review_bpm -> indicative_approved) only
    # opens the stage once. A single-stage service always has `next_stage is None` here
    # (its only stage is already in `completed_stages` from the applicant's submit), so
    # this is a no-op for it — no behavior change from before this feature.
    completed_stages = application.completed_stages or []
    next_stage = next((s for s in definition.stages if s.key not in completed_stages), None)
    current_stage_key = application.checkpoint.get("stage_key")
    has_outgoing_transition = any(t.source == result.status for t in definition.transitions)
    if next_stage is not None and next_stage.key != current_stage_key and has_outgoing_transition:
        first_step = next_stage.steps[0] if next_stage.steps else None
        first_field = first_step.fields[0] if first_step and first_step.fields else None
        application.checkpoint = {
            "stage_key": next_stage.key,
            "step_key": first_step.key if first_step else None,
            "screen_key": first_field.key if first_field else None,
        }
        application.timeline = [
            *application.timeline,
            {
                "status": result.status,
                "at": datetime.now(timezone.utc).isoformat(),
                "event": "stage_opened",
                "stage": next_stage.key,
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
