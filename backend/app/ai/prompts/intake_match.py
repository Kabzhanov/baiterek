"""Prompt for `POST /api/v1/intake/match` (SPEC.md §7.1 "Подбор меры (главная): свободный
текст → LLM с каталогом услуг в контексте → топ-3 меры с объяснением").
"""
from __future__ import annotations

import json

SYSTEM_PROMPT = (
    "TASK: intake_match\n"
    "Ты подбираешь меры поддержки бизнеса из каталога Единого портала поддержки "
    "бизнеса (Байтерек) по свободному описанию предпринимателя. Верни JSON-массив "
    'длиной не более 3 объектов {"slug": строка, "why": строка} — slug ТОЛЬКО из '
    "каталога ниже (не придумывай новые), why — короткое объяснение на русском простым "
    "языком, почему мера подходит именно этому запросу. Ответ — ТОЛЬКО JSON-массив."
)


def build_prompt(query: str, catalog: list[dict]) -> str:
    return f"QUERY:\n{query}\n\nCATALOG:\n{json.dumps(catalog, ensure_ascii=False)}\n"
