"""Mock eGov IDP adapter (SPEC.md §8): "экран «Вход через eGov» → выбор тестового
пользователя (ИП Тестов / ТОО «Демо») → JWT". The MVP's auth boundary is already the
`X-User-Id` header read by `app/api/deps.get_current_user_id` (see that module's
docstring) — a real JWT-issuing IDP would replace that dependency later without
touching this adapter's contract. This module's job is only the "выбор тестового
пользователя" step: turn a fixed, fully synthetic test identity into a `users` row
(get-or-create) so the frontend can hand its `id` back as `X-User-Id`.

Test users and their ИИН/БИН are entirely synthetic (SPEC.md §6/§9 "test users
полностью синтетические") — no real person or organization is represented.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserRole


@dataclass(frozen=True)
class MockTestUser:
    key: str
    label: str
    iin_bin: str
    role: UserRole
    profile: dict


# Полностью синтетические тестовые личности (SPEC.md §8, §9). ИИН/БИН не принадлежат
# реальным людям/организациям — совпадения случайны и намеренно шаблонны (990101400000 и т.п.).
TEST_USERS: tuple[MockTestUser, ...] = (
    MockTestUser(
        key="ip_testov",
        label="ИП Тестов Тест Тестович",
        iin_bin="900101300123",
        role=UserRole.ENTREPRENEUR,
        profile={"name": "Тестов Тест Тестович", "applicant_type": "ИП"},
    ),
    MockTestUser(
        key="too_demo",
        label='ТОО «Демо»',
        iin_bin="990101400000",
        role=UserRole.ENTREPRENEUR,
        profile={"name": 'ТОО «Демо»', "applicant_type": "ТОО"},
    ),
)


class EgovIdpPort(Protocol):
    """Interface a real eGov IDP adapter must satisfy."""

    def list_test_users(self) -> tuple[MockTestUser, ...]: ...

    async def login(self, session: AsyncSession, test_user_key: str) -> User: ...


class MockEgovIdpAdapter:
    """Имитация eGov IDP — выбор тестового пользователя вместо реального входа."""

    def list_test_users(self) -> tuple[MockTestUser, ...]:
        return TEST_USERS

    async def login(self, session: AsyncSession, test_user_key: str) -> User:
        """Get-or-create the `users` row for a test identity. Raises `KeyError` for an
        unknown `test_user_key` — callers translate that into a 404 `ApiError`."""
        candidate = next((item for item in TEST_USERS if item.key == test_user_key), None)
        if candidate is None:
            raise KeyError(test_user_key)

        existing = await session.scalar(select(User).where(User.iin_bin == candidate.iin_bin))
        if existing is not None:
            return existing

        user = User(iin_bin=candidate.iin_bin, role=candidate.role, profile=candidate.profile)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


__all__ = ["EgovIdpPort", "MockEgovIdpAdapter", "MockTestUser", "TEST_USERS"]
