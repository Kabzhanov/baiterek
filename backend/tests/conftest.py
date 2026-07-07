"""Fixtures for the API test suite.

Runs against a real PostgreSQL instance (JSONB/native enums used by the models are
Postgres-specific, so SQLite is not a viable in-memory substitute here — see the
final report for how the test database was provisioned).

`BAITEREK_DATABASE_URL` must be set (see the invocation this suite is meant to run
with) *before* `app.db`/`app.main` are imported, since `app.config.settings()` is
`lru_cache`d and `app.db` builds its engine at import time.
"""
from __future__ import annotations

import json
import os
import random
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

os.environ.setdefault(
    "BAITEREK_DATABASE_URL",
    "postgresql+asyncpg://baiterek:baiterek@127.0.0.1:55432/baiterek_test",
)

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import Session, engine
from app.main import app
from app.models import Organization, ServiceStatus, UserRole


# All tests/fixtures below share one event loop (loop_scope="session"): app.db's
# engine/connection pool is a process-wide singleton, and asyncpg connections created
# on one event loop cannot be reused on another — the default per-test event loop of
# pytest-asyncio would otherwise make every second test fail with "attached to a
# different loop".


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def _clean_database():
    yield
    async with engine.begin() as connection:
        await connection.execute(
            text("TRUNCATE TABLE applications, service_definitions, users, organizations RESTART IDENTITY CASCADE")
        )


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest_asyncio.fixture(loop_scope="session")
async def db_session():
    async with Session() as session:
        yield session


def _random_iin_bin() -> str:
    return str(random.randint(10**11, 10**12 - 1))


async def seed_organization(session, **overrides) -> Organization:
    organization = Organization(name="Демо Холдинг", short_name="Demo", **overrides)
    session.add(organization)
    await session.commit()
    await session.refresh(organization)
    return organization


async def seed_user(session, role: UserRole = UserRole.ENTREPRENEUR) -> SimpleNamespace:
    """Returns a lightweight `SimpleNamespace(id=...)`, not the `User` ORM model.

    `app/models/user.py` maps `role` as `Enum(UserRole, ...)` with the same
    values-vs-names mismatch documented on `seed_service` below, so both inserting via
    the ORM *and* reading a hydrated `User` entity back would crash. Nothing in this
    suite needs more than `user.id`, so a raw INSERT sidesteps the bug entirely instead
    of asking a router (out of scope) to fix it.
    """
    user_id = uuid.uuid4()
    await session.execute(
        text("INSERT INTO users (id, iin_bin, role) VALUES (:id, :iin_bin, :role)"),
        {"id": str(user_id), "iin_bin": _random_iin_bin(), "role": role.value},
    )
    await session.commit()
    return SimpleNamespace(id=user_id, role=role)


def build_definition_json(**overrides) -> dict:
    definition = {
        "service_id": "eppb-demo",
        "version": 1,
        "meta": {
            "title": "Демонстрационная услуга",
            "org": "demo-org",
            "category": "leasing",
            "audience": ["ЮЛ", "ИП"],
            "summary_plain": "Простыми словами о том, что делает услуга.",
            "conditions": [{"label": "Сумма", "value": "до 100 000 000 ₸"}],
            "documents_checklist": ["Справка о гос. регистрации"],
            "result": "Решение о финансировании",
            "sla_days": 15,
        },
        "statuses": ["draft", "submitted"],
        "transitions": [{"source": "draft", "target": "submitted"}],
        "stages": [
            {
                "key": "main",
                "title": "Основной этап",
                "steps": [
                    {
                        "key": "form",
                        "title": "Форма",
                        "fields": [
                            {"key": "f1", "label": "Поле 1", "type": "text", "required": True},
                            {"key": "f2", "label": "Поле 2", "type": "text"},
                            {"key": "f3", "label": "Поле 3", "type": "text"},
                            {"key": "f4", "label": "Поле 4", "type": "text"},
                            {"key": "f5", "label": "Поле 5", "type": "text"},
                            {"key": "f6", "label": "Поле 6", "type": "text"},
                            {"key": "f7", "label": "Поле 7", "type": "text"},
                            {"key": "amount", "label": "Сумма", "type": "number", "minimum": 1},
                        ],
                    }
                ],
            }
        ],
        "computed": [{"key": "doubled", "expression": {"op": "mul", "args": ["$amount", 2]}}],
    }
    definition.update(overrides)
    return definition


async def seed_service(
    session,
    org_id,
    *,
    slug: str = "demo-service",
    status: ServiceStatus = ServiceStatus.PUBLISHED,
    version: int = 1,
    service_id: uuid.UUID | None = None,
    definition: dict | None = None,
) -> SimpleNamespace:
    """Returns a lightweight `SimpleNamespace`, not the `ServiceDefinition` ORM model.

    Raw INSERT намеренно: сид не должен зависеть от ORM-маппинга, который сам
    проверяется тестами (регрессия values_callable у native enum — колонка должна
    принимать lowercase-значения 'published'/'draft' независимо от имён членов Enum).
    """
    service_id = service_id or uuid.uuid4()
    definition = definition or build_definition_json()
    await session.execute(
        text(
            "INSERT INTO service_definitions (service_id, org_id, slug, status, version, definition, published_at) "
            "VALUES (:service_id, :org_id, :slug, :status, :version, CAST(:definition AS JSONB), :published_at)"
        ),
        {
            "service_id": str(service_id),
            "org_id": str(org_id),
            "slug": slug,
            "status": status.value,
            "version": version,
            "definition": json.dumps(definition),
            "published_at": datetime.now(timezone.utc) if status == ServiceStatus.PUBLISHED else None,
        },
    )
    await session.commit()
    return SimpleNamespace(service_id=service_id, org_id=org_id, slug=slug, status=status, version=version, definition=definition)
