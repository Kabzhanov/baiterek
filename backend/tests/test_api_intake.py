"""API tests for `POST /api/v1/intake/match` (`app/api/intake.py`, SPEC.md §7.1) — the
non-LLM keyword fallback, since `BAITEREK_LLM_PROVIDER` defaults to `mock`.
"""
from __future__ import annotations

import pytest

from app.models import ServiceStatus, UserRole
from tests.conftest import build_definition_json, seed_organization, seed_service, seed_user

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _headers(user) -> dict:
    return {"X-User-Id": str(user.id)}


async def test_intake_match_returns_keyword_fallback_for_entrepreneur(client, db_session):
    org = await seed_organization(db_session)
    entrepreneur = await seed_user(db_session, role=UserRole.ENTREPRENEUR)
    await seed_service(
        db_session,
        org.id,
        slug="oborotnoe-msb",
        status=ServiceStatus.PUBLISHED,
        definition=build_definition_json(
            meta={
                "title": "Оборотное кредитование для МСБ",
                "summary_plain": "Кредит на пополнение оборотных средств для малого и среднего бизнеса.",
                "category": "credit",
            }
        ),
    )

    response = await client.post(
        "/api/v1/intake/match",
        json={"query": "нужен кредит на оборотные средства для малого бизнеса"},
        headers=_headers(entrepreneur),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["method"] == "keyword"
    assert body["degraded"] is False
    assert body["items"][0]["slug"] == "oborotnoe-msb"
    assert body["items"][0]["why"]


async def test_intake_match_requires_authentication(client):
    response = await client.post("/api/v1/intake/match", json={"query": "кредит"})

    assert response.status_code == 401


async def test_intake_match_with_empty_catalog_returns_empty_items(client, db_session):
    entrepreneur = await seed_user(db_session, role=UserRole.ENTREPRENEUR)

    response = await client.post(
        "/api/v1/intake/match", json={"query": "что угодно"}, headers=_headers(entrepreneur)
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
