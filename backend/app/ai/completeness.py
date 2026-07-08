"""Application-completeness copilot (SPEC.md §7.1 "Проверка полноты заявки перед
отправкой": подсказки, что стоит проверить/дополнить — советует, НЕ блокирует
`/submit`).

Deliberately mirrors `app.ai.intake`'s split: a pure, offline `rule_based_suggestions`
(the same required-and-visible check `app.engine.runtime.validate` already performs for
real validation, just reworded as advice) is always available and is exactly what
`MockLLMProvider` effectively produces (SPEC.md §7.3 "keyword/rule-fallback без LLM" —
same spirit as `app.ai.intake.keyword_match`); a configured real provider gets one
chance to rephrase those same gaps in nicer prose, and any failure — network error,
garbled JSON, an invented field name — degrades back to the rule-based list rather than
ever blocking submission or 500ing.
"""
from __future__ import annotations

import json

from app.ai.prompts.completeness import SYSTEM_PROMPT, build_prompt
from app.ai.provider import LLMProvider
from app.engine.rules import effects


def _visible_required_empty_labels(definition, data: dict, stage_key: str | None) -> list[str]:
    applied, _trace = effects(definition.rules, data)
    labels: list[str] = []
    for stage in definition.stages:
        if stage_key is not None and stage.key != stage_key:
            continue
        for step in stage.steps:
            for field in step.fields:
                visible = applied.get(field.key) != "hide"
                required = (field.required or applied.get(field.key) == "require") and applied.get(field.key) != "optional"
                if not (visible and required):
                    continue
                if data.get(field.key) in (None, "", []):
                    labels.append(field.label)
    return labels


def rule_based_suggestions(definition, data: dict, stage_key: str | None = None) -> list[str]:
    """Pure, offline, non-LLM suggestions — same required/visible rule
    `app.engine.runtime.validate` applies, worded as advice rather than an error code."""
    return [
        f"Рекомендуем проверить: «{label}» — поле пока не заполнено."
        for label in _visible_required_empty_labels(definition, data, stage_key)
    ]


def _parse_llm_suggestions(text: str) -> list[str]:
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("completeness response must be a JSON array")
    results = [str(item).strip() for item in parsed if str(item).strip()]
    if not results:
        raise ValueError("empty suggestions list")
    return results


async def completeness_suggestions(
    provider: LLMProvider, definition, data: dict, stage_key: str | None = None
) -> tuple[list[str], str]:
    """Returns `(suggestions, method)`, `method` being `"llm"` or `"rule"`. Nothing to
    say (every required visible field is filled) short-circuits to an empty list
    without ever calling the provider, mock or real."""
    base = rule_based_suggestions(definition, data, stage_key)
    if provider.name != "mock" and base:
        try:
            result = await provider.complete(system=SYSTEM_PROMPT, prompt=build_prompt(base))
            return _parse_llm_suggestions(result.text), "llm"
        except Exception:  # noqa: BLE001 - any provider/parse failure degrades, never blocks/500s
            pass
    return base, "rule"
