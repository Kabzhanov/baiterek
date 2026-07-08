"""Constructor/registry API (SPEC.md §5.1 "Реестр услуг", §5.2 "Визуальный
конструктор", §5.3 "AI-генератор услуги"; docs/IMPLEMENTATION_PLAN.md §9 "Этап 4 —
административный контур /create").

This is deliberately a SEPARATE router from `app/api/definitions.py` (which only
exposes the narrow, idempotent `/admin/definitions/import` used by `make seed` — see
that file's module docstring) rather than an edit to it: import/seed is a different
concern (idempotent-by-slug, no draft/publish lifecycle) from the constructor's
full CRUD + preflight + versioning lifecycle below. Both routers happen to share the
`/admin/definitions` path prefix; FastAPI dispatches by exact path/method, so
`POST /admin/definitions/import` (definitions.py) and `POST /admin/definitions`
(this file) never collide.

## Publish semantics — draft row is DELETED, not kept (design decision)

`service_definitions` rows are immutable once `status=published`
(`app/models/service_definition.py`: "publish создаёт новую строку с version+1,
предыдущие версии не изменяются"). Publishing a draft therefore always INSERTs a new
row rather than flipping the draft's own `status` in place. That leaves an open
question the task spec calls out explicitly: what happens to the draft row itself?

Chosen: the draft row is deleted in the same transaction that inserts the new
published row. Reasoning:

1. Nothing references a draft row by identity. Applications only ever attach to a
   *published* `service_id`+`version` pair (SPEC.md §5 API: `POST /applications`
   creates a draft "на текущей published-версии"); a draft `service_definitions` row
   is never a foreign-key target. Deleting it cannot orphan anything.
2. The alternative — leave the draft row sitting at whatever version number it had —
   produces a permanently stale, confusing registry entry: the draft's own `version`
   column is NOT the version it just published as (the published row's version is
   `max(published/archived versions for this service_id) + 1`, computed independently
   — see `_next_published_version` below), so a surviving draft row would show a
   version number that has no relationship to the version that actually went live.
   `GET /admin/definitions` (list ALL statuses) would keep displaying a "draft" that
   looks editable but represents content already superseded by the published row.
3. Deleting keeps the invariant simple and auditable: a `service_id` has at most one
   *live* draft row at any time (the thing `PUT`/`POST .../publish` operate on) plus
   zero or more immutable published/archived history rows. That symmetry is what
   `_next_published_version`'s "max across published+archived, ignore draft" query
   below relies on.

Known gap this leaves (out of scope for this task — no new endpoint requested for it):
there is no "reopen this published service for a v(N+1) edit" endpoint yet. An author
who wants to revise an already-published service has to `duplicate` it (which forks a
NEW `service_id` — SPEC.md §5.1 explicitly "новый service_id") rather than continue the
same `service_id`'s version lineage. A future "new draft from published" endpoint would
slot in cleanly (insert a fresh draft row copying the latest published `definition`,
same `service_id`) without touching anything in this file.
"""
from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.budget import log_ai_call
from app.ai.factory import resolve_provider
from app.ai.generation import GenerationFailed, generate_definition_json
from app.api.contracts import (
    CreateDefinitionRequest,
    DefinitionDetailOut,
    DefinitionListItem,
    DefinitionListOut,
    DuplicateDefinitionOut,
    GenerateDefinitionOut,
    GenerateDefinitionRequest,
    PublishDefinitionOut,
    UpdateDefinitionRequest,
)
from app.api.deps import require_role
from app.api.errors import ApiError
from app.db import get_session
from app.models import AuditLog, Organization, ServiceDefinition, ServiceStatus, UserRole
from app.schemas.definition import ServiceDefinition as ServiceDefinitionSchema

router = APIRouter(tags=["admin-definitions"])

_AUTHOR_OR_ADMIN = require_role(UserRole.ADMIN, UserRole.AUTHOR)
# NOTE (SPEC.md §5.4 "author — конструктор своей организации"): true org-scoped
# authorization for AUTHOR would need a `users` ↔ `organizations` relationship that
# does not exist on the current `User` model (`app/models/user.py` has no `org_id`).
# Adding one is a models change, out of scope here (task scope excludes `app/models`).
# Both roles therefore get the same access below; only role-level RBAC (ADMIN/AUTHOR
# vs ENTREPRENEUR) is enforced.


def _title(definition: dict) -> str:
    meta = definition.get("meta") or {}
    return str(meta.get("title", ""))


def _slugify(text: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return slug or fallback


async def _unique_slug(session: AsyncSession, base: str) -> str:
    candidate = base
    suffix = 2
    while await session.scalar(select(ServiceDefinition.id).where(ServiceDefinition.slug == candidate)):
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


async def _resolve_org_id(session: AsyncSession, org_id: uuid.UUID | None) -> uuid.UUID:
    """Организация услуги: явная из запроса или первая по умолчанию — конструктор в UI
    не заставляет выбирать организацию (SPEC §5.2), а колонка org_id NOT NULL."""
    if org_id is not None:
        return org_id
    default_org = await session.scalar(select(Organization.id).order_by(Organization.created_at).limit(1))
    if default_org is None:
        raise ApiError(422, "no_organization", "Нет ни одной организации для привязки услуги", {})
    return default_org


def _to_detail(row: ServiceDefinition) -> DefinitionDetailOut:
    return DefinitionDetailOut(
        id=row.id,
        service_id=row.service_id,
        org_id=row.org_id,
        slug=row.slug,
        status=row.status.value if hasattr(row.status, "value") else row.status,
        version=row.version,
        definition=row.definition,
        created_by=row.created_by,
        published_at=row.published_at,
        updated_at=row.updated_at,
    )


def _validate_definition(definition: dict) -> None:
    try:
        ServiceDefinitionSchema.model_validate(definition)
    except ValidationError as exc:
        # `include_context=False`: pydantic embeds the raw `ValueError` raised inside
        # `ServiceDefinitionSchema.references` in `ctx.error`, which is not JSON
        # serializable and would otherwise turn this 422 into an unhandled 500 — same
        # fix already applied in `app/api/definitions.py`.
        raise ApiError(
            422,
            "invalid_definition",
            "Service Definition failed schema validation",
            {"errors": exc.errors(include_context=False, include_url=False)},
        ) from exc


async def _load_or_404(session: AsyncSession, definition_id: uuid.UUID) -> ServiceDefinition:
    row = await session.get(ServiceDefinition, definition_id)
    if row is None:
        raise ApiError(404, "not_found", "Service Definition not found", {"id": str(definition_id)})
    return row


# ---------------------------------------------------------------------------
# GET /admin/definitions, GET /admin/definitions/{id}
# ---------------------------------------------------------------------------


@router.get("/admin/definitions", response_model=DefinitionListOut)
async def list_definitions(
    _admin_user_id: uuid.UUID = Depends(_AUTHOR_OR_ADMIN),
    session: AsyncSession = Depends(get_session),
) -> DefinitionListOut:
    stmt = select(ServiceDefinition).order_by(ServiceDefinition.updated_at.desc())
    rows = (await session.execute(stmt)).scalars().all()
    return DefinitionListOut(
        items=[
            DefinitionListItem(
                id=row.id,
                service_id=row.service_id,
                slug=row.slug,
                status=row.status.value,
                version=row.version,
                title=_title(row.definition),
                updated_at=row.updated_at,
            )
            for row in rows
        ]
    )


@router.get("/admin/definitions/{definition_id}", response_model=DefinitionDetailOut)
async def get_definition(
    definition_id: uuid.UUID,
    _admin_user_id: uuid.UUID = Depends(_AUTHOR_OR_ADMIN),
    session: AsyncSession = Depends(get_session),
) -> DefinitionDetailOut:
    row = await _load_or_404(session, definition_id)
    return _to_detail(row)


# ---------------------------------------------------------------------------
# POST /admin/definitions, PUT /admin/definitions/{id}
# ---------------------------------------------------------------------------


@router.post("/admin/definitions", response_model=DefinitionDetailOut, status_code=201)
async def create_definition(
    payload: CreateDefinitionRequest,
    admin_user_id: uuid.UUID = Depends(_AUTHOR_OR_ADMIN),
    session: AsyncSession = Depends(get_session),
) -> DefinitionDetailOut:
    _validate_definition(payload.definition)
    row = ServiceDefinition(
        org_id=await _resolve_org_id(session, payload.org_id),
        slug=payload.slug,
        status=ServiceStatus.DRAFT,
        version=1,
        definition=payload.definition,
        created_by=admin_user_id,
        published_at=None,
    )
    session.add(row)
    session.add(
        AuditLog(user_id=admin_user_id, action="definition_create", entity_type="service_definition", entity_id=None)
    )
    await session.commit()
    await session.refresh(row)
    return _to_detail(row)


@router.put("/admin/definitions/{definition_id}", response_model=DefinitionDetailOut)
async def update_definition(
    definition_id: uuid.UUID,
    payload: UpdateDefinitionRequest,
    admin_user_id: uuid.UUID = Depends(_AUTHOR_OR_ADMIN),
    session: AsyncSession = Depends(get_session),
) -> DefinitionDetailOut:
    row = await _load_or_404(session, definition_id)
    if row.status != ServiceStatus.DRAFT:
        raise ApiError(
            409,
            "not_draft",
            "Only a draft Service Definition can be updated; published versions are immutable",
            {"status": row.status.value},
        )
    _validate_definition(payload.definition)
    before = dict(row.definition)
    row.definition = payload.definition
    session.add(
        AuditLog(
            user_id=admin_user_id,
            action="definition_update",
            entity_type="service_definition",
            entity_id=row.id,
            before={"definition": before},
            after={"definition": payload.definition},
        )
    )
    await session.commit()
    await session.refresh(row)
    return _to_detail(row)


# ---------------------------------------------------------------------------
# POST /admin/definitions/{id}/publish
# ---------------------------------------------------------------------------


async def _next_published_version(session: AsyncSession, service_id: uuid.UUID) -> int:
    stmt = select(func.max(ServiceDefinition.version)).where(
        ServiceDefinition.service_id == service_id,
        ServiceDefinition.status.in_([ServiceStatus.PUBLISHED, ServiceStatus.ARCHIVED]),
    )
    current_max = await session.scalar(stmt)
    return (current_max or 0) + 1


@router.post("/admin/definitions/{definition_id}/publish", response_model=PublishDefinitionOut, status_code=201)
async def publish_definition(
    definition_id: uuid.UUID,
    admin_user_id: uuid.UUID = Depends(_AUTHOR_OR_ADMIN),
    session: AsyncSession = Depends(get_session),
) -> PublishDefinitionOut:
    draft = await _load_or_404(session, definition_id)
    if draft.status != ServiceStatus.DRAFT:
        raise ApiError(
            409,
            "not_draft",
            "Only a draft Service Definition can be published",
            {"status": draft.status.value},
        )

    # Preflight (SPEC.md §5.2 "Публикация: валидация целостности Definition"): schema
    # validation already covers "unique keys" (duplicate stage/step/field/status keys),
    # "ссылки rules/formulas" (unknown rule targets, unknown formula refs, formula
    # dependency cycles) and "статусная модель" (transitions reference known statuses)
    # — see `ServiceDefinitionSchema.references` in `app/schemas/definition.py`.
    _validate_definition(draft.definition)

    new_version = await _next_published_version(session, draft.service_id)
    published_definition = dict(draft.definition)
    published_definition["version"] = new_version
    published_at = datetime.now(timezone.utc)
    published = ServiceDefinition(
        service_id=draft.service_id,
        org_id=draft.org_id,
        slug=draft.slug,
        status=ServiceStatus.PUBLISHED,
        version=new_version,
        definition=published_definition,
        created_by=draft.created_by,
        published_at=published_at,
    )
    draft_audit = {"draft_id": str(draft.id), "draft_version": draft.version}
    # Draft удаляется ДО вставки published-строки: при первой публикации draft занимает
    # ту же пару (service_id, version) и uq_service_definitions_service_id_version
    # сработал бы на flush INSERT'а раньше, чем дошло бы до delete.
    await session.delete(draft)  # see module docstring: draft row does not survive publish
    await session.flush()
    session.add(published)
    await session.flush()  # assigns `published.id` for the audit row below

    session.add(
        AuditLog(
            user_id=admin_user_id,
            action="definition_publish",
            entity_type="service_definition",
            entity_id=published.id,
            before=draft_audit,
            after={"version": new_version, "status": ServiceStatus.PUBLISHED.value},
        )
    )
    await session.commit()
    await session.refresh(published)
    return PublishDefinitionOut(
        id=published.id,
        service_id=published.service_id,
        slug=published.slug,
        status=published.status.value,
        version=published.version,
        published_at=published.published_at,
        draft_deleted=True,
    )


# ---------------------------------------------------------------------------
# POST /admin/definitions/{id}/duplicate
# ---------------------------------------------------------------------------


@router.post("/admin/definitions/{definition_id}/duplicate", response_model=DuplicateDefinitionOut, status_code=201)
async def duplicate_definition(
    definition_id: uuid.UUID,
    admin_user_id: uuid.UUID = Depends(_AUTHOR_OR_ADMIN),
    session: AsyncSession = Depends(get_session),
) -> DuplicateDefinitionOut:
    source = await _load_or_404(session, definition_id)
    new_slug = await _unique_slug(session, f"{source.slug}-copy")

    new_definition = dict(source.definition)
    original_dsl_id = new_definition.get("service_id", source.slug)
    new_definition["service_id"] = f"{original_dsl_id}-copy"
    meta = dict(new_definition.get("meta") or {})
    if meta.get("title"):
        meta["title"] = f"{meta['title']} (копия)"
    new_definition["meta"] = meta

    row = ServiceDefinition(
        org_id=source.org_id,
        slug=new_slug,
        status=ServiceStatus.DRAFT,
        version=1,
        definition=new_definition,
        created_by=admin_user_id,
        published_at=None,
    )
    session.add(row)
    session.add(
        AuditLog(
            user_id=admin_user_id,
            action="definition_duplicate",
            entity_type="service_definition",
            entity_id=None,
            before={"source_id": str(source.id)},
        )
    )
    await session.commit()
    await session.refresh(row)
    return DuplicateDefinitionOut(
        id=row.id, service_id=row.service_id, slug=row.slug, status=row.status.value, version=row.version
    )


# ---------------------------------------------------------------------------
# GET /admin/definitions/{id}/export
# ---------------------------------------------------------------------------


@router.get("/admin/definitions/{definition_id}/export", response_model=dict)
async def export_definition(
    definition_id: uuid.UUID,
    _admin_user_id: uuid.UUID = Depends(_AUTHOR_OR_ADMIN),
    session: AsyncSession = Depends(get_session),
) -> dict:
    # Returns exactly `row.definition` — lossless round-trip with
    # `POST /admin/definitions/import`'s `definition` field (`app/api/definitions.py`)
    # and with this router's own `POST /admin/definitions`.
    row = await _load_or_404(session, definition_id)
    return row.definition


# ---------------------------------------------------------------------------
# POST /admin/definitions/generate (SPEC.md §5.3, §7.2)
# ---------------------------------------------------------------------------


@router.post("/admin/definitions/generate", response_model=GenerateDefinitionOut, status_code=201)
async def generate_definition(
    payload: GenerateDefinitionRequest,
    admin_user_id: uuid.UUID = Depends(_AUTHOR_OR_ADMIN),
    session: AsyncSession = Depends(get_session),
) -> GenerateDefinitionOut:
    provider, degraded = await resolve_provider(session)

    try:
        outcome = await generate_definition_json(provider, payload.text)
    except GenerationFailed as exc:
        await log_ai_call(
            session, user_id=admin_user_id, kind="ai_generate", provider=provider.name, degraded=degraded
        )
        raise ApiError(
            422,
            "ai_generation_failed",
            "AI did not produce a schema-valid Service Definition after retries",
            {"errors": exc.errors, "attempts": exc.attempts},
        ) from exc

    slug = payload.slug or await _unique_slug(session, _slugify(_title(outcome.definition), "ai-service"))
    row = ServiceDefinition(
        org_id=await _resolve_org_id(session, payload.org_id),
        slug=slug,
        status=ServiceStatus.DRAFT,
        version=1,
        definition=outcome.definition,
        created_by=admin_user_id,
        published_at=None,
    )
    session.add(row)
    await session.flush()  # assigns `row.id` for the audit row below
    session.add(
        AuditLog(
            user_id=admin_user_id,
            action="definition_create",
            entity_type="service_definition",
            entity_id=row.id,
            after={"source": "ai_generate", "attempts": outcome.attempts},
        )
    )
    await log_ai_call(session, user_id=admin_user_id, kind="ai_generate", provider=provider.name, degraded=degraded)
    await session.refresh(row)
    return GenerateDefinitionOut(id=row.id, warnings=outcome.warnings, degraded=degraded)
