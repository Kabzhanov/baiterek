"""API tests for the constructor/registry router (`app/api/admin_definitions.py`) —
SPEC.md §5.1/§5.2, docs/IMPLEMENTATION_PLAN.md §9. Runs entirely on `MockLLMProvider`
(default `BAITEREK_LLM_PROVIDER`), no network.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models import ServiceDefinition, ServiceStatus, UserRole
from tests.conftest import build_definition_json, seed_organization, seed_service, seed_user

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _headers(user) -> dict:
    return {"X-User-Id": str(user.id)}


async def _row_id(db_session, service_id, version) -> uuid.UUID:
    return await db_session.scalar(
        select(ServiceDefinition.id).where(
            ServiceDefinition.service_id == service_id, ServiceDefinition.version == version
        )
    )


# ---------------------------------------------------------------------------
# POST /admin/definitions (create draft)
# ---------------------------------------------------------------------------


async def test_create_definition_happy_path(client, db_session):
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)

    response = await client.post(
        "/api/v1/admin/definitions",
        json={"org_id": str(org.id), "slug": "new-draft", "definition": build_definition_json()},
        headers=_headers(admin),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "draft"
    assert body["version"] == 1
    assert body["slug"] == "new-draft"
    assert body["definition"]["meta"]["title"] == "Демонстрационная услуга"


async def test_create_definition_without_org_id_uses_default_org(client, db_session):
    # Конструктор в UI не заставляет выбирать организацию: {slug, definition} без org_id
    # должен создавать draft, привязанный к организации по умолчанию (первой).
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)

    response = await client.post(
        "/api/v1/admin/definitions",
        json={"slug": "no-org-draft", "definition": build_definition_json()},
        headers=_headers(admin),
    )

    assert response.status_code == 201, response.text
    assert response.json()["org_id"] == str(org.id)


async def test_create_definition_invalid_schema_returns_422(client, db_session):
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)
    broken = build_definition_json(rules=[{"target": "unknown_field", "effect": "hide", "when": {"op": "eq", "args": ["$f1", "x"]}}])

    response = await client.post(
        "/api/v1/admin/definitions",
        json={"org_id": str(org.id), "slug": "broken", "definition": broken},
        headers=_headers(admin),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_definition"


# ---------------------------------------------------------------------------
# GET /admin/definitions, GET /admin/definitions/{id}
# ---------------------------------------------------------------------------


async def test_list_definitions_returns_every_status(client, db_session):
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)
    await seed_service(db_session, org.id, slug="draft-one", status=ServiceStatus.DRAFT)
    await seed_service(db_session, org.id, slug="published-one", status=ServiceStatus.PUBLISHED)
    await seed_service(db_session, org.id, slug="archived-one", status=ServiceStatus.ARCHIVED)

    response = await client.get("/api/v1/admin/definitions", headers=_headers(admin))

    assert response.status_code == 200
    slugs = {item["slug"] for item in response.json()["items"]}
    assert slugs == {"draft-one", "published-one", "archived-one"}


async def test_get_definition_not_found(client, db_session):
    admin = await seed_user(db_session, role=UserRole.ADMIN)

    response = await client.get(f"/api/v1/admin/definitions/{uuid.uuid4()}", headers=_headers(admin))

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


# ---------------------------------------------------------------------------
# PUT /admin/definitions/{id}
# ---------------------------------------------------------------------------


async def test_update_draft_happy_path(client, db_session):
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)
    created = await client.post(
        "/api/v1/admin/definitions",
        json={"org_id": str(org.id), "slug": "editable", "definition": build_definition_json()},
        headers=_headers(admin),
    )
    definition_id = created.json()["id"]
    updated_definition = build_definition_json(meta={"title": "Обновлённое название"})

    response = await client.put(
        f"/api/v1/admin/definitions/{definition_id}",
        json={"definition": updated_definition},
        headers=_headers(admin),
    )

    assert response.status_code == 200
    assert response.json()["definition"]["meta"]["title"] == "Обновлённое название"


async def test_update_published_definition_returns_409(client, db_session):
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)
    row = await seed_service(db_session, org.id, slug="already-live", status=ServiceStatus.PUBLISHED)
    definition_id = await _row_id(db_session, row.service_id, row.version)

    response = await client.put(
        f"/api/v1/admin/definitions/{definition_id}",
        json={"definition": build_definition_json()},
        headers=_headers(admin),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "not_draft"


# ---------------------------------------------------------------------------
# POST /admin/definitions/{id}/publish
# ---------------------------------------------------------------------------


async def test_publish_first_version_and_deletes_draft_row(client, db_session):
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)
    created = await client.post(
        "/api/v1/admin/definitions",
        json={"org_id": str(org.id), "slug": "to-publish", "definition": build_definition_json()},
        headers=_headers(admin),
    )
    draft_id = created.json()["id"]

    response = await client.post(f"/api/v1/admin/definitions/{draft_id}/publish", headers=_headers(admin))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "published"
    assert body["version"] == 1
    assert body["draft_deleted"] is True

    # the draft row is gone (design decision documented in app/api/admin_definitions.py)
    draft_lookup = await client.get(f"/api/v1/admin/definitions/{draft_id}", headers=_headers(admin))
    assert draft_lookup.status_code == 404

    # and it is immediately visible on the public catalog, no redeploy needed
    catalog = await client.get("/api/v1/services/to-publish")
    assert catalog.status_code == 200


async def test_publish_computes_next_version_from_published_history_not_draft_version(client, db_session):
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)
    service_id = uuid.uuid4()
    await seed_service(db_session, org.id, slug="multi", service_id=service_id, version=1, status=ServiceStatus.PUBLISHED)
    await seed_service(db_session, org.id, slug="multi", service_id=service_id, version=2, status=ServiceStatus.PUBLISHED)
    # the draft's OWN version number (42) is deliberately unrelated to the published
    # lineage (1, 2) — publish must derive the new version from published history only.
    draft_row = await seed_service(
        db_session, org.id, slug="multi", service_id=service_id, version=42, status=ServiceStatus.DRAFT
    )
    draft_id = await _row_id(db_session, service_id, 42)

    response = await client.post(f"/api/v1/admin/definitions/{draft_id}/publish", headers=_headers(admin))

    assert response.status_code == 201, response.text
    assert response.json()["version"] == 3
    assert draft_row.service_id == service_id  # sanity: same service lineage throughout


async def test_publish_requires_draft_status(client, db_session):
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)
    row = await seed_service(db_session, org.id, slug="already-published", status=ServiceStatus.PUBLISHED)
    definition_id = await _row_id(db_session, row.service_id, row.version)

    response = await client.post(f"/api/v1/admin/definitions/{definition_id}/publish", headers=_headers(admin))

    assert response.status_code == 409
    assert response.json()["code"] == "not_draft"


async def test_publish_preflight_rejects_invalid_definition_and_leaves_draft_untouched(client, db_session):
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)
    broken = build_definition_json(rules=[{"target": "unknown_field", "effect": "hide", "when": {"op": "eq", "args": ["$f1", "x"]}}])
    row = await seed_service(db_session, org.id, slug="invalid-draft", status=ServiceStatus.DRAFT, definition=broken)
    definition_id = await _row_id(db_session, row.service_id, row.version)

    response = await client.post(f"/api/v1/admin/definitions/{definition_id}/publish", headers=_headers(admin))

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_definition"

    still_there = await client.get(f"/api/v1/admin/definitions/{definition_id}", headers=_headers(admin))
    assert still_there.status_code == 200
    assert still_there.json()["status"] == "draft"


# ---------------------------------------------------------------------------
# POST /admin/definitions/{id}/duplicate
# ---------------------------------------------------------------------------


async def test_duplicate_creates_new_service_with_suffixed_slug(client, db_session):
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)
    created = await client.post(
        "/api/v1/admin/definitions",
        json={"org_id": str(org.id), "slug": "original", "definition": build_definition_json()},
        headers=_headers(admin),
    )
    original = created.json()

    response = await client.post(f"/api/v1/admin/definitions/{original['id']}/duplicate", headers=_headers(admin))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["slug"] == "original-copy"
    assert body["service_id"] != original["service_id"]
    assert body["status"] == "draft"
    assert body["version"] == 1

    detail = await client.get(f"/api/v1/admin/definitions/{body['id']}", headers=_headers(admin))
    assert detail.json()["definition"]["meta"]["title"].endswith("(копия)")


# ---------------------------------------------------------------------------
# GET /admin/definitions/{id}/export
# ---------------------------------------------------------------------------


async def test_export_is_lossless(client, db_session):
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)
    definition = build_definition_json()
    created = await client.post(
        "/api/v1/admin/definitions",
        json={"org_id": str(org.id), "slug": "exportable", "definition": definition},
        headers=_headers(admin),
    )
    definition_id = created.json()["id"]

    response = await client.get(f"/api/v1/admin/definitions/{definition_id}/export", headers=_headers(admin))

    assert response.status_code == 200
    assert response.json() == definition

    # round-trips through the existing import endpoint (SPEC.md §6 "export/import
    # сохраняет Definition полностью")
    reimport = await client.post(
        "/api/v1/admin/definitions/import",
        json={"org_id": str(org.id), "slug": "exportable-reimport", "status": "draft", "definition": response.json()},
        headers=_headers(admin),
    )
    assert reimport.status_code == 200, reimport.text


# ---------------------------------------------------------------------------
# RBAC — entrepreneur is not author/admin
# ---------------------------------------------------------------------------


async def test_entrepreneur_forbidden_from_registry_endpoints(client, db_session):
    org = await seed_organization(db_session)
    entrepreneur = await seed_user(db_session, role=UserRole.ENTREPRENEUR)

    list_response = await client.get("/api/v1/admin/definitions", headers=_headers(entrepreneur))
    create_response = await client.post(
        "/api/v1/admin/definitions",
        json={"org_id": str(org.id), "slug": "nope", "definition": build_definition_json()},
        headers=_headers(entrepreneur),
    )
    generate_response = await client.post(
        "/api/v1/admin/definitions/generate",
        json={"text": "Кредит", "org_id": str(org.id)},
        headers=_headers(entrepreneur),
    )

    for response in (list_response, create_response, generate_response):
        assert response.status_code == 403
        assert response.json()["code"] == "forbidden"


# ---------------------------------------------------------------------------
# POST /admin/definitions/generate (SPEC.md §5.3, §7.2)
# ---------------------------------------------------------------------------


async def test_generate_happy_path_creates_draft(client, db_session):
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)

    response = await client.post(
        "/api/v1/admin/definitions/generate",
        json={"text": "Оборотный кредит для малого бизнеса до 20 миллионов тенге", "org_id": str(org.id)},
        headers=_headers(admin),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["warnings"] == []
    assert body["degraded"] is False

    detail = await client.get(f"/api/v1/admin/definitions/{body['id']}", headers=_headers(admin))
    assert detail.json()["status"] == "draft"


async def test_generate_retries_then_succeeds_with_warning(client, db_session):
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)

    response = await client.post(
        "/api/v1/admin/definitions/generate",
        json={"text": "AI_TEST_INVALID_ONCE Гарантия по кредиту для экспортёров", "org_id": str(org.id)},
        headers=_headers(admin),
    )

    assert response.status_code == 201, response.text
    assert response.json()["warnings"], "expected a warning describing the repair attempt"


async def test_generate_exhausts_retries_returns_422_and_creates_nothing(client, db_session):
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)
    before = await client.get("/api/v1/admin/definitions", headers=_headers(admin))
    before_count = len(before.json()["items"])

    response = await client.post(
        "/api/v1/admin/definitions/generate",
        json={"text": "AI_TEST_INVALID_ALWAYS полностью невалидный ответ", "org_id": str(org.id)},
        headers=_headers(admin),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "ai_generation_failed"

    after = await client.get("/api/v1/admin/definitions", headers=_headers(admin))
    assert len(after.json()["items"]) == before_count
