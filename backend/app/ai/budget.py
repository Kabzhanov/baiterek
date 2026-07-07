"""Daily AI-call budget (SPEC.md §7.3 "Бюджет LLM на публичном стенде"; task scope
explicitly forbids new migrations, so there is no dedicated counter table — the count
is derived from `audit_log` rows this module itself writes).

Every AI call (`app.ai.generation.generate_definition_json` via the `/generate`
endpoint, `app.ai.intake.match_services` via `/intake/match`) is logged as one
`audit_log` row with `action="ai_call"` and NO free text / user input in `after` (only
the resolved provider name, whether it degraded, and non-PII counters) — SPEC.md §7.3
"Логирование AI-вызовов в audit_log (без персональных данных)".

The cap is a calendar-day (UTC) bucket, not a rolling 24h window: "суточный потолок"
reads naturally as "per day", and a fixed UTC-midnight boundary is simple to reason
about and to test (insert rows with `created_at` before/after `today`).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog

AI_CALL_ACTION = "ai_call"


def _start_of_today_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def count_ai_calls_today(session: AsyncSession) -> int:
    stmt = select(func.count()).select_from(AuditLog).where(
        AuditLog.action == AI_CALL_ACTION,
        AuditLog.created_at >= _start_of_today_utc(),
    )
    return int(await session.scalar(stmt) or 0)


async def daily_limit_exceeded(session: AsyncSession, limit: int) -> bool:
    return await count_ai_calls_today(session) >= limit


async def log_ai_call(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    kind: str,
    provider: str,
    degraded: bool,
    method: str | None = None,
) -> None:
    """Append the audit trail row and commit the session (callers add this last, after
    any other row for the same request — e.g. a freshly-created draft — so the AI call
    is logged atomically together with its side effect, success or failure alike: a
    generation attempt that ultimately fails validation still consumed the daily budget).
    """
    after: dict[str, object] = {"provider": provider, "degraded": degraded}
    if method is not None:
        after["method"] = method
    session.add(
        AuditLog(
            user_id=user_id,
            action=AI_CALL_ACTION,
            entity_type=kind,
            entity_id=None,
            before=None,
            after=after,
        )
    )
    await session.commit()
