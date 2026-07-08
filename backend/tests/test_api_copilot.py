"""API tests for the two AI copilots (SPEC.md §7.1, `app/api/copilot.py`):
`POST /services/{slug}/explain` and `POST /applications/{id}/completeness`. Both run
against `BAITEREK_LLM_PROVIDER=mock` (the test default), exercising the MockLLMProvider
path end to end — same spirit as `test_api_intake.py` for `/intake/match`.
"""
from __future__ import annotations

import pytest

from app.models import ServiceStatus
from tests.conftest import build_definition_json, seed_organization, seed_service, seed_user

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _headers(user) -> dict:
    return {"X-User-Id": str(user.id)}


# ---------------------------------------------------------------------------
# POST /services/{slug}/explain
# ---------------------------------------------------------------------------


async def test_explain_returns_plain_language_paraphrase(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    await seed_service(
        db_session,
        org.id,
        slug="oborotnoe-msb",
        status=ServiceStatus.PUBLISHED,
        definition=build_definition_json(
            meta={
                "title": "Оборотное кредитование для МСБ",
                "summary_plain": "Кредит на пополнение оборотных средств.",
                "conditions": [{"label": "Сумма", "value": "до 100 000 000 ₸"}],
                "documents_checklist": ["Справка о гос. регистрации"],
                "result": "Решение о финансировании",
                "sla_days": 15,
            }
        ),
    )

    response = await client.post("/api/v1/services/oborotnoe-msb/explain", headers=_headers(user))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["degraded"] is False
    assert "Оборотное кредитование" in body["text"]
    assert "Справка о гос. регистрации" in body["text"]


async def test_explain_requires_authentication(client):
    response = await client.post("/api/v1/services/anything/explain")

    assert response.status_code == 401


async def test_explain_unknown_slug_is_404(client, db_session):
    user = await seed_user(db_session)

    response = await client.post("/api/v1/services/does-not-exist/explain", headers=_headers(user))

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /applications/{id}/completeness
# ---------------------------------------------------------------------------


async def _create_draft(client, user, service_row) -> str:
    response = await client.post(
        "/api/v1/applications", json={"service_id": str(service_row.service_id)}, headers=_headers(user)
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_completeness_suggests_missing_required_field(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    application_id = await _create_draft(client, user, service_row)

    response = await client.post(f"/api/v1/applications/{application_id}/completeness", headers=_headers(user))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["degraded"] is False
    assert any("Поле 1" in s for s in body["suggestions"])


async def test_completeness_has_no_suggestions_once_required_field_is_filled(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    application_id = await _create_draft(client, user, service_row)
    await client.patch(
        f"/api/v1/applications/{application_id}/draft",
        json={"data_delta": {"f1": "ТОО Ромашка"}, "checkpoint": None, "expected_revision": 1},
        headers=_headers(user),
    )

    response = await client.post(f"/api/v1/applications/{application_id}/completeness", headers=_headers(user))

    assert response.status_code == 200
    assert response.json()["suggestions"] == []


async def test_completeness_never_blocks_and_does_not_change_status(client, db_session):
    """SPEC.md §7.1 "не блокирует отправку": calling it must not touch
    `application.status` even when required fields are still missing."""
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    application_id = await _create_draft(client, user, service_row)

    check = await client.post(f"/api/v1/applications/{application_id}/completeness", headers=_headers(user))
    assert check.status_code == 200

    resume = await client.get(f"/api/v1/applications/{application_id}/resume", headers=_headers(user))
    assert resume.json()["status"] == "draft"


async def test_completeness_requires_ownership(client, db_session):
    org = await seed_organization(db_session)
    owner = await seed_user(db_session)
    other = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    application_id = await _create_draft(client, owner, service_row)

    response = await client.post(f"/api/v1/applications/{application_id}/completeness", headers=_headers(other))

    assert response.status_code == 404


async def test_completeness_requires_authentication(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    application_id = await _create_draft(client, user, service_row)

    response = await client.post(f"/api/v1/applications/{application_id}/completeness")

    assert response.status_code == 401


async def test_completeness_unknown_application_is_404(client, db_session):
    user = await seed_user(db_session)

    response = await client.post(
        "/api/v1/applications/00000000-0000-0000-0000-000000000000/completeness", headers=_headers(user)
    )

    assert response.status_code == 404
