"""Demo «без логинов» mode (config.open_access, ENV BAITEREK_OPEN_ACCESS).

With the flag on, an unknown random X-User-Id is auto-provisioned and role gates on the
admin contour are lifted — so the public стенд is usable end-to-end without a login.
The flag defaults off, so every other test keeps exercising the real auth/RBAC path.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

import app.api.deps as deps


@pytest.fixture
def open_access(monkeypatch):
    monkeypatch.setattr(deps, "settings", lambda: SimpleNamespace(open_access=True))


@pytest.mark.asyncio(loop_scope="session")
async def test_unknown_user_is_rejected_without_open_access(client):
    # Baseline: the real auth path still 401s an unknown id (flag off by default).
    response = await client.get("/api/v1/applications", headers={"X-User-Id": str(uuid.uuid4())})
    assert response.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
async def test_open_access_auto_provisions_unknown_user(open_access, client):
    fresh_id = str(uuid.uuid4())
    response = await client.get("/api/v1/applications", headers={"X-User-Id": fresh_id})
    assert response.status_code == 200
    assert response.json() == {"items": []}
    # Idempotent: the same id on a second call does not blow up on a duplicate insert.
    again = await client.get("/api/v1/applications", headers={"X-User-Id": fresh_id})
    assert again.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_open_access_lifts_admin_role_gate(open_access, client):
    # A brand-new (non-author) visitor can reach the constructor registry.
    response = await client.get("/api/v1/admin/definitions", headers={"X-User-Id": str(uuid.uuid4())})
    assert response.status_code == 200
