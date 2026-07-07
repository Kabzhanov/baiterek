"""Deterministic, offline `LLMProvider` (SPEC.md §7.3 "MockLLMProvider детерминированные
ответы для офлайн-демо и тестов"; docs/IMPLEMENTATION_PLAN.md §9 "MockLLMProvider
детерминирован для CI/fallback").

This is the default provider (`BAITEREK_LLM_PROVIDER` unset) and the automatic
fallback once the daily AI budget is exhausted (`app.ai.factory.resolve_provider`).
It never makes a network call, so the whole AI-contract test suite runs offline.

Two markers recognised inside the `SOURCE_TEXT:` section of a generation prompt
(never meaningful in real administrator input — documented here rather than hidden,
in the spirit of SPEC.md's №230-VIII explainability requirement):

- `AI_TEST_INVALID_ONCE` — return deliberately-invalid JSON on the first (non-repair)
  attempt only, then a valid definition on any repair attempt. Exercises
  `app.ai.generation`'s retry loop deterministically, without depending on a real
  model's non-determinism.
- `AI_TEST_INVALID_ALWAYS` — return invalid JSON on every attempt, so the retry budget
  is exhausted and the caller has to answer an honest 422.

`/intake/match` does not go through this provider's text-in/text-out protocol at all
when `provider.name == "mock"` — `app.ai.intake.match_services` calls
`app.ai.intake.keyword_match` directly. That keeps the "keyword-fallback без LLM" path
(SPEC.md §7.1) a genuinely separate, auditable algorithm rather than a JSON string this
class would otherwise have to fake being an LLM to produce.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata

from app.ai.provider import LLMResult

_INVALID_ONCE = "AI_TEST_INVALID_ONCE"
_INVALID_ALWAYS = "AI_TEST_INVALID_ALWAYS"
_SOURCE_MARKER = "SOURCE_TEXT:\n"


def _slugify(text: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return slug or fallback


def _extract_source_text(prompt: str) -> str:
    index = prompt.find(_SOURCE_MARKER)
    return prompt[index + len(_SOURCE_MARKER) :].strip() if index != -1 else prompt.strip()


class MockLLMProvider:
    """Offline, deterministic `LLMProvider` — see module docstring."""

    name = "mock"

    async def complete(self, *, system: str, prompt: str) -> LLMResult:
        if system.startswith("TASK: generate_service_definition"):
            return LLMResult(text=self._generate_definition(prompt), provider=self.name)
        # No other task currently routes through the mock's text protocol (see module
        # docstring re: /intake/match), but returning valid empty JSON rather than
        # raising keeps this provider a safe default for any future caller.
        return LLMResult(text="{}", provider=self.name)

    def _generate_definition(self, prompt: str) -> str:
        is_repair = prompt.startswith("REPAIR_ATTEMPT: true")
        source_text = _extract_source_text(prompt)
        if not is_repair and _INVALID_ONCE in source_text:
            return json.dumps({"not_a_valid_service_definition": True})
        if _INVALID_ALWAYS in source_text:
            return json.dumps({"not_a_valid_service_definition": True})

        cleaned = source_text.replace(_INVALID_ONCE, "").replace(_INVALID_ALWAYS, "").strip() or "Услуга"
        first_line = (cleaned.splitlines()[0] if cleaned else "Сгенерированная услуга")[:120].strip()
        first_line = first_line or "Сгенерированная услуга"
        digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:10]
        slug = _slugify(first_line, f"ai-{digest}")
        definition = {
            "schema_version": "1.0",
            "service_id": f"ai-{slug}-{digest}",
            "version": 1,
            "meta": {
                "title": first_line,
                "description": cleaned[:500],
                "org": "",
                "category": "",
                "audience": [],
                "summary_plain": cleaned[:280],
                "conditions": [],
                "documents_checklist": [],
                "result": "",
                "sla_days": None,
                "labels_plain": {"draft": "Черновик", "submitted": "Заявка отправлена"},
            },
            "statuses": ["draft", "submitted"],
            "transitions": [{"source": "draft", "target": "submitted"}],
            "stages": [
                {
                    "key": "main",
                    "title": "Заявка",
                    "steps": [
                        {
                            "key": "applicant",
                            "title": "Заявитель",
                            "fields": [
                                {
                                    "key": "company_name",
                                    "label": "Наименование заявителя",
                                    "type": "text",
                                    "required": True,
                                },
                                {"key": "bin", "label": "БИН/ИИН", "type": "text", "required": True},
                            ],
                        }
                    ],
                }
            ],
            "rules": [],
            "computed": [],
            "integrations": [],
        }
        return json.dumps(definition, ensure_ascii=False)
