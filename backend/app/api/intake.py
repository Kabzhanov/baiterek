"""`POST /api/v1/intake/match` (SPEC.md §7.1 "Подбор меры" — the main-page free-text
search: "Опишите свой бизнес или задачу своими словами" → top-3 services + "why").

Open to any authenticated role (not `require_role`-gated): this is the entrepreneur-
facing homepage feature SPEC.md §7.1 describes, not an admin/author tool — unlike
`app/api/admin_definitions.py`'s `/generate`, which the RBAC tests target instead.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.budget import log_ai_call
from app.ai.factory import resolve_provider
from app.ai.intake import match_services
from app.api.contracts import IntakeMatchItem, IntakeMatchOut, IntakeMatchRequest
from app.api.deps import get_current_user_id
from app.db import get_session
from app.models import ServiceDefinition, ServiceStatus

router = APIRouter(tags=["intake"])


async def _published_catalog(session: AsyncSession) -> list[dict]:
    stmt = select(ServiceDefinition).where(ServiceDefinition.status == ServiceStatus.PUBLISHED)
    rows = (await session.execute(stmt)).scalars().all()
    # Same "latest version per service_id" rule `app/api/services.py` uses for the
    # public catalog — the AI/keyword matcher should only ever offer what a user could
    # actually open right now.
    latest: dict[uuid.UUID, ServiceDefinition] = {}
    for row in rows:
        current = latest.get(row.service_id)
        if current is None or row.version > current.version:
            latest[row.service_id] = row
    catalog = []
    for row in latest.values():
        meta = row.definition.get("meta") or {}
        catalog.append(
            {
                "slug": row.slug,
                "title": meta.get("title", row.slug),
                "summary_plain": meta.get("summary_plain", ""),
                "category": meta.get("category", ""),
            }
        )
    return catalog


@router.post("/intake/match", response_model=IntakeMatchOut)
async def intake_match(
    payload: IntakeMatchRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> IntakeMatchOut:
    provider, degraded = await resolve_provider(session)
    catalog = await _published_catalog(session)
    matches, method = await match_services(provider, payload.query, catalog)
    await log_ai_call(
        session, user_id=user_id, kind="ai_intake", provider=provider.name, degraded=degraded, method=method
    )
    return IntakeMatchOut(
        items=[IntakeMatchItem(slug=m.slug, title=m.title, why=m.why) for m in matches],
        method=method,
        degraded=degraded,
    )
