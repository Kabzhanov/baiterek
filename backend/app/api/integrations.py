"""Mock ЕИШ endpoints (SPEC.md §8): eGov IDP login, ГБД ЮЛ lookup, ЭЦП sign.

Every response carries `mock: true` plus a human `disclaimer` — SPEC.md §8's "честная
пометка" requirement applies at the HTTP boundary, not just in code comments, so a
frontend/reviewer can tell at a glance that no real government system was called.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.api.errors import ApiError
from app.db import get_session
from app.integrations.ecp_sign import MockEcpSignAdapter
from app.integrations.egov_idp import TEST_USERS, MockEgovIdpAdapter
from app.integrations.gbd_ul import MockGbdUlAdapter
from app.models import Application

router = APIRouter(tags=["integrations"])

_egov_idp = MockEgovIdpAdapter()
_gbd_ul = MockGbdUlAdapter()
_ecp_sign = MockEcpSignAdapter()


# ---------------------------------------------------------------------------
# egov_idp — mock auth (SPEC.md §8)
# ---------------------------------------------------------------------------


class MockEgovUserOut(BaseModel):
    key: str
    label: str
    role: str


class MockEgovLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_user_key: str


class MockEgovLoginOut(BaseModel):
    user_id: uuid.UUID
    iin_bin: str
    role: str
    mock: bool = True
    disclaimer: str = "Имитация eGov IDP: выбран тестовый пользователь, это не реальная государственная авторизация."


@router.get("/auth/mock-egov/users", response_model=list[MockEgovUserOut])
async def list_mock_egov_users() -> list[MockEgovUserOut]:
    """Test identities the "Вход через eGov" screen offers (SPEC.md §8)."""
    return [MockEgovUserOut(key=item.key, label=item.label, role=item.role.value) for item in TEST_USERS]


@router.post("/auth/mock-egov", response_model=MockEgovLoginOut)
async def mock_egov_login(
    payload: MockEgovLoginRequest, session: AsyncSession = Depends(get_session)
) -> MockEgovLoginOut:
    """Get-or-create the chosen test identity's `users` row and hand back its id — the
    frontend then sends that id as `X-User-Id` on every subsequent call
    (`app/api/deps.get_current_user_id`)."""
    try:
        user = await _egov_idp.login(session, payload.test_user_key)
    except KeyError as exc:
        raise ApiError(
            404, "unknown_test_user", "Unknown mock eGov test user", {"test_user_key": payload.test_user_key}
        ) from exc
    return MockEgovLoginOut(user_id=user.id, iin_bin=user.iin_bin, role=user.role.value)


# ---------------------------------------------------------------------------
# gbd_ul — mock company registry lookup (SPEC.md §8)
# ---------------------------------------------------------------------------


class GbdUlOut(BaseModel):
    bin: str
    name: str
    oked: str
    oked_name: str
    address: str
    director: str
    mock: bool = True
    disclaimer: str = "Имитация ГБД ЮЛ: тестовый справочник, а не реальный госреестр."


@router.get("/integrations/gbd-ul/{bin_value}", response_model=GbdUlOut)
async def gbd_ul_lookup(bin_value: str) -> GbdUlOut:
    """Prefill source for `field.prefill: "integration:gbd_ul.bin"` (SPEC.md §3.2)."""
    record = _gbd_ul.lookup(bin_value)
    if record is None:
        raise ApiError(404, "not_found", "Company not found in mock ГБД ЮЛ directory", {"bin": bin_value})
    return GbdUlOut(
        bin=record.bin,
        name=record.name,
        oked=record.oked,
        oked_name=record.oked_name,
        address=record.address,
        director=record.director,
    )


# ---------------------------------------------------------------------------
# ecp_sign — mock digital signature (SPEC.md §8)
# ---------------------------------------------------------------------------


class EcpSignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    application_id: uuid.UUID


class EcpSignOut(BaseModel):
    application_id: uuid.UUID
    signature_meta: dict
    mock: bool = True
    disclaimer: str = "Имитация ЭЦП НУЦ РК: тестовая подпись, а не настоящая криптография."


@router.post("/integrations/ecp/sign", response_model=EcpSignOut)
async def ecp_sign(
    payload: EcpSignRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> EcpSignOut:
    """Signs an application on behalf of its owner. 404s (not 403) on ownership
    mismatch, matching the IDOR-avoidance pattern `app/api/applications.py` uses for
    every owned-resource lookup."""
    application = await session.get(Application, payload.application_id)
    if application is None or application.user_id != user_id:
        raise ApiError(404, "not_found", "Application not found", {})

    meta = _ecp_sign.sign(payload.application_id, signer_label=str(user_id))
    return EcpSignOut(
        application_id=payload.application_id,
        signature_meta={
            "signed_by": meta.signed_by,
            "signed_at": meta.signed_at.isoformat(),
            "algorithm": meta.algorithm,
            "serial_number": meta.serial_number,
            "mock": meta.mock,
        },
    )
