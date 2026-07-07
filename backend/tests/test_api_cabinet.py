"""Личный кабинет: GET /api/v1/applications (список) и GET /api/v1/applications/{id}
(детали с таймлайном/уведомлениями). Процент заполнения = заполненные видимые поля /
все видимые поля — см. `app/api/cabinet.py::_progress_percent`."""
import uuid

import pytest
from sqlalchemy import text

from tests.conftest import build_definition_json, seed_organization, seed_service, seed_user

pytestmark = pytest.mark.asyncio(loop_scope="session")


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


async def _patch_draft(client, user, application: dict, data_delta: dict) -> dict:
    response = await client.patch(
        f"/api/v1/applications/{application['id']}/draft",
        json={"data_delta": data_delta, "checkpoint": None, "expected_revision": application["revision"]},
        headers=_headers(user),
    )
    assert response.status_code == 200, response.text
    return response.json()


FULL_DATA = {"f1": "a", "f2": "b", "f3": "c", "f4": "d", "f5": "e", "f6": "f", "f7": "g", "amount": 10}


# ---------------------------------------------------------------------------
# GET /applications (список)
# ---------------------------------------------------------------------------

async def test_list_requires_auth(client):
    response = await client.get("/api/v1/applications")
    assert response.status_code == 401


async def test_list_empty(client, db_session):
    user = await seed_user(db_session)
    response = await client.get("/api/v1/applications", headers=_headers(user))
    assert response.status_code == 200
    assert response.json() == {"items": []}


async def test_list_draft_progress_percent(client, db_session):
    """4 заполненных из 8 видимых полей (правил нет — видимы все) → 50%."""
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = await _create_draft(client, user, service_row)
    await _patch_draft(client, user, draft, {"f1": "a", "f2": "b", "f3": "c", "f4": "d"})

    response = await client.get("/api/v1/applications", headers=_headers(user))

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    item = items[0]
    assert item["id"] == draft["id"]
    assert item["status"] == "draft"
    assert item["number"] is None
    assert item["progress_percent"] == 50
    assert item["service"] == {"slug": "demo-service", "title": "Демонстрационная услуга"}
    assert item["service_version"] == 1
    assert item["checkpoint"]["stage_key"] == "main"
    assert item["updated_at"]


async def test_list_progress_skips_hidden_fields(client, db_session):
    """Правило прячет f2 при f1='ip': видимых полей 7, заполнено 1 → round(100/7)=14."""
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    definition = build_definition_json(
        rules=[{"target": "f2", "effect": "hide", "when": {"op": "eq", "args": ["$f1", "ip"]}}]
    )
    service_row = await seed_service(db_session, org.id, definition=definition)
    draft = await _create_draft(client, user, service_row)
    await _patch_draft(client, user, draft, {"f1": "ip"})

    response = await client.get("/api/v1/applications", headers=_headers(user))

    assert response.json()["items"][0]["progress_percent"] == 14


async def test_list_submitted_and_labels_plain(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    definition = build_definition_json()
    definition["meta"]["labels_plain"] = {"submitted": "Заявка отправлена"}
    service_row = await seed_service(db_session, org.id, definition=definition)
    draft = await _create_draft(client, user, service_row)
    await _patch_draft(client, user, draft, FULL_DATA)
    submit = await client.post(f"/api/v1/applications/{draft['id']}/submit", headers=_headers(user))
    assert submit.status_code == 200, submit.text

    response = await client.get("/api/v1/applications", headers=_headers(user))

    item = response.json()["items"][0]
    assert item["status"] == "submitted"
    assert item["number"] == submit.json()["number"]
    assert item["progress_percent"] == 100
    assert item["labels_plain"] == {"submitted": "Заявка отправлена"}


async def test_list_shows_only_own_applications(client, db_session):
    org = await seed_organization(db_session)
    owner = await seed_user(db_session)
    stranger = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    await _create_draft(client, owner, service_row)

    response = await client.get("/api/v1/applications", headers=_headers(stranger))

    assert response.status_code == 200
    assert response.json()["items"] == []


# ---------------------------------------------------------------------------
# GET /applications/{id} (детали)
# ---------------------------------------------------------------------------

async def test_detail_draft(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = await _create_draft(client, user, service_row)

    response = await client.get(f"/api/v1/applications/{draft['id']}", headers=_headers(user))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == draft["id"]
    assert body["status"] == "draft"
    assert body["timeline"] == []
    assert body["documents"] == []
    assert body["notifications"] == []
    assert body["created_at"]


async def test_detail_timeline_after_submit(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = await _create_draft(client, user, service_row)
    await _patch_draft(client, user, draft, FULL_DATA)
    submit = await client.post(f"/api/v1/applications/{draft['id']}/submit", headers=_headers(user))
    assert submit.status_code == 200, submit.text

    response = await client.get(f"/api/v1/applications/{draft['id']}", headers=_headers(user))

    body = response.json()
    assert len(body["timeline"]) == 1
    assert body["timeline"][0]["status"] == "submitted"
    assert body["timeline"][0]["event"] == "submitted"
    assert body["timeline"][0]["at"]


async def test_detail_returns_own_notifications_only(client, db_session):
    org = await seed_organization(db_session)
    user = await seed_user(db_session)
    other = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = await _create_draft(client, user, service_row)
    for target_user, title in ((user, "Нужны документы"), (other, "Чужое уведомление")):
        await db_session.execute(
            text(
                "INSERT INTO notifications (user_id, application_id, type, title, body) "
                "VALUES (:user_id, :application_id, :type, :title, :body)"
            ),
            {
                "user_id": str(target_user.id),
                "application_id": draft["id"],
                "type": "docs_request",
                "title": title,
                "body": "Загрузите справку о гос. регистрации.",
            },
        )
    await db_session.commit()

    response = await client.get(f"/api/v1/applications/{draft['id']}", headers=_headers(user))

    notifications = response.json()["notifications"]
    assert len(notifications) == 1
    assert notifications[0]["title"] == "Нужны документы"
    assert notifications[0]["read_at"] is None


async def test_detail_idor_returns_404(client, db_session):
    """Чужая заявка отвечает 404 (не 403), чтобы не раскрывать существование id."""
    org = await seed_organization(db_session)
    owner = await seed_user(db_session)
    stranger = await seed_user(db_session)
    service_row = await seed_service(db_session, org.id)
    draft = await _create_draft(client, owner, service_row)

    response = await client.get(f"/api/v1/applications/{draft['id']}", headers=_headers(stranger))

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_detail_unknown_id_returns_404(client, db_session):
    user = await seed_user(db_session)
    response = await client.get(f"/api/v1/applications/{uuid.uuid4()}", headers=_headers(user))
    assert response.status_code == 404
