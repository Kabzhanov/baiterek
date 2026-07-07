from datetime import date
from decimal import Decimal

import pytest

from app.models import AnalyticsMaterial, AnalyticsMaterialType, KnowledgeItem, KnowledgeItemCategory, MapProject
from tests.conftest import seed_organization

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _seed_map_project(session, org_id, **overrides) -> MapProject:
    defaults = dict(
        name="Тестовый проект",
        region_code="KZ-75",
        locality="Алматы",
        lat=Decimal("43.222000"),
        lng=Decimal("76.851200"),
        industry="Сельское хозяйство",
        amount=Decimal("100000000.00"),
        period_start=date(2024, 1, 1),
        period_end=date(2025, 1, 1),
        status="Реализуется",
        description="Демо-проект для теста",
    )
    defaults.update(overrides)
    row = MapProject(org_id=org_id, **defaults)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def _seed_analytics_material(session, org_id, **overrides) -> AnalyticsMaterial:
    defaults = dict(
        type=AnalyticsMaterialType.REPORT,
        title="Тестовый материал",
        description="Демо-описание",
        source="test.kz",
        period="2024",
        url="https://example.kz/report",
        embed_allowed=False,
    )
    defaults.update(overrides)
    row = AnalyticsMaterial(org_id=org_id, **defaults)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def _seed_knowledge_item(session, **overrides) -> KnowledgeItem:
    defaults = dict(
        category=KnowledgeItemCategory.GUIDE,
        title="Тестовый материал знаний",
        description="Демо-описание",
        content="Демо-контент",
        url=None,
    )
    defaults.update(overrides)
    row = KnowledgeItem(**defaults)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# /api/v1/map/projects
# ---------------------------------------------------------------------------


async def test_list_map_projects_returns_items(client, db_session):
    org = await seed_organization(db_session, short_name="Даму")
    row = await _seed_map_project(db_session, org.id, name="Проект А")

    response = await client.get("/api/v1/map/projects")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["id"] == str(row.id)
    assert item["organization"] == "Даму"
    assert item["name"] == "Проект А"
    assert item["region_code"] == "KZ-75"
    assert item["is_demo"] is True


async def test_list_map_projects_filters_by_organization(client, db_session):
    damu = await seed_organization(db_session, short_name="Даму")
    brk = await seed_organization(db_session, short_name="БРК")
    await _seed_map_project(db_session, damu.id, name="Проект Даму")
    await _seed_map_project(db_session, brk.id, name="Проект БРК")

    response = await client.get("/api/v1/map/projects", params={"organization": "БРК"})

    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["organization"] == "БРК"


async def test_list_map_projects_filters_by_region_industry_status(client, db_session):
    org = await seed_organization(db_session, short_name="Даму")
    await _seed_map_project(
        db_session, org.id, name="Проект 1", region_code="KZ-75", industry="Туризм", status="Завершён"
    )
    await _seed_map_project(
        db_session, org.id, name="Проект 2", region_code="KZ-11", industry="Сельское хозяйство", status="Реализуется"
    )

    response = await client.get("/api/v1/map/projects", params={"region": "KZ-11"})
    assert [item["name"] for item in response.json()["items"]] == ["Проект 2"]

    response = await client.get("/api/v1/map/projects", params={"industry": "Туризм"})
    assert [item["name"] for item in response.json()["items"]] == ["Проект 1"]

    response = await client.get("/api/v1/map/projects", params={"status": "Завершён"})
    assert [item["name"] for item in response.json()["items"]] == ["Проект 1"]


# ---------------------------------------------------------------------------
# /api/v1/map/summary
# ---------------------------------------------------------------------------


async def test_map_summary_aggregates_counts_and_amounts(client, db_session):
    damu = await seed_organization(db_session, short_name="Даму")
    brk = await seed_organization(db_session, short_name="БРК")
    await _seed_map_project(db_session, damu.id, name="A", region_code="KZ-75", amount=Decimal("100000000.00"))
    await _seed_map_project(db_session, damu.id, name="B", region_code="KZ-75", amount=Decimal("50000000.00"))
    await _seed_map_project(db_session, brk.id, name="C", region_code="KZ-11", amount=Decimal("30000000.00"))

    response = await client.get("/api/v1/map/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 3
    assert Decimal(body["total_amount"]) == Decimal("180000000.00")
    by_region = {row["region_code"]: row for row in body["by_region"]}
    assert by_region["KZ-75"]["count"] == 2
    assert Decimal(by_region["KZ-75"]["amount"]) == Decimal("150000000.00")
    assert by_region["KZ-11"]["count"] == 1


async def test_map_summary_respects_organization_filter(client, db_session):
    damu = await seed_organization(db_session, short_name="Даму")
    brk = await seed_organization(db_session, short_name="БРК")
    await _seed_map_project(db_session, damu.id, name="A")
    await _seed_map_project(db_session, brk.id, name="B")

    response = await client.get("/api/v1/map/summary", params={"organization": "Даму"})

    body = response.json()
    assert body["total_count"] == 1


# ---------------------------------------------------------------------------
# /api/v1/analytics/materials
# ---------------------------------------------------------------------------


async def test_list_analytics_materials_filters_by_organization_and_type(client, db_session):
    damu = await seed_organization(db_session, short_name="Даму")
    brk = await seed_organization(db_session, short_name="БРК")
    await _seed_analytics_material(db_session, damu.id, title="Отчёт Даму", type=AnalyticsMaterialType.REPORT)
    await _seed_analytics_material(db_session, brk.id, title="Дашборд БРК", type=AnalyticsMaterialType.DASHBOARD)

    response = await client.get("/api/v1/analytics/materials")
    assert len(response.json()["items"]) == 2

    response = await client.get("/api/v1/analytics/materials", params={"organization": "Даму"})
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Отчёт Даму"
    assert items[0]["type"] == "report"

    response = await client.get("/api/v1/analytics/materials", params={"type": "dashboard"})
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Дашборд БРК"


# ---------------------------------------------------------------------------
# /api/v1/knowledge/items
# ---------------------------------------------------------------------------


async def test_list_knowledge_items_filters_by_category(client, db_session):
    await _seed_knowledge_item(db_session, title="Гайд", category=KnowledgeItemCategory.GUIDE)
    await _seed_knowledge_item(db_session, title="Чек-лист", category=KnowledgeItemCategory.CHECKLIST)

    response = await client.get("/api/v1/knowledge/items")
    assert len(response.json()["items"]) == 2

    response = await client.get("/api/v1/knowledge/items", params={"category": "checklist"})
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Чек-лист"
