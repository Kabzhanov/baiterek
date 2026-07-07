"""`app.ai.budget` (SPEC.md §7.3 daily budget, counted from `audit_log` since no new
migration/table is in scope). `audit_log` is append-only and NOT truncated between
tests by `tests/conftest.py`'s `_clean_database` fixture (deliberately — it is meant to
accumulate), so assertions here compare deltas against a measured baseline rather than
absolute counts, to stay correct regardless of what earlier tests in the same run wrote.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.ai.budget import count_ai_calls_today, daily_limit_exceeded, log_ai_call
from app.ai.factory import resolve_provider
from app.models import AuditLog

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_count_ai_calls_today_ignores_yesterday_and_other_actions(db_session):
    baseline = await count_ai_calls_today(db_session)
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1, hours=1)
    db_session.add(AuditLog(action="ai_call", entity_type="ai_generate", created_at=yesterday))
    db_session.add(AuditLog(action="ai_call", entity_type="ai_generate", created_at=now))
    db_session.add(AuditLog(action="application_status_change", entity_type="application", created_at=now))
    await db_session.commit()

    count = await count_ai_calls_today(db_session)

    assert count == baseline + 1


async def test_daily_limit_exceeded_at_the_boundary(db_session):
    baseline = await count_ai_calls_today(db_session)
    for _ in range(3):
        await log_ai_call(db_session, user_id=None, kind="ai_generate", provider="mock", degraded=False)

    assert await daily_limit_exceeded(db_session, limit=baseline + 3) is True
    assert await daily_limit_exceeded(db_session, limit=baseline + 4) is False


async def test_resolve_provider_never_degrades_when_configured_provider_is_mock(db_session):
    # `BAITEREK_LLM_PROVIDER` is unset in the test environment, so the configured
    # provider is already `mock` — `resolve_provider` must short-circuit and never even
    # look at the budget in that case (checking it would be pointless: mock never
    # spends anything). Piling up AuditLog rows here proves it really is a short-circuit.
    for _ in range(5):
        await log_ai_call(db_session, user_id=None, kind="ai_generate", provider="mock", degraded=False)

    provider, degraded = await resolve_provider(db_session)

    assert provider.name == "mock"
    assert degraded is False
