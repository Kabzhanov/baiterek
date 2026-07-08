"""Two AI copilots for the entrepreneur-facing UI (SPEC.md §7.1, AI-критерий 9.4):

- `POST /services/{slug}/explain` — «Объяснить простыми словами» a published service's
  `meta` (the service-card page).
- `POST /applications/{id}/completeness` — «Проверка полноты заявки» before submit,
  advisory only, never blocks `/submit` (the review screen).

Both are open to any authenticated (or open-access auto-provisioned) user — neither is
an admin/author tool, same as `app/api/intake.py`'s `/intake/match`. Kept as their own
router rather than folded into `intake.py`/`applications.py`/`services.py` so the AI
layer's endpoints stay grouped together, mirroring how `app/api/admin_definitions.py`
already separates the `/generate` AI endpoint from `definitions.py`'s CRUD endpoints.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.budget import log_ai_call
from app.ai.completeness import completeness_suggestions
from app.ai.explain import explain_service
from app.ai.factory import resolve_provider
from app.api.applications import _get_owned_application, _load_definition_row, _parse_definition
from app.api.contracts import ApplicationCompletenessOut, ExplainServiceOut
from app.api.deps import get_current_user_id
from app.api.errors import ApiError
from app.api.screen import resolve_indices
from app.api.services import _latest_published_by_slug
from app.db import get_session
from app.engine.runtime import compute

router = APIRouter(tags=["copilot"])


@router.post("/services/{slug}/explain", response_model=ExplainServiceOut)
async def explain(
    slug: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ExplainServiceOut:
    row = await _latest_published_by_slug(session, slug)
    if row is None:
        raise ApiError(404, "not_found", "Service not found", {"slug": slug})
    meta = row.definition.get("meta") or {}

    provider, budget_degraded = await resolve_provider(session)
    text, call_degraded = await explain_service(provider, meta)
    degraded = budget_degraded or call_degraded
    await log_ai_call(session, user_id=user_id, kind="ai_explain", provider=provider.name, degraded=degraded)
    return ExplainServiceOut(text=text, degraded=degraded)


@router.post("/applications/{application_id}/completeness", response_model=ApplicationCompletenessOut)
async def completeness(
    application_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ApplicationCompletenessOut:
    """Advisory only (SPEC.md §7.1 "не блокирует отправку"): never changes
    `application.status`, never raises on incomplete data — only `/submit`'s full
    `app.engine.runtime.validate` is authoritative for that."""
    application = await _get_owned_application(session, application_id, user_id)
    definition_row = await _load_definition_row(session, application.service_id, application.service_version)
    definition = _parse_definition(definition_row)

    stage_index, _step_index, _screen_index = resolve_indices(definition, application.checkpoint)
    current_stage_key = definition.stages[stage_index].key if definition.stages else None
    try:
        values, _explanations = compute(definition, application.data, partial=True)
    except ValueError:
        # Same "advisory only, must never itself fail" stance as the rest of this
        # endpoint — app.api.applications.submit_application raises 422 on a genuine
        # computation error; here we just fall back to the raw stored data instead.
        values = dict(application.data)

    provider, budget_degraded = await resolve_provider(session)
    suggestions, method = await completeness_suggestions(provider, definition, values, stage_key=current_stage_key)
    await log_ai_call(
        session, user_id=user_id, kind="ai_completeness", provider=provider.name, degraded=budget_degraded, method=method
    )
    return ApplicationCompletenessOut(suggestions=suggestions, degraded=budget_degraded)
