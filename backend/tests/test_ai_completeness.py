"""Unit tests for `app.ai.completeness` — the offline rule-based suggestions (SPEC.md
§7.1 "Проверка полноты заявки") plus its LLM/degrade routing. No DB, no network.
"""
from __future__ import annotations

import pytest

from app.ai.completeness import completeness_suggestions, rule_based_suggestions
from app.ai.mock_provider import MockLLMProvider
from app.ai.provider import LLMResult
from app.schemas.definition import ServiceDefinition
from tests.conftest import build_definition_json

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _definition(**overrides) -> ServiceDefinition:
    return ServiceDefinition.model_validate(build_definition_json(**overrides))


class _StubProvider:
    def __init__(self, name: str, *, text: str | None = None, error: Exception | None = None) -> None:
        self.name = name
        self._text = text
        self._error = error

    async def complete(self, *, system: str, prompt: str) -> LLMResult:
        if self._error is not None:
            raise self._error
        return LLMResult(text=self._text if self._text is not None else "[]", provider=self.name)


def test_rule_based_suggestions_lists_only_empty_required_visible_fields():
    definition = _definition()  # f1 is the only required field in the shared fixture

    suggestions = rule_based_suggestions(definition, {})

    assert len(suggestions) == 1
    assert "Поле 1" in suggestions[0]
    assert "Рекомендуем проверить" in suggestions[0]


def test_rule_based_suggestions_is_empty_once_required_field_is_filled():
    definition = _definition()

    suggestions = rule_based_suggestions(definition, {"f1": "ТОО Ромашка"})

    assert suggestions == []


def test_rule_based_suggestions_restricts_to_the_given_stage():
    two_stage = build_definition_json(
        stages=[
            {
                "key": "stage1",
                "title": "Этап I",
                "steps": [
                    {
                        "key": "s1",
                        "title": "Шаг I",
                        "fields": [{"key": "a", "label": "Поле A", "type": "text", "required": True}],
                    }
                ],
            },
            {
                "key": "stage2",
                "title": "Этап II",
                "steps": [
                    {
                        "key": "s2",
                        "title": "Шаг II",
                        "fields": [{"key": "b", "label": "Поле B", "type": "text", "required": True}],
                    }
                ],
            },
        ],
        computed=[],
    )
    definition = ServiceDefinition.model_validate(two_stage)

    suggestions = rule_based_suggestions(definition, {}, stage_key="stage1")

    assert any("Поле A" in s for s in suggestions)
    assert not any("Поле B" in s for s in suggestions)


async def test_completeness_suggestions_with_mock_provider_never_calls_llm():
    definition = _definition()

    suggestions, method = await completeness_suggestions(MockLLMProvider(), definition, {})

    assert method == "rule"
    assert suggestions == rule_based_suggestions(definition, {})


async def test_completeness_suggestions_short_circuits_when_nothing_is_missing():
    definition = _definition()

    suggestions, method = await completeness_suggestions(MockLLMProvider(), definition, {"f1": "заполнено"})

    assert suggestions == []
    assert method == "rule"


async def test_completeness_suggestions_uses_real_provider_response_when_it_succeeds():
    definition = _definition()
    provider = _StubProvider(
        "anthropic", text='["Рекомендуем проверить: «Поле 1» — обязательно для расчёта суммы"]'
    )

    suggestions, method = await completeness_suggestions(provider, definition, {})

    assert method == "llm"
    assert suggestions == ["Рекомендуем проверить: «Поле 1» — обязательно для расчёта суммы"]


async def test_completeness_suggestions_degrades_to_rule_based_when_real_provider_fails():
    definition = _definition()
    provider = _StubProvider("anthropic", error=RuntimeError("network down"))

    suggestions, method = await completeness_suggestions(provider, definition, {})

    assert method == "rule"
    assert suggestions == rule_based_suggestions(definition, {})


async def test_completeness_suggestions_degrades_to_rule_based_on_garbled_llm_json():
    definition = _definition()
    provider = _StubProvider("anthropic", text="this is not json")

    suggestions, method = await completeness_suggestions(provider, definition, {})

    assert method == "rule"
    assert suggestions == rule_based_suggestions(definition, {})
