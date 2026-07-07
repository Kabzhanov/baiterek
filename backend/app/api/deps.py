"""Request-scoped dependencies for the v1 API.

Auth is intentionally a stand-in (SPEC.md §8 "mock eGov IDP"): the caller sends an
`X-User-Id` header naming an existing `users.id`. Isolating it in one dependency means
swapping in the real eGov IDP later only touches this file, not every router.
"""
from __future__ import annotations

import uuid

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError
from app.db import get_session
from app.models import User, UserRole


async def get_current_user_id(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    session: AsyncSession = Depends(get_session),
) -> uuid.UUID:
    if not x_user_id:
        raise ApiError(401, "unauthorized", "X-User-Id header is required", {})
    try:
        user_id = uuid.UUID(x_user_id)
    except ValueError as exc:
        raise ApiError(401, "unauthorized", "X-User-Id must be a UUID", {}) from exc
    known = await session.scalar(select(User.id).where(User.id == user_id))
    if known is None:
        raise ApiError(401, "unauthorized", "unknown user", {})
    return user_id


def require_role(*roles: UserRole):
    """Dependency factory: 403s unless the authenticated user's role is one of `roles`.

    Kept generic (one factory, not one `get_current_*_user_id` per role) because both
    the admin status-change endpoint (`app/api/admin.py`, ADMIN only) and the
    Definition import endpoint (`app/api/definitions.py`, ADMIN or AUTHOR — SPEC.md
    §5.4 "author — конструктор своей организации") need the same shape of check with a
    different allowed set.
    """

    async def _dependency(
        user_id: uuid.UUID = Depends(get_current_user_id),
        session: AsyncSession = Depends(get_session),
    ) -> uuid.UUID:
        role = await session.scalar(select(User.role).where(User.id == user_id))
        if role not in roles:
            raise ApiError(
                403,
                "forbidden",
                "User role is not allowed to perform this action",
                {"required_roles": [item.value for item in roles]},
            )
        return user_id

    return _dependency
