"""Prompt for `POST /api/v1/services/{slug}/explain` (SPEC.md §7.1 "Объяснить простыми
словами": published Definition.meta → LLM → пересказ условий простым языком + что
понадобится для заявки).

One marker, mirroring `app.ai.prompts.generate_definition`'s `SOURCE_TEXT:` convention:

- `META:` — delimits the service's `meta` JSON from the rest of the prompt.
  `MockLLMProvider` parses it back out (`app.ai.mock_provider._extract_meta`);
  `AnthropicProvider` just forwards the whole prompt to the model.
"""
from __future__ import annotations

import json

SYSTEM_PROMPT = (
    "TASK: explain_service\n"
    "Ты объясняешь предпринимателю условия государственной меры поддержки простым "
    "языком, без канцелярита и юридических штампов. На основе структурированного "
    "описания услуги (JSON ниже, ключ meta из Service Definition ЕППБ) напиши связный "
    "текст на русском языке: что это за мера, кому подходит, какие условия и что "
    "понадобится для подачи заявки. НЕ придумывай факты, сумм, ставок или условий, "
    "которых нет в описании (SPEC.md №230-VIII — прозрачность и объяснимость). Ответ — "
    "простой связный текст (НЕ JSON, без markdown-разметки), 3-6 предложений."
)


def build_prompt(meta: dict) -> str:
    return f"META:\n{json.dumps(meta, ensure_ascii=False)}\n"
