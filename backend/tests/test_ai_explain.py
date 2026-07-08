"""Unit tests for `app.ai.explain` — deterministic `MockLLMProvider` paraphrase plus
real-provider success/degrade routing (SPEC.md §7.1 "Объяснить простыми словами",
§7.3 "MockLLMProvider детерминированные ответы"). No DB, no network.
"""
from __future__ import annotations

import pytest

from app.ai.explain import explain_service
from app.ai.mock_provider import MockLLMProvider
from app.ai.provider import LLMResult

pytestmark = pytest.mark.asyncio(loop_scope="session")

_META = {
    "title": "Оборотное кредитование для МСБ",
    "summary_plain": "Кредит на пополнение оборотных средств для малого и среднего бизнеса.",
    "conditions": [{"label": "Сумма", "value": "до 100 000 000 ₸"}],
    "documents_checklist": ["Справка о гос. регистрации", "Финансовая отчётность"],
    "result": "Решение о финансировании",
    "sla_days": 15,
}


class _StubProvider:
    """Minimal `LLMProvider`-shaped stub, standing in for `AnthropicProvider` without
    touching the network — mirrors how `test_ai_intake.py` exercises `match_services`'s
    routing with just `MockLLMProvider`, but here we also need a *non*-mock name to
    reach the "real provider" branch."""

    def __init__(self, name: str, *, text: str | None = None, error: Exception | None = None) -> None:
        self.name = name
        self._text = text
        self._error = error

    async def complete(self, *, system: str, prompt: str) -> LLMResult:
        if self._error is not None:
            raise self._error
        return LLMResult(text=self._text or "", provider=self.name)


async def test_explain_with_mock_provider_is_deterministic():
    provider = MockLLMProvider()

    text1, degraded1 = await explain_service(provider, _META)
    text2, degraded2 = await explain_service(provider, _META)

    assert text1 == text2
    assert degraded1 is False
    assert degraded2 is False


async def test_explain_mock_paraphrases_meta_without_raw_json():
    provider = MockLLMProvider()

    text, _degraded = await explain_service(provider, _META)

    assert "{" not in text  # not a raw JSON dump — a real paraphrase
    assert "Оборотное кредитование" in text
    assert "Справка о гос. регистрации" in text
    assert "15" in text  # sla_days worked into a sentence


async def test_explain_with_empty_meta_still_returns_non_empty_text():
    provider = MockLLMProvider()

    text, degraded = await explain_service(provider, {})

    assert text
    assert degraded is False


async def test_explain_uses_real_provider_response_when_it_succeeds():
    provider = _StubProvider("anthropic", text="  Простое объяснение услуги.  ")

    text, degraded = await explain_service(provider, _META)

    assert text == "Простое объяснение услуги."
    assert degraded is False


async def test_explain_falls_back_to_mock_when_real_provider_fails():
    expected_text, _ = await explain_service(MockLLMProvider(), _META)
    failing_provider = _StubProvider("anthropic", error=RuntimeError("network down"))

    text, degraded = await explain_service(failing_provider, _META)

    assert text == expected_text
    assert degraded is True


async def test_explain_falls_back_to_mock_when_real_provider_returns_empty_text():
    expected_text, _ = await explain_service(MockLLMProvider(), _META)
    provider = _StubProvider("anthropic", text="   ")

    text, degraded = await explain_service(provider, _META)

    assert text == expected_text
    assert degraded is True
