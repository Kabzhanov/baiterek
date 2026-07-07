"""Service Definition generation from free text (SPEC.md §5.3, §7.2;
docs/IMPLEMENTATION_PLAN.md §9 "AI generator": "text/document → LLM → JSON extraction
→ JSON Schema → semantic validation → [VERIFY] warnings → draft").

Pipeline: prompt → `LLMProvider` → JSON parse → `app.schemas.definition.ServiceDefinition`
validation → up to `MAX_REPAIR_ATTEMPTS` self-correction retries with the validation
error fed back into the prompt → the first schema-valid result wins, or `GenerationFailed`
if the model never produces one ("invalid output не портит draft; retry ограничен").

The raw, validated-but-NOT-re-serialized `dict` is what gets returned/persisted (not
`ServiceDefinitionSchema(...).model_dump()`): `app.schemas.definition.Meta` only models
`title/description/labels_plain` and silently drops the richer catalog-card fields
(`org, category, summary_plain, conditions, ...` — see `app/api/services.py`'s docstring
for the same gap). Re-serializing through the schema would strip those fields from an
AI-generated service before it ever reaches the catalog; validating-then-keeping-the-raw-dict
is exactly what `app/api/definitions.py`'s existing `/admin/definitions/import` already
does, so this mirrors that precedent.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.ai.prompts.generate_definition import SYSTEM_PROMPT, build_prompt, build_repair_prompt
from app.ai.provider import LLMProvider
from app.schemas.definition import ServiceDefinition as ServiceDefinitionSchema

MAX_REPAIR_ATTEMPTS = 2  # SPEC.md §7.2 "авторепромпт (до 2 ретраев)"


@dataclass(frozen=True)
class GenerationOutcome:
    definition: dict
    warnings: list[str] = field(default_factory=list)
    attempts: int = 1


class GenerationFailed(Exception):
    """Raised when no attempt (initial + retries) produced a schema-valid Definition."""

    def __init__(self, errors: list[dict], attempts: int) -> None:
        self.errors = errors
        self.attempts = attempts
        super().__init__("AI generation did not produce a schema-valid Service Definition")


def _parse_json_object(text: str) -> dict:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"response is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("response JSON must be an object")
    return parsed


async def generate_definition_json(provider: LLMProvider, text: str) -> GenerationOutcome:
    warnings: list[str] = []
    last_errors: list[dict] = []
    total_attempts = MAX_REPAIR_ATTEMPTS + 1
    for attempt in range(1, total_attempts + 1):
        is_repair = attempt > 1
        prompt = (
            build_repair_prompt(text, json.dumps(last_errors, ensure_ascii=False))
            if is_repair
            else build_prompt(text)
        )
        result = await provider.complete(system=SYSTEM_PROMPT, prompt=prompt)

        try:
            candidate = _parse_json_object(result.text)
        except ValueError as exc:
            last_errors = [{"msg": str(exc)}]
            if is_repair:
                warnings.append(f"repair attempt {attempt - 1}: response was not valid JSON")
            continue

        try:
            ServiceDefinitionSchema.model_validate(candidate)
        except ValidationError as exc:
            last_errors = [dict(err) for err in exc.errors(include_context=False, include_url=False)]
            if is_repair:
                warnings.append(f"repair attempt {attempt - 1}: still failed schema validation")
            continue

        if is_repair:
            warnings.append(f"schema-valid after {attempt - 1} repair attempt(s)")
        return GenerationOutcome(definition=candidate, warnings=warnings, attempts=attempt)

    raise GenerationFailed(errors=last_errors, attempts=total_attempts)
