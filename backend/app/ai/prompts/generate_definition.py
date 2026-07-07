"""Prompt for `POST /api/v1/admin/definitions/generate` (SPEC.md §5.3, §7.2;
docs/IMPLEMENTATION_PLAN.md §9 "AI generator": "text/document → LLM → JSON extraction
→ JSON Schema → semantic validation").

Two markers `app.ai.generation` and every `LLMProvider` implementation agree on:

- `SOURCE_TEXT:` — delimits the administrator-supplied program text from the rest of
  the prompt. `MockLLMProvider` parses it back out; `AnthropicProvider` just forwards
  the whole prompt to the model, which reads it as plain instructions.
- `REPAIR_ATTEMPT: true` — present only on retry prompts (`build_repair_prompt`), so a
  provider (or a human reading logs) can tell an initial attempt from a self-correction
  round triggered by a failed validation.
"""
from __future__ import annotations

SYSTEM_PROMPT = (
    "TASK: generate_service_definition\n"
    "Ты — генератор Service Definition для портала ЕППБ (Байтерек). На основе текста "
    "программы государственной поддержки бизнеса верни ОДИН JSON-объект, строго "
    "соответствующий схеме Service Definition: schema_version (\"1.0\"), service_id "
    "(строка-слаг), version (int), meta{title, description, labels_plain}, "
    "stages[{key,title,steps[{key,title,fields[{key,label,topic,required,type,...}]}]}], "
    "rules[{target,effect,when}], computed[{key,expression}], statuses[строки], "
    "transitions[{source,target,when?}], integrations[строки]. "
    "НИКОГДА не придумывай суммы, ставки, сроки или условия, которых нет в исходном "
    "тексте (SPEC.md №230-VIII — прозрачность и объяснимость): если условие не указано "
    "явно, не включай соответствующее поле. Ответ — ТОЛЬКО JSON, без markdown, без "
    "пояснений до или после."
)


def build_prompt(text: str) -> str:
    return f"SOURCE_TEXT:\n{text}\n"


def build_repair_prompt(text: str, previous_error: str) -> str:
    return (
        "REPAIR_ATTEMPT: true\n"
        f"Предыдущий ответ не прошёл валидацию по схеме Service Definition: {previous_error}\n"
        "Верни ИСПРАВЛЕННЫЙ JSON, строго соответствующий схеме, и только его.\n\n"
        f"SOURCE_TEXT:\n{text}\n"
    )
