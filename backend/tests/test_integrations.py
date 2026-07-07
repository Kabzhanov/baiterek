"""Tests for `backend/app/integrations/` and the routers that expose them
(SPEC.md §8 "Имитация интеграций"): mock eGov IDP login, ГБД ЮЛ lookup, ЭЦП sign, and
the admin status-change endpoint that stands in for bpm_status.
"""
from __future__ import annotations

import uuid

import pytest

from app.models import UserRole
from tests.conftest import build_definition_json, seed_organization, seed_service, seed_user

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _headers(user) -> dict:
    return {"X-User-Id": str(user.id)}


# ---------------------------------------------------------------------------
# egov_idp
# ---------------------------------------------------------------------------


async def test_list_mock_egov_users_returns_synthetic_test_identities(client):
    response = await client.get("/api/v1/auth/mock-egov/users")

    assert response.status_code == 200
    body = response.json()
    keys = {item["key"] for item in body}
    assert keys == {"ip_testov", "too_demo"}


async def test_mock_egov_login_creates_user(client, db_session):
    response = await client.post("/api/v1/auth/mock-egov", json={"test_user_key": "too_demo"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["iin_bin"] == "990101400000"
    assert body["role"] == "entrepreneur"
    assert body["mock"] is True
    assert "имитация" in body["disclaimer"].lower()
    uuid.UUID(body["user_id"])  # does not raise


async def test_mock_egov_login_is_idempotent_per_test_user(client, db_session):
    first = await client.post("/api/v1/auth/mock-egov", json={"test_user_key": "ip_testov"})
    second = await client.post("/api/v1/auth/mock-egov", json={"test_user_key": "ip_testov"})

    assert first.json()["user_id"] == second.json()["user_id"]


async def test_mock_egov_login_unknown_key_returns_404(client):
    response = await client.post("/api/v1/auth/mock-egov", json={"test_user_key": "does-not-exist"})

    assert response.status_code == 404
    assert response.json()["code"] == "unknown_test_user"


# ---------------------------------------------------------------------------
# gbd_ul
# ---------------------------------------------------------------------------


async def test_gbd_ul_lookup_known_bin_returns_marked_mock_data(client):
    response = await client.get("/api/v1/integrations/gbd-ul/990101400000")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "ТОО «Демо»"
    assert body["mock"] is True
    assert "имитация" in body["disclaimer"].lower()


async def test_gbd_ul_lookup_unknown_bin_returns_404(client):
    response = await client.get("/api/v1/integrations/gbd-ul/000000000000")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


# ---------------------------------------------------------------------------
# ecp_sign
# ---------------------------------------------------------------------------


async def test_ecp_sign_returns_marked_mock_signature(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = (
        await client.post(
            "/api/v1/applications", json={"service_id": str(service_row.service_id)}, headers=_headers(user)
        )
    ).json()

    response = await client.post(
        "/api/v1/integrations/ecp/sign", json={"application_id": draft["id"]}, headers=_headers(user)
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["signature_meta"]["mock"] is True
    assert "MOCK" in body["signature_meta"]["algorithm"]
    assert body["signature_meta"]["serial_number"].startswith("MOCK-")


async def test_ecp_sign_rejects_other_user(client, db_session):
    org = await seed_organization(db_session)
    owner = await seed_user(db_session)
    intruder = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = (
        await client.post(
            "/api/v1/applications", json={"service_id": str(service_row.service_id)}, headers=_headers(owner)
        )
    ).json()

    response = await client.post(
        "/api/v1/integrations/ecp/sign", json={"application_id": draft["id"]}, headers=_headers(intruder)
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# bpm (admin status change)
# ---------------------------------------------------------------------------


async def test_admin_status_change_applies_declared_transition(client, db_session):
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)
    applicant = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = (
        await client.post(
            "/api/v1/applications", json={"service_id": str(service_row.service_id)}, headers=_headers(applicant)
        )
    ).json()

    response = await client.post(
        f"/api/v1/admin/applications/{draft['id']}/status",
        json={"target": "submitted", "comment": "проверено вручную"},
        headers=_headers(admin),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "submitted"
    assert body["mock"] is True
    assert body["timeline"][-1]["event"] == "admin_status_change"
    assert body["timeline"][-1]["comment"] == "проверено вручную"


async def test_admin_status_change_rejects_undeclared_transition(client, db_session):
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)
    applicant = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = (
        await client.post(
            "/api/v1/applications", json={"service_id": str(service_row.service_id)}, headers=_headers(applicant)
        )
    ).json()

    response = await client.post(
        f"/api/v1/admin/applications/{draft['id']}/status",
        json={"target": "approved"},  # build_definition_json only declares draft -> submitted
        headers=_headers(admin),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_transition"


async def test_admin_status_change_forbidden_for_non_admin(client, db_session):
    org = await seed_organization(db_session)
    applicant = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = (
        await client.post(
            "/api/v1/applications", json={"service_id": str(service_row.service_id)}, headers=_headers(applicant)
        )
    ).json()

    response = await client.post(
        f"/api/v1/admin/applications/{draft['id']}/status",
        json={"target": "submitted"},
        headers=_headers(applicant),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


# ---------------------------------------------------------------------------
# definitions import (used by app/seed, see test_seed.py for the seed-level coverage)
# ---------------------------------------------------------------------------


async def test_import_definition_creates_then_is_idempotent_by_slug(client, db_session):
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)
    definition = build_definition_json(service_id="import-test")

    first = await client.post(
        "/api/v1/admin/definitions/import",
        json={"org_id": str(org.id), "slug": "import-test-slug", "status": "published", "definition": definition},
        headers=_headers(admin),
    )
    second = await client.post(
        "/api/v1/admin/definitions/import",
        json={"org_id": str(org.id), "slug": "import-test-slug", "status": "published", "definition": definition},
        headers=_headers(admin),
    )

    assert first.status_code == 200, first.text
    assert first.json()["created"] is True
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["id"] == first.json()["id"]

    catalog = await client.get("/api/v1/services/import-test-slug")
    assert catalog.status_code == 200


async def test_import_definition_rejects_invalid_schema(client, db_session):
    org = await seed_organization(db_session)
    admin = await seed_user(db_session, role=UserRole.ADMIN)
    invalid_definition = build_definition_json()
    invalid_definition["rules"] = [{"target": "unknown_field", "effect": "hide", "when": {"op": "eq", "args": ["$f1", "x"]}}]

    response = await client.post(
        "/api/v1/admin/definitions/import",
        json={"org_id": str(org.id), "slug": "invalid-def", "status": "draft", "definition": invalid_definition},
        headers=_headers(admin),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_definition"


async def test_import_definition_forbidden_for_entrepreneur(client, db_session):
    org = await seed_organization(db_session)
    entrepreneur = await seed_user(db_session)
    definition = build_definition_json()

    response = await client.post(
        "/api/v1/admin/definitions/import",
        json={"org_id": str(org.id), "slug": "forbidden-def", "status": "draft", "definition": definition},
        headers=_headers(entrepreneur),
    )

    assert response.status_code == 403
