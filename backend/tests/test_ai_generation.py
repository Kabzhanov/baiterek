"""Unit tests for `app.ai.generation` against `MockLLMProvider` directly — no DB, no
network (SPEC.md §7.3 "контрактные тесты ... без сети").
"""
from __future__ import annotations

import pytest

from app.ai.generation import GenerationFailed, generate_definition_json
from app.ai.mock_provider import MockLLMProvider
from app.schemas.definition import ServiceDefinition as ServiceDefinitionSchema

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_generate_happy_path_first_attempt():
    provider = MockLLMProvider()

    outcome = await generate_definition_json(provider, "Кредит для малого бизнеса до 10 млн тенге")

    assert outcome.attempts == 1
    assert outcome.warnings == []
    ServiceDefinitionSchema.model_validate(outcome.definition)  # does not raise
    assert outcome.definition["meta"]["title"]


async def test_generate_retries_once_then_succeeds():
    provider = MockLLMProvider()

    outcome = await generate_definition_json(provider, "AI_TEST_INVALID_ONCE Кредит для стартапов")

    assert outcome.attempts == 2
    assert outcome.warnings, "a repair happened, so there should be a warning about it"
    ServiceDefinitionSchema.model_validate(outcome.definition)


async def test_generate_exhausts_retries_and_raises_honest_failure():
    provider = MockLLMProvider()

    with pytest.raises(GenerationFailed) as exc_info:
        await generate_definition_json(provider, "AI_TEST_INVALID_ALWAYS Гарантия по кредиту")

    assert exc_info.value.attempts == 3  # 1 initial + 2 repairs (SPEC.md §7.2 "до 2 ретраев")
    assert exc_info.value.errors
