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

`/intake/match` and `/applications/{id}/completeness` do NOT go through this provider's
text-in/text-out protocol at all when `provider.name == "mock"` —
`app.ai.intake.match_services` calls `app.ai.intake.keyword_match` directly, and
`app.ai.completeness.completeness_suggestions` calls `rule_based_suggestions` directly.
That keeps their "keyword/rule-fallback без LLM" paths (SPEC.md §7.1) genuinely
separate, auditable algorithms rather than a JSON string this class would otherwise
have to fake being an LLM to produce.

`/services/{slug}/explain` is different: there is no separate rule-based "explain this
service" algorithm, so this class DOES answer that prompt (`TASK: explain_service`,
handled by `_explain_service` below) — a deterministic, template-based paraphrase of the
service's `meta`, in the same spirit as `_generate_definition` fakes the JSON-generation
protocol.
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
_META_MARKER = "META:\n"


def _slugify(text: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return slug or fallback


def _extract_source_text(prompt: str) -> str:
    index = prompt.find(_SOURCE_MARKER)
    return prompt[index + len(_SOURCE_MARKER) :].strip() if index != -1 else prompt.strip()


def _extract_meta(prompt: str) -> dict:
    index = prompt.find(_META_MARKER)
    raw = prompt[index + len(_META_MARKER) :].strip() if index != -1 else "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _lowercase_first(text: str) -> str:
    return f"{text[0].lower()}{text[1:]}" if text else text


class MockLLMProvider:
    """Offline, deterministic `LLMProvider` — see module docstring."""

    name = "mock"

    async def complete(self, *, system: str, prompt: str) -> LLMResult:
        if system.startswith("TASK: generate_service_definition"):
            return LLMResult(text=self._generate_definition(prompt), provider=self.name)
        if system.startswith("TASK: explain_service"):
            return LLMResult(text=self._explain_service(prompt), provider=self.name)
        # No other task currently routes through the mock's text protocol (see module
        # docstring re: /intake/match and /completeness), but returning valid empty JSON
        # rather than raising keeps this provider a safe default for any future caller.
        return LLMResult(text="{}", provider=self.name)

    def _explain_service(self, prompt: str) -> str:
        """Deterministic, template-based paraphrase of a service's `meta` (SPEC.md §7.1
        "Объяснить простыми словами", §7.3 "MockLLMProvider детерминированные ответы").
        Purely a function of `meta` — same input always yields the same sentences, no
        randomness, nothing invented that isn't already in `meta`."""
        meta = _extract_meta(prompt)
        title = str(meta.get("title") or "").strip() or "Эта мера поддержки"
        # `.rstrip(".")` avoids a doubled "нужного слов.." when the source text already
        # ends in a period — this template always supplies its own final punctuation.
        summary = str(meta.get("summary_plain") or "").strip().rstrip(".")
        conditions = meta.get("conditions") or []
        documents = meta.get("documents_checklist") or []
        result = str(meta.get("result") or "").strip().rstrip(".")
        sla_days = meta.get("sla_days")

        sentences = [f"«{title}» — {_lowercase_first(summary)}." if summary else f"«{title}» — мера поддержки бизнеса от государства."]

        condition_bits = [
            f"{item.get('label')}: {item.get('value')}"
            for item in conditions
            if isinstance(item, dict) and item.get("label") and item.get("value")
        ]
        if condition_bits:
            sentences.append("Основные условия: " + "; ".join(condition_bits) + ".")

        document_bits = [str(item).strip() for item in documents if str(item).strip()]
        if document_bits:
            sentences.append("Для заявки понадобится: " + ", ".join(document_bits) + ".")

        if result:
            sentences.append(f"Итог обращения — {_lowercase_first(result)}.")

        if isinstance(sla_days, (int, float)) and not isinstance(sla_days, bool):
            sentences.append(f"Срок рассмотрения — примерно {int(sla_days)} дн.")

        return " ".join(sentences)

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
