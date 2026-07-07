"""`AnthropicProvider` — the real `LLMProvider` (SPEC.md §7.3 "AnthropicProvider (основная)").

Calls the Anthropic Messages API directly over `httpx` (already a dependency for the
FastAPI test client) instead of adding the `anthropic` SDK as a new dependency — the
Messages API is a single plain HTTP call and structured output here just means "the
model returns JSON in its text", which needs no SDK-specific feature.

Never exercised by the test suite (SPEC.md §7.3 "контрактные тесты ... без сети" /
`BAITEREK_LLM_PROVIDER` defaults to `mock`) — it only runs against the real API key
from `ANTHROPIC_API_KEY` on the deployed stand.
"""
from __future__ import annotations

import httpx

from app.ai.provider import LLMResult

_API_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"
_MAX_TOKENS = 4096
_TIMEOUT_SECONDS = 60.0


class AnthropicProviderError(RuntimeError):
    """Raised when the Anthropic API call itself fails (network/auth/rate-limit/shape).

    Callers (`app.ai.generation`, `app.ai.intake`) treat this as "the provider is
    unusable right now" and degrade gracefully rather than propagate a 500 — see
    `app.ai.provider.LLMProvider.complete`'s docstring.
    """


class AnthropicProvider:
    """Real `LLMProvider` backed by the Anthropic Messages API."""

    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-sonnet-5") -> None:
        self._api_key = api_key
        self._model = model

    async def complete(self, *, system: str, prompt: str) -> LLMResult:
        payload = {
            "model": self._model,
            "max_tokens": _MAX_TOKENS,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.post(_API_URL, headers=headers, json=payload)
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AnthropicProviderError(f"Anthropic API call failed: {exc}") from exc

        blocks = body.get("content", [])
        text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        if not text:
            raise AnthropicProviderError("Anthropic API returned no text content")
        return LLMResult(text=text, provider=self.name)
