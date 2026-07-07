"""Tests for `app/seed` (SPEC.md §6 item 3, docs/IMPLEMENTATION_PLAN.md §10): seeds
organizations, dictionaries and two neutral demo services, and must be safely
re-runnable (`make seed` runs on every deploy).

`tests/conftest.py`'s autouse `_clean_database` fixture truncates
`applications, service_definitions, users, organizations` after every test (not
`dictionaries` — see that fixture), so each test below starts with a clean slate for
the tables it asserts counts on.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Dictionary, Organization, ServiceDefinition, User
from app.seed import run_seed
from app.seed.data import DEMO_SERVICES, DICTIONARIES, ORGANIZATIONS

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_run_seed_creates_organizations_dictionaries_and_services(db_session):
    summary = await run_seed()

    assert summary.organizations_created == len(ORGANIZATIONS)
    assert summary.services_created == len(DEMO_SERVICES)
    assert sorted(summary.service_slugs) == sorted(item["slug"] for item in DEMO_SERVICES)

    organizations = (await db_session.execute(select(Organization))).scalars().all()
    assert {org.short_name for org in organizations} == {item["short_name"] for item in ORGANIZATIONS}

    for spec in DICTIONARIES:
        dictionary = await db_session.scalar(select(Dictionary).where(Dictionary.code == spec["code"]))
        assert dictionary is not None
        assert len(dictionary.items) == len(spec["items"])

    for spec in DEMO_SERVICES:
        row = await db_session.scalar(select(ServiceDefinition).where(ServiceDefinition.slug == spec["slug"]))
        assert row is not None
        assert row.status.value == "published"
        assert row.definition["meta"]["title"] == spec["definition"]["meta"]["title"]


async def test_run_seed_is_idempotent(db_session):
    first = await run_seed()
    second = await run_seed()

    assert first.organizations_created == len(ORGANIZATIONS)
    assert second.organizations_created == 0
    assert second.organizations_existing == len(ORGANIZATIONS)

    assert first.services_created == len(DEMO_SERVICES)
    assert second.services_created == 0
    assert second.services_existing == len(DEMO_SERVICES)

    organizations = (await db_session.execute(select(Organization))).scalars().all()
    assert len(organizations) == len(ORGANIZATIONS)  # no duplicates

    services = (await db_session.execute(select(ServiceDefinition))).scalars().all()
    assert len(services) == len(DEMO_SERVICES)  # no duplicate versions/rows

    # The seed author (get-or-create by iin_bin) must not be duplicated either.
    users = (await db_session.execute(select(User))).scalars().all()
    assert len(users) == 1


async def test_seeded_services_are_neutral_not_control_cases(db_session):
    """Guards the disqualification clause at the data level (SPEC.md §0/§9): the demo
    services created by `make seed` must not be the contest control cases, which may
    only ever be created through the constructor/AI-generator, never seeded."""
    await run_seed()

    titles = " ".join(item["definition"]["meta"]["title"] for item in DEMO_SERVICES).lower()
    forbidden = ("вагон", "животновод", "wagons", "agroanimal")
    assert not any(word in titles for word in forbidden)
