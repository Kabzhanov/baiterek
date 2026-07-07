"""GET /api/v1/map/projects, /api/v1/map/summary, /api/v1/analytics/materials,
/api/v1/knowledge/items (SPEC.md §4.5-4.7, docs/IMPLEMENTATION_PLAN.md §11 "Этап 6").

All four endpoints are public read-only catalogs (no auth) — the underlying rows are
managed only through admin/seed today (SPEC.md §5.4 "Управление контентом" is a later
increment), so this router only ever reads.

Filtering is done in SQL, not in Python, so `map/summary` and the list endpoints stay
consistent as the dataset grows past the ~120 seeded demo rows.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.contracts import (
    AnalyticsMaterialListOut,
    AnalyticsMaterialOut,
    KnowledgeItemListOut,
    KnowledgeItemOut,
    MapProjectListOut,
    MapProjectOut,
    MapRegionSummary,
    MapSummaryOut,
)
from app.db import get_session
from app.models import AnalyticsMaterial, KnowledgeItem, MapProject, Organization

router = APIRouter(tags=["content"])


def _map_project_out(row: MapProject, org: Organization) -> MapProjectOut:
    return MapProjectOut(
        id=row.id,
        org_id=row.org_id,
        organization=org.short_name,
        name=row.name,
        region_code=row.region_code,
        locality=row.locality,
        lat=row.lat,
        lng=row.lng,
        industry=row.industry,
        amount=row.amount,
        period_start=row.period_start,
        period_end=row.period_end,
        status=row.status,
        description=row.description,
        is_demo=row.is_demo,
    )


def _map_projects_query(
    organization: str | None,
    region: str | None,
    industry: str | None,
    status: str | None,
):
    stmt = select(MapProject, Organization).join(Organization, MapProject.org_id == Organization.id)
    if organization:
        stmt = stmt.where(Organization.short_name == organization)
    if region:
        stmt = stmt.where(MapProject.region_code == region)
    if industry:
        stmt = stmt.where(MapProject.industry == industry)
    if status:
        stmt = stmt.where(MapProject.status == status)
    return stmt


@router.get("/map/projects", response_model=MapProjectListOut)
async def list_map_projects(
    organization: str | None = Query(default=None, description="Organization.short_name"),
    region: str | None = Query(default=None, description="region_code (КАТО)"),
    industry: str | None = Query(default=None),
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> MapProjectListOut:
    stmt = _map_projects_query(organization, region, industry, status).order_by(MapProject.name)
    rows = (await session.execute(stmt)).all()
    return MapProjectListOut(items=[_map_project_out(project, org) for project, org in rows])


@router.get("/map/summary", response_model=MapSummaryOut)
async def map_summary(
    organization: str | None = Query(default=None),
    region: str | None = Query(default=None),
    industry: str | None = Query(default=None),
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> MapSummaryOut:
    stmt = _map_projects_query(organization, region, industry, status)
    rows = (await session.execute(stmt)).all()
    total_count = len(rows)
    total_amount = sum((project.amount for project, _org in rows if project.amount is not None), start=0)
    by_region: dict[str, dict] = {}
    for project, _org in rows:
        bucket = by_region.setdefault(project.region_code, {"count": 0, "amount": 0})
        bucket["count"] += 1
        bucket["amount"] += project.amount or 0
    regions = [
        MapRegionSummary(region_code=code, count=data["count"], amount=data["amount"])
        for code, data in sorted(by_region.items())
    ]
    return MapSummaryOut(total_count=total_count, total_amount=total_amount, by_region=regions)


@router.get("/analytics/materials", response_model=AnalyticsMaterialListOut)
async def list_analytics_materials(
    organization: str | None = Query(default=None, description="Organization.short_name"),
    type: str | None = Query(default=None, description="AnalyticsMaterialType value"),
    session: AsyncSession = Depends(get_session),
) -> AnalyticsMaterialListOut:
    stmt = select(AnalyticsMaterial, Organization).join(Organization, AnalyticsMaterial.org_id == Organization.id)
    if organization:
        stmt = stmt.where(Organization.short_name == organization)
    if type:
        stmt = stmt.where(AnalyticsMaterial.type == type)
    stmt = stmt.order_by(AnalyticsMaterial.title)
    rows = (await session.execute(stmt)).all()
    return AnalyticsMaterialListOut(
        items=[
            AnalyticsMaterialOut(
                id=material.id,
                org_id=material.org_id,
                organization=org.short_name,
                type=material.type,
                title=material.title,
                description=material.description,
                source=material.source,
                period=material.period,
                url=material.url,
                embed_allowed=material.embed_allowed,
            )
            for material, org in rows
        ]
    )


@router.get("/knowledge/items", response_model=KnowledgeItemListOut)
async def list_knowledge_items(
    category: str | None = Query(default=None, description="KnowledgeItemCategory value"),
    session: AsyncSession = Depends(get_session),
) -> KnowledgeItemListOut:
    stmt = select(KnowledgeItem)
    if category:
        stmt = stmt.where(KnowledgeItem.category == category)
    stmt = stmt.order_by(KnowledgeItem.title)
    rows = (await session.execute(stmt)).scalars().all()
    return KnowledgeItemListOut(
        items=[
            KnowledgeItemOut(
                id=item.id,
                category=item.category,
                title=item.title,
                description=item.description,
                content=item.content,
                url=item.url,
            )
            for item in rows
        ]
    )
