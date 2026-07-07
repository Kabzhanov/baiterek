"""`python -m app.seed.control_cases` (SPEC.md §9 "Контрольный кейс",
docs/IMPLEMENTATION_PLAN.md §10 "Этап 5 — контрольные услуги и достоверность").

Loads the two contest control-case Service Definitions and publishes them — this is
the ONLY place either control case is created. SPEC.md §0's disqualification clause is
explicit: "услуга, реализованная «жёстко в коде» без конструктора, не соответствует
сути задачи. Обе контрольные услуги существуют ТОЛЬКО как записи `service_definitions`
в БД, созданные через конструктор/AI-генератор." Accordingly:

- The Definition JSON itself lives in `app/seed/fixtures/*.json` (data, not code).
- It reaches the database exclusively through the same public HTTP surface the
  constructor/AI-generator use: `POST /admin/definitions/import` (the narrow,
  idempotent-by-slug import endpoint `app/api/definitions.py` exposes — the same one
  `app/seed/__init__.py` drives for the two neutral demo services) followed by
  `POST /admin/definitions/{id}/publish` (the constructor's own publish endpoint,
  `app/api/admin_definitions.py`) — never a direct `ServiceDefinition(...)` INSERT.
- Both calls run in-process against `app.main.app` via `httpx.ASGITransport`, exactly
  like `app/seed/__init__.py`'s `_seed_demo_services` and `backend/tests/conftest.py`'s
  `client` fixture.

Deliberately separate from `app/seed/__init__.py`/`python -m app.seed`: that module's
two demo services are intentionally generic financing programs (see its docstring),
NOT the contest control cases. Keeping them apart means `make seed` never has to know
about the control cases (or vice versa), and the disqualification-clause grep
(`make lint-hardcode`) has a single, obvious place to point at if anyone asks "where do
the two control-case names come from".

Idempotent and safe to run repeatedly: an already-imported slug (`created: false`)
is left alone unless it is still sitting in `draft` (e.g. a previous run crashed
between import and publish), in which case this run finishes publishing it. A
completed prior run is therefore a no-op.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Session
from app.models import Organization, User, UserRole
from app.seed.data import ORGANIZATIONS

_FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Синтетический автор контрольных кейсов (отдельно от `app/seed/__init__.py`'s
# `_SEED_AUTHOR_IIN`, чтобы `python -m app.seed.control_cases` не зависел от того,
# запускался ли до этого `python -m app.seed`).
_AUTHOR_IIN = "000000000002"

# `fixture` — имя файла в `app/seed/fixtures/`; `slug` — публичный slug услуги;
# `org_short_name` — держатель программы из `app.seed.data.ORGANIZATIONS`
# (см. docs/control-cases.md для источников и обоснования выбора держателя).
_CASES: tuple[dict[str, str], ...] = (
    {"fixture": "control_case_a.json", "slug": "wagons-leasing", "org_short_name": "БРК"},
    {"fixture": "control_case_b.json", "slug": "agro-livestock", "org_short_name": "КАФ"},
)


@dataclass
class ControlCaseSummary:
    imported: list[str] = field(default_factory=list)
    already_published: list[str] = field(default_factory=list)
    published_this_run: list[str] = field(default_factory=list)

    def describe(self) -> str:
        return (
            f"imported: {self.imported}; already published: {self.already_published}; "
            f"published this run: {self.published_this_run}"
        )


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURES_DIR / name).read_text(encoding="utf-8"))


async def _ensure_organization(session: AsyncSession, short_name: str) -> Organization:
    existing = await session.scalar(select(Organization).where(Organization.short_name == short_name))
    if existing is not None:
        return existing
    spec = next(item for item in ORGANIZATIONS if item["short_name"] == short_name)
    organization = Organization(**spec)
    session.add(organization)
    await session.commit()
    await session.refresh(organization)
    return organization


async def _ensure_author(session: AsyncSession) -> User:
    existing = await session.scalar(select(User).where(User.iin_bin == _AUTHOR_IIN))
    if existing is not None:
        return existing
    author = User(iin_bin=_AUTHOR_IIN, role=UserRole.ADMIN, profile={"name": "Сид-автор контрольных кейсов"})
    session.add(author)
    await session.commit()
    await session.refresh(author)
    return author


async def run_control_cases() -> ControlCaseSummary:
    summary = ControlCaseSummary()
    async with Session() as session:
        author = await _ensure_author(session)
        orgs = {case["org_short_name"]: await _ensure_organization(session, case["org_short_name"]) for case in _CASES}

    # Imported lazily, same reasoning as app/seed/__init__.py's `_seed_demo_services`:
    # `app.main` pulls in the whole `api_router`, which would otherwise force importing
    # every router module before the organizations/author above even exist to seed.
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://control-cases") as client:
        headers = {"X-User-Id": str(author.id)}
        for case in _CASES:
            definition = _load_fixture(case["fixture"])
            org = orgs[case["org_short_name"]]

            import_response = await client.post(
                "/api/v1/admin/definitions/import",
                json={
                    "org_id": str(org.id),
                    "slug": case["slug"],
                    # Imported as a draft, then published below through the constructor's
                    # own publish endpoint — see module docstring for why this is two
                    # calls instead of `status: "published"` in one.
                    "status": "draft",
                    "definition": definition,
                },
                headers=headers,
            )
            import_response.raise_for_status()
            body = import_response.json()
            if body["created"]:
                summary.imported.append(body["slug"])

            if body["status"] == "published":
                summary.already_published.append(body["slug"])
                continue

            publish_response = await client.post(
                f"/api/v1/admin/definitions/{body['id']}/publish",
                headers=headers,
            )
            publish_response.raise_for_status()
            summary.published_this_run.append(publish_response.json()["slug"])

    return summary


def main() -> None:
    summary = asyncio.run(run_control_cases())
    print(f"control cases: {summary.describe()}")


if __name__ == "__main__":
    main()


__all__ = ["ControlCaseSummary", "run_control_cases"]
