import re

import pytest

from tests.conftest import seed_organization, seed_service, seed_user

pytestmark = pytest.mark.asyncio(loop_scope="session")

NUMBER_RE = re.compile(r"^EPPB-\d{4}-\d{6}$")


def _headers(user) -> dict:
    return {"X-User-Id": str(user.id)}


async def _create_draft(client, user, service_row) -> dict:
    response = await client.post(
        "/api/v1/applications",
        json={"service_id": str(service_row.service_id)},
        headers=_headers(user),
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# POST /applications
# ---------------------------------------------------------------------------

async def test_create_application_happy_path(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)

    body = await _create_draft(client, user, service_row)

    assert body["service_id"] == str(service_row.service_id)
    assert body["service_version"] == 1
    assert body["status"] == "draft"
    assert body["revision"] == 1
    assert body["data"] == {}
    assert body["checkpoint"] == {"stage_key": "main", "step_key": "form", "screen_key": "f1"}


async def test_create_application_is_idempotent(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)

    first = await _create_draft(client, user, service_row)
    second = await client.post(
        "/api/v1/applications",
        json={"service_id": str(service_row.service_id)},
        headers=_headers(user),
    )

    assert second.status_code == 200
    assert second.json()["id"] == first["id"]


async def test_create_application_keeps_live_v1_draft_when_v2_is_published(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_v1 = await seed_service(db_session, org.id, version=1)

    first = await _create_draft(client, user, service_v1)

    await seed_service(
        db_session, org.id, slug=service_v1.slug, service_id=service_v1.service_id, version=2,
    )

    second = await client.post(
        "/api/v1/applications",
        json={"service_id": str(service_v1.service_id)},
        headers=_headers(user),
    )

    assert second.status_code == 200
    body = second.json()
    assert body["id"] == first["id"]
    assert body["service_version"] == 1  # not upgraded to the newly published v2


async def test_create_application_unknown_service_returns_404(client, db_session):
    import uuid as uuid_module

    user = await seed_user(db_session)
    response = await client.post(
        "/api/v1/applications",
        json={"service_id": str(uuid_module.uuid4())},
        headers=_headers(user),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "service_not_found"


async def test_create_application_requires_auth_header(client, db_session):
    org = await seed_organization(db_session)
    service_row = await seed_service(db_session, org.id)

    response = await client.post("/api/v1/applications", json={"service_id": str(service_row.service_id)})

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# PATCH /applications/{id}/draft
# ---------------------------------------------------------------------------

async def test_patch_draft_happy_path(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = await _create_draft(client, user, service_row)

    response = await client.patch(
        f"/api/v1/applications/{draft['id']}/draft",
        json={"data_delta": {"f1": "Иван"}, "checkpoint": None, "expected_revision": 1},
        headers=_headers(user),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 2
    assert body["checkpoint"]["screen_key"] == "f1"
    keys = [f["key"] for f in body["screen"]["fields"]]
    assert keys == ["f1", "f2", "f3", "f4", "f5", "f6"]


async def test_patch_draft_navigates_to_screen_by_key_not_index(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = await _create_draft(client, user, service_row)

    response = await client.patch(
        f"/api/v1/applications/{draft['id']}/draft",
        json={"data_delta": {}, "checkpoint": {"screen_key": "f7"}, "expected_revision": 1},
        headers=_headers(user),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["checkpoint"]["screen_key"] == "f7"
    keys = [f["key"] for f in body["screen"]["fields"]]
    assert keys == ["f7", "amount"]


async def test_patch_draft_stale_revision_returns_409_with_current_revision(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = await _create_draft(client, user, service_row)

    first = await client.patch(
        f"/api/v1/applications/{draft['id']}/draft",
        json={"data_delta": {"f1": "a"}, "expected_revision": 1},
        headers=_headers(user),
    )
    assert first.status_code == 200
    assert first.json()["revision"] == 2

    stale = await client.patch(
        f"/api/v1/applications/{draft['id']}/draft",
        json={"data_delta": {"f1": "b"}, "expected_revision": 1},
        headers=_headers(user),
    )

    assert stale.status_code == 409
    body = stale.json()
    assert body["code"] == "revision_conflict"
    assert body["details"]["current_revision"] == 2
    assert "trace_id" in body

    # The stale write must not have applied.
    resumed = await client.get(f"/api/v1/applications/{draft['id']}/resume", headers=_headers(user))
    assert resumed.json()["data"]["f1"] == "a"


async def test_patch_draft_rejects_other_user(client, db_session):
    org = await seed_organization(db_session)
    owner = await seed_user(db_session)
    intruder = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = await _create_draft(client, owner, service_row)

    response = await client.patch(
        f"/api/v1/applications/{draft['id']}/draft",
        json={"data_delta": {"f1": "x"}, "expected_revision": 1},
        headers=_headers(intruder),
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /applications/{id}/resume
# ---------------------------------------------------------------------------

async def test_resume_returns_definition_data_checkpoint_and_screen(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = await _create_draft(client, user, service_row)
    await client.patch(
        f"/api/v1/applications/{draft['id']}/draft",
        json={"data_delta": {"f1": "Иван"}, "expected_revision": 1},
        headers=_headers(user),
    )

    response = await client.get(f"/api/v1/applications/{draft['id']}/resume", headers=_headers(user))

    assert response.status_code == 200
    body = response.json()
    assert body["service_id"] == str(service_row.service_id)
    assert body["service_version"] == 1
    assert body["status"] == "draft"
    assert body["revision"] == 2
    assert body["data"]["f1"] == "Иван"
    assert body["checkpoint"]["screen_key"] == "f1"
    assert body["definition"]["meta"]["title"] == "Демонстрационная услуга"
    assert body["screen"]["fields"][0]["key"] == "f1"


# ---------------------------------------------------------------------------
# POST /applications/{id}/submit
# ---------------------------------------------------------------------------

async def _fill_required_fields(client, user, application_id: str, revision: int) -> int:
    response = await client.patch(
        f"/api/v1/applications/{application_id}/draft",
        json={"data_delta": {"f1": "ИП Тестов", "amount": 1000}, "expected_revision": revision},
        headers=_headers(user),
    )
    assert response.status_code == 200, response.text
    return response.json()["revision"]


async def test_submit_happy_path(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = await _create_draft(client, user, service_row)
    await _fill_required_fields(client, user, draft["id"], 1)

    response = await client.post(f"/api/v1/applications/{draft['id']}/submit", headers=_headers(user))

    assert response.status_code == 200, response.text
    body = response.json()
    assert NUMBER_RE.match(body["number"])
    assert body["status"] == "submitted"
    assert len(body["timeline"]) == 1
    assert body["timeline"][0]["status"] == "submitted"


async def test_submit_numbers_are_unique_and_sequential(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)

    draft_a = await _create_draft(client, user, service_row)
    await _fill_required_fields(client, user, draft_a["id"], 1)
    submit_a = await client.post(f"/api/v1/applications/{draft_a['id']}/submit", headers=_headers(user))

    draft_b = await _create_draft(client, user, service_row)
    await _fill_required_fields(client, user, draft_b["id"], 1)
    submit_b = await client.post(f"/api/v1/applications/{draft_b['id']}/submit", headers=_headers(user))

    numbers = {submit_a.json()["number"], submit_b.json()["number"]}
    assert len(numbers) == 2
    assert all(NUMBER_RE.match(n) for n in numbers)


async def test_submit_without_required_field_returns_422(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = await _create_draft(client, user, service_row)
    # amount filled (so the computed formula can resolve) but the required f1 is not.
    await client.patch(
        f"/api/v1/applications/{draft['id']}/draft",
        json={"data_delta": {"amount": 500}, "expected_revision": 1},
        headers=_headers(user),
    )

    response = await client.post(f"/api/v1/applications/{draft['id']}/submit", headers=_headers(user))

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_failed"
    assert {"field": "f1", "code": "required"} in body["details"]["errors"]
    assert "trace_id" in body


async def test_submit_twice_returns_409(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = await _create_draft(client, user, service_row)
    await _fill_required_fields(client, user, draft["id"], 1)
    first = await client.post(f"/api/v1/applications/{draft['id']}/submit", headers=_headers(user))
    assert first.status_code == 200

    second = await client.post(f"/api/v1/applications/{draft['id']}/submit", headers=_headers(user))

    assert second.status_code == 409
    assert second.json()["code"] == "application_not_draft"


async def test_submit_rejects_other_user(client, db_session):
    org = await seed_organization(db_session)
    owner = await seed_user(db_session)
    intruder = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = await _create_draft(client, owner, service_row)
    await _fill_required_fields(client, owner, draft["id"], 1)

    response = await client.post(f"/api/v1/applications/{draft['id']}/submit", headers=_headers(intruder))

    assert response.status_code == 404
