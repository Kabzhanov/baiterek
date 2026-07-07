"""GET /api/v1/services, GET /api/v1/services/{slug} (SPEC.md §5 API item 1).

`app/schemas/definition.py`'s `Meta` model only carries `title`/`description` — it does
not model the richer catalog-card fields the frontend contract expects
(`org, category, audience, summary_plain, conditions, documents_checklist, result,
sla_days` — SPEC.md §3.2 DSL example). Parsing through that Pydantic model would
silently drop those extra keys, so this router reads
`service_definitions.definition["meta"]` directly (it is a plain JSONB dict) —
the full catalog-card contract survives even though the DSL schema hasn't caught up yet.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.contracts import ServiceSummary
from app.api.errors import ApiError
from app.db import get_session
from app.models import ServiceDefinition, ServiceStatus

router = APIRouter(tags=["services"])


def _meta(definition: dict) -> dict:
    meta = definition.get("meta") or {}
    return {
        "title": meta.get("title", ""),
        "org": meta.get("org"),
        "category": meta.get("category"),
        "audience": meta.get("audience", []),
        "summary_plain": meta.get("summary_plain", ""),
        "conditions": meta.get("conditions", []),
        "documents_checklist": meta.get("documents_checklist", []),
        "result": meta.get("result"),
        "sla_days": meta.get("sla_days"),
    }


async def _latest_published_by_slug(session: AsyncSession, slug: str) -> ServiceDefinition | None:
    stmt = (
        select(ServiceDefinition)
        .where(ServiceDefinition.slug == slug, ServiceDefinition.status == ServiceStatus.PUBLISHED)
        .order_by(ServiceDefinition.version.desc())
        .limit(1)
    )
    return await session.scalar(stmt)


@router.get("/services", response_model=list[ServiceSummary])
async def list_services(session: AsyncSession = Depends(get_session)) -> list[ServiceSummary]:
    stmt = select(ServiceDefinition).where(ServiceDefinition.status == ServiceStatus.PUBLISHED)
    rows = (await session.execute(stmt)).scalars().all()
    # A service can have several published versions alive at once (publish does not
    # retroactively archive older ones); the catalog shows the latest per service_id.
    latest: dict = {}
    for row in rows:
        current = latest.get(row.service_id)
        if current is None or row.version > current.version:
            latest[row.service_id] = row
    ordered = sorted(latest.values(), key=lambda row: row.slug)
    return [ServiceSummary(id=row.service_id, slug=row.slug, meta=_meta(row.definition)) for row in ordered]


@router.get("/services/{slug}", response_model=ServiceSummary)
async def get_service(slug: str, session: AsyncSession = Depends(get_session)) -> ServiceSummary:
    row = await _latest_published_by_slug(session, slug)
    if row is None:
        raise ApiError(404, "not_found", "Service not found", {"slug": slug})
    return ServiceSummary(id=row.service_id, slug=row.slug, meta=_meta(row.definition))
