import uuid

import pytest

from app.models import ServiceStatus
from tests.conftest import build_definition_json, seed_organization, seed_service

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_list_services_returns_catalog_card_contract(client, db_session):
    org = await seed_organization(db_session)
    row = await seed_service(db_session, org.id, slug="lizing-vagonov")

    response = await client.get("/api/v1/services")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    item = body[0]
    assert item["id"] == str(row.service_id)
    assert item["slug"] == "lizing-vagonov"
    meta = item["meta"]
    assert meta["title"] == "Демонстрационная услуга"
    assert meta["org"] == "demo-org"
    assert meta["category"] == "leasing"
    assert meta["audience"] == ["ЮЛ", "ИП"]
    assert meta["summary_plain"]
    assert meta["conditions"] == [{"label": "Сумма", "value": "до 100 000 000 ₸"}]
    assert meta["documents_checklist"] == ["Справка о гос. регистрации"]
    assert meta["result"] == "Решение о финансировании"
    assert meta["sla_days"] == 15


async def test_list_services_excludes_draft_and_archived(client, db_session):
    org = await seed_organization(db_session)
    await seed_service(db_session, org.id, slug="black-draft", status=ServiceStatus.DRAFT)
    await seed_service(db_session, org.id, slug="black-archived", status=ServiceStatus.ARCHIVED)

    response = await client.get("/api/v1/services")

    assert response.json() == []


async def test_list_services_shows_latest_published_version_only(client, db_session):
    org = await seed_organization(db_session)
    service_id = uuid.uuid4()
    await seed_service(
        db_session, org.id, slug="demo", service_id=service_id, version=1,
        definition=build_definition_json(meta={"title": "v1"}),
    )
    await seed_service(
        db_session, org.id, slug="demo", service_id=service_id, version=2,
        definition=build_definition_json(meta={"title": "v2"}),
    )

    response = await client.get("/api/v1/services")

    body = response.json()
    assert len(body) == 1
    assert body[0]["meta"]["title"] == "v2"


async def test_get_service_by_slug(client, db_session):
    org = await seed_organization(db_session)
    await seed_service(db_session, org.id, slug="agro-crf")

    response = await client.get("/api/v1/services/agro-crf")

    assert response.status_code == 200
    assert response.json()["slug"] == "agro-crf"


async def test_get_service_not_found_uses_error_envelope(client):
    response = await client.get("/api/v1/services/unknown-slug")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "not_found"
    assert body["details"] == {"slug": "unknown-slug"}
    assert "trace_id" in body and body["trace_id"]
