"""Prompt for `POST /api/v1/applications/{id}/completeness` (SPEC.md §7.1 "Проверка
полноты заявки": подсказки, что стоит проверить/дополнить перед отправкой — советует,
не блокирует).

Only reached for a *configured, non-mock* provider (`app.ai.completeness.
completeness_suggestions` — see that module's docstring): the model is asked to
rephrase/prioritise an already-computed list of empty required field labels, never to
invent which fields are missing itself, so a hallucinated field name can't produce a
misleading suggestion.
"""
from __future__ import annotations

import json

SYSTEM_PROMPT = (
    "TASK: completeness_advice\n"
    "Ты помогаешь предпринимателю на портале ЕППБ проверить заявку перед отправкой. "
    "Ниже — JSON-массив названий полей текущего этапа заявки, которые пока не "
    "заполнены. Верни JSON-массив строк (не более 8) — по одной рекомендации на поле, "
    'в формате "Рекомендуем проверить: «НАЗВАНИЕ ПОЛЯ» — короткое пояснение, зачем это '
    'нужно". НЕ добавляй поля, которых нет в списке ниже, и не меняй их названия. Ответ '
    "— ТОЛЬКО JSON-массив строк."
)


def build_prompt(missing_labels: list[str]) -> str:
    return f"MISSING_FIELDS:\n{json.dumps(missing_labels, ensure_ascii=False)}\n"
