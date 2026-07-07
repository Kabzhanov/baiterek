"""POST/PATCH/GET /api/v1/applications/... (SPEC.md §5 API items 2-5,
"Обязательное расширение" §2 checkpoint-модель).

Only the `POST .../handoff` AI-intake endpoint from SPEC.md §5 is intentionally not
implemented here — it was not part of this task's endpoint list (see task write-up).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.contracts import (
    ApplicationOut,
    CreateApplicationRequest,
    DraftPatchOut,
    PatchDraftRequest,
    ResumeOut,
    SubmitOut,
)
from app.api.deps import get_current_user_id
from app.api.errors import ApiError
from app.api.screen import resolve_indices, safe_render, to_checkpoint
from app.db import get_session
from app.engine.rules import evaluate_condition
from app.engine.runtime import compute, transition, validate
from app.models import Application
from app.models import ServiceDefinition as ServiceDefinitionModel
from app.models import ServiceStatus
from app.schemas.definition import ServiceDefinition as ServiceDefinitionSchema

router = APIRouter(tags=["applications"])


def _application_out(application: Application) -> ApplicationOut:
    return ApplicationOut(
        id=application.id,
        service_id=application.service_id,
        service_version=application.service_version,
        status=application.status,
        revision=application.revision,
        number=application.number,
        checkpoint=application.checkpoint,
        data=application.data,
    )


async def _load_definition_row(
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


def _parse_definition(row: ServiceDefinitionModel) -> ServiceDefinitionSchema:
    return ServiceDefinitionSchema.model_validate(row.definition)


async def _get_owned_application(
    session: AsyncSession, application_id: uuid.UUID, user_id: uuid.UUID
) -> Application:
    application = await session.get(Application, application_id)
    # 404 (not 403) on ownership mismatch so the endpoint doesn't leak which ids exist (IDOR).
    if application is None or application.user_id != user_id:
        raise ApiError(404, "not_found", "Application not found", {})
    return application


async def _find_active_draft(
    session: AsyncSession, user_id: uuid.UUID, service_id: uuid.UUID
) -> Application | None:
    stmt = (
        select(Application)
        .where(
            Application.user_id == user_id,
            Application.service_id == service_id,
            Application.status == "draft",
        )
        .order_by(Application.created_at.desc())
        .limit(1)
    )
    return await session.scalar(stmt)


@router.post("/applications", response_model=ApplicationOut)
async def create_application(
    payload: CreateApplicationRequest,
    response: Response,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ApplicationOut:
    """Create a draft on the current published version, or idempotently return the
    caller's existing active draft on *any* version of this service (SPEC.md §5 item 2:
    a live v1 draft survives a v2 publish; a second draft is never created)."""
    existing = await _find_active_draft(session, user_id, payload.service_id)
    if existing is not None:
        response.status_code = 200
        return _application_out(existing)

    definition_stmt = (
        select(ServiceDefinitionModel)
        .where(
            ServiceDefinitionModel.service_id == payload.service_id,
            ServiceDefinitionModel.status == ServiceStatus.PUBLISHED,
        )
        .order_by(ServiceDefinitionModel.version.desc())
        .limit(1)
    )
    definition_row = await session.scalar(definition_stmt)
    if definition_row is None:
        raise ApiError(404, "service_not_found", "Published service not found", {"service_id": str(payload.service_id)})

    definition = _parse_definition(definition_row)
    screen = safe_render(definition, {}, {"stage": 0, "step": 0, "screen": 0})
    application = Application(
        user_id=user_id,
        service_id=definition_row.service_id,
        service_version=definition_row.version,
        status="draft",
        revision=1,
        checkpoint=to_checkpoint(screen),
        data={},
        timeline=[],
    )
    session.add(application)
    try:
        await session.commit()
    except IntegrityError:
        # Race: a concurrent request created the active draft first (partial unique
        # index on user+service+version). Roll back and return the winner instead.
        await session.rollback()
        existing = await _find_active_draft(session, user_id, payload.service_id)
        if existing is None:  # pragma: no cover - defensive
            raise
        response.status_code = 200
        return _application_out(existing)

    await session.refresh(application)
    response.status_code = 201
    return _application_out(application)


@router.patch("/applications/{application_id}/draft", response_model=DraftPatchOut)
async def patch_draft(
    application_id: uuid.UUID,
    payload: PatchDraftRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> DraftPatchOut:
    """Incremental autosave (SPEC.md "Обязательное расширение" §2). A stale
    `expected_revision` never overwrites a newer save — it returns 409 with the
    current revision instead."""
    application = await _get_owned_application(session, application_id, user_id)
    if application.status != "draft":
        raise ApiError(409, "application_not_draft", "Application is no longer editable", {"status": application.status})
    if payload.expected_revision != application.revision:
        raise ApiError(
            409,
            "revision_conflict",
            "Draft was modified by another request",
            {"current_revision": application.revision},
        )

    definition_row = await _load_definition_row(session, application.service_id, application.service_version)
    definition = _parse_definition(definition_row)

    merged_data = {**application.data, **payload.data_delta}
    requested_checkpoint = {**application.checkpoint, **(payload.checkpoint or {})}
    stage_index, step_index, screen_index = resolve_indices(definition, requested_checkpoint)
    screen = safe_render(definition, merged_data, {"stage": stage_index, "step": step_index, "screen": screen_index})

    application.data = merged_data
    application.checkpoint = to_checkpoint(screen)
    application.revision += 1
    await session.commit()
    await session.refresh(application)
    return DraftPatchOut(id=application.id, revision=application.revision, checkpoint=application.checkpoint, screen=screen)


@router.get("/applications/{application_id}/resume", response_model=ResumeOut)
async def resume_application(
    application_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ResumeOut:
    application = await _get_owned_application(session, application_id, user_id)
    definition_row = await _load_definition_row(session, application.service_id, application.service_version)
    definition = _parse_definition(definition_row)

    stage_index, step_index, screen_index = resolve_indices(definition, application.checkpoint)
    screen = safe_render(definition, application.data, {"stage": stage_index, "step": step_index, "screen": screen_index})

    return ResumeOut(
        id=application.id,
        service_id=application.service_id,
        service_version=application.service_version,
        status=application.status,
        revision=application.revision,
        data=application.data,
        checkpoint=to_checkpoint(screen),
        definition=definition_row.definition,
        screen=screen,
    )


async def _next_application_number(session: AsyncSession) -> str:
    year = datetime.now(timezone.utc).year
    count = await session.scalar(select(func.count()).select_from(Application).where(Application.number.isnot(None)))
    return f"EPPB-{year}-{(count or 0) + 1:06d}"


def _pick_submit_target(definition: ServiceDefinitionSchema, current_status: str, values: dict) -> str:
    candidates = [t for t in definition.transitions if t.source == current_status]
    for candidate in candidates:
        if candidate.when is None or evaluate_condition(candidate.when, values).value:
            return candidate.target
    raise ApiError(422, "no_transition", "Service definition has no submit transition from the current status", {"status": current_status})


@router.post("/applications/{application_id}/submit", response_model=SubmitOut)
async def submit_application(
    application_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> SubmitOut:
    """Full server-side validation, status transition, application number and
    timeline event (SPEC.md §5 item 5). Never trusts client-side validation."""
    application = await _get_owned_application(session, application_id, user_id)
    if application.status != "draft":
        raise ApiError(409, "application_not_draft", "Application was already submitted", {"status": application.status})

    definition_row = await _load_definition_row(session, application.service_id, application.service_version)
    definition = _parse_definition(definition_row)

    try:
        values, _explanations = compute(definition, application.data)
    except ValueError as exc:
        # A computed formula still references a field the applicant never filled in —
        # that is itself an incomplete application, so report it the same way as a
        # regular required-field validation error instead of a raw 500.
        raise ApiError(
            422,
            "validation_failed",
            "Application data is incomplete or invalid",
            {"errors": [{"field": None, "code": "computation_failed", "message": str(exc)}]},
        ) from exc
    errors = validate(definition, values, full=True)
    if errors:
        raise ApiError(422, "validation_failed", "Application data is incomplete or invalid", {"errors": errors})

    target = _pick_submit_target(definition, application.status, values)
    new_status = transition(definition, application.status, target, values)

    def _apply_submission(app: Application, number: str) -> None:
        app.number = number
        app.status = new_status
        app.timeline = [
            *app.timeline,
            {"status": new_status, "at": datetime.now(timezone.utc).isoformat(), "event": "submitted"},
        ]

    number = await _next_application_number(session)
    _apply_submission(application, number)
    try:
        await session.commit()
    except IntegrityError:
        # Number collision under a concurrent submit — rollback re-expires the instance,
        # so re-fetching gives the pre-attempt state; regenerate the number once and retry.
        await session.rollback()
        application = await _get_owned_application(session, application_id, user_id)
        number = await _next_application_number(session)
        _apply_submission(application, number)
        await session.commit()

    await session.refresh(application)
    return SubmitOut(id=application.id, number=number, status=application.status, timeline=application.timeline)
