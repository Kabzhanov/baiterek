"""`python -m app.seed` (SPEC.md §6 item 3, docs/IMPLEMENTATION_PLAN.md §10): seeds
organizations, dictionaries and two neutral demo Service Definitions.

Organizations/dictionaries are inserted directly (there is no public API for them in
this MVP) but Definitions are NOT — SPEC.md §6 "make seed создает Definitions через
тот же публичный API конструктора, а не прямыми INSERT" — so `_seed_demo_services`
drives an in-process ASGI client against `app.main.app` and calls
`POST /api/v1/admin/definitions/import` (the same router `app/api/definitions.py`
exposes publicly), exactly like `backend/tests/conftest.py`'s `client` fixture does.

Idempotent: safe to run repeatedly (`make seed` re-runs on every deploy). Organizations
are matched by `short_name`, dictionaries are upserted by their unique `code`, the
admin author is matched by `iin_bin`, and Definitions are matched by `slug` (see
`app/api/definitions.py`'s `created: false` short-circuit).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Session
from app.models import Dictionary, Organization, User, UserRole
from app.seed.data import DEMO_SERVICES, DICTIONARIES, ORGANIZATIONS

# Синтетический тестовый автор для сида Definitions (не реальный человек, SPEC.md §9).
_SEED_AUTHOR_IIN = "000000000001"


@dataclass
class SeedSummary:
    organizations_created: int = 0
    organizations_existing: int = 0
    dictionaries_upserted: int = 0
    services_created: int = 0
    services_existing: int = 0
    service_slugs: list[str] = field(default_factory=list)

    def describe(self) -> str:
        return (
            f"organizations: +{self.organizations_created} (already had {self.organizations_existing}); "
            f"dictionaries upserted: {self.dictionaries_upserted}; "
            f"services: +{self.services_created} (already had {self.services_existing}) "
            f"{self.service_slugs}"
        )


async def _seed_organizations(session: AsyncSession, summary: SeedSummary) -> dict[str, Organization]:
    by_short_name: dict[str, Organization] = {}
    for spec in ORGANIZATIONS:
        existing = await session.scalar(select(Organization).where(Organization.short_name == spec["short_name"]))
        if existing is not None:
            by_short_name[spec["short_name"]] = existing
            summary.organizations_existing += 1
            continue
        organization = Organization(**spec)
        session.add(organization)
        await session.flush()
        by_short_name[spec["short_name"]] = organization
        summary.organizations_created += 1
    await session.commit()
    return by_short_name


async def _seed_dictionaries(session: AsyncSession, summary: SeedSummary) -> None:
    for spec in DICTIONARIES:
        statement = pg_insert(Dictionary).values(code=spec["code"], name=spec["name"], items=spec["items"])
        statement = statement.on_conflict_do_update(
            index_elements=[Dictionary.code],
            # `.items` (attribute access) collides with `ColumnCollection.items()` (the
            # dict-like method) — bracket access is required to reach the "items" column.
            set_={"name": statement.excluded.name, "items": statement.excluded["items"]},
        )
        await session.execute(statement)
        summary.dictionaries_upserted += 1
    await session.commit()


async def _seed_author(session: AsyncSession) -> User:
    existing = await session.scalar(select(User).where(User.iin_bin == _SEED_AUTHOR_IIN))
    if existing is not None:
        return existing
    author = User(iin_bin=_SEED_AUTHOR_IIN, role=UserRole.ADMIN, profile={"name": "Сид-автор (make seed)"})
    session.add(author)
    await session.commit()
    await session.refresh(author)
    return author


async def _seed_demo_services(
    author: User, organizations: dict[str, Organization], summary: SeedSummary
) -> None:
    # Imported lazily: app.main pulls in the whole api_router, which would otherwise
    # make `python -m app.seed` import every router module before organizations even
    # exist to seed.
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://seed") as client:
        headers = {"X-User-Id": str(author.id)}
        for service in DEMO_SERVICES:
            org = organizations[service["org_short_name"]]
            response = await client.post(
                "/api/v1/admin/definitions/import",
                json={
                    "org_id": str(org.id),
                    "slug": service["slug"],
                    "status": "published",
                    "definition": service["definition"],
                },
                headers=headers,
            )
            response.raise_for_status()
            body = response.json()
            summary.service_slugs.append(body["slug"])
            if body["created"]:
                summary.services_created += 1
            else:
                summary.services_existing += 1


async def run_seed() -> SeedSummary:
    summary = SeedSummary()
    async with Session() as session:
        organizations = await _seed_organizations(session, summary)
        await _seed_dictionaries(session, summary)
        author = await _seed_author(session)
    await _seed_demo_services(author, organizations, summary)
    return summary


__all__ = ["SeedSummary", "run_seed"]
