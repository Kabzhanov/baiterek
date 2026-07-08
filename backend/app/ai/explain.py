"""«Объяснить простыми словами» (SPEC.md §7.1): a published service's `Definition.meta`
→ `LLMProvider` → a short plain-language paraphrase of the conditions plus what an
applicant will need, no legalese.

Mirrors `app.ai.generation`'s "always go through `provider.complete`, mock included"
shape (SPEC.md §7.3 "MockLLMProvider детерминированные ответы для офлайн-демо") rather
than `app.ai.intake`'s "mock bypasses the LLM protocol entirely" shape: there is no
separate rule-based algorithm for "explain this service in your own words", so
`MockLLMProvider` itself answers the prompt deterministically
(`app.ai.mock_provider._explain_service`) exactly like it fakes `generate_definition_json`.
"""
from __future__ import annotations

from app.ai.mock_provider import MockLLMProvider
from app.ai.prompts.explain_service import SYSTEM_PROMPT, build_prompt
from app.ai.provider import LLMProvider


async def explain_service(provider: LLMProvider, meta: dict) -> tuple[str, bool]:
    """Returns `(text, degraded)`. `degraded=True` only when the *call itself* failed
    (network/auth/garbled response) and a `MockLLMProvider` paraphrase was substituted
    instead — additive with (not a replacement for) the budget-forced `degraded`
    `app.ai.factory.resolve_provider` may already report for the same request."""
    prompt = build_prompt(meta)
    try:
        result = await provider.complete(system=SYSTEM_PROMPT, prompt=prompt)
        text = result.text.strip()
        if not text:
            raise ValueError("empty explanation")
        return text, False
    except Exception:  # noqa: BLE001 - any provider failure degrades to Mock, never 500s
        if provider.name == "mock":
            raise  # MockLLMProvider must never fail this path; a bug here is a real bug, not "network down"
        fallback = await MockLLMProvider().complete(system=SYSTEM_PROMPT, prompt=prompt)
        return fallback.text.strip(), True
