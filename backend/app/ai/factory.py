"""Provider selection (SPEC.md §7.3 "выбор через ENV LLM_PROVIDER").

`resolve_provider` is what the API routes call: it picks the provider named by
`BAITEREK_LLM_PROVIDER` (default `mock`) and, only when that provider is `anthropic`,
checks the daily budget first — degrading to `MockLLMProvider` (and reporting
`degraded=True`) once `BAITEREK_LLM_DAILY_LIMIT` calls have already happened today
(SPEC.md §7.3 "При исчерпании — graceful-фолбэк на MockLLMProvider ... функциональность
портала не деградирует"). Checking the mock provider's own budget would be pointless —
it never spends anything — so `degraded` is always `False` when mock was already the
configured choice.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.anthropic_provider import AnthropicProvider
from app.ai.budget import daily_limit_exceeded
from app.ai.mock_provider import MockLLMProvider
from app.ai.provider import LLMProvider
from app.config import settings


def build_configured_provider() -> LLMProvider:
    """The provider `BAITEREK_LLM_PROVIDER` asks for, ignoring the budget."""
    config = settings()
    if config.llm_provider == "anthropic" and config.anthropic_api_key:
        return AnthropicProvider(api_key=config.anthropic_api_key, model=config.anthropic_model)
    return MockLLMProvider()


async def resolve_provider(session: AsyncSession) -> tuple[LLMProvider, bool]:
    """Returns `(provider, degraded)`. `degraded=True` means the budget forced a
    downgrade to `MockLLMProvider` even though a real provider is configured."""
    configured = build_configured_provider()
    if configured.name == "mock":
        return configured, False
    if await daily_limit_exceeded(session, settings().llm_daily_limit):
        return MockLLMProvider(), True
    return configured, False
