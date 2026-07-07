"""Free-text service matching (SPEC.md §7.1 "Подбор меры": "свободный текст → LLM с
каталогом услуг в контексте → топ-3 меры с объяснением 'почему подходит'").

`match_services` tries the configured `LLMProvider` first when it is NOT the mock
(`AnthropicProvider`, catalog embedded in the prompt); any failure of that call —
network error, non-JSON reply, a slug outside the catalog — degrades to `keyword_match`
rather than raising, so `/intake/match` never 500s because of the model (SPEC.md §7.3
"функциональность портала не деградирует"). When the configured provider IS the mock
(the default, and every test in this suite), `keyword_match` runs directly — SPEC.md
§7.1's "keyword-fallback без LLM" is a genuinely separate, auditable algorithm, not the
mock pretending to be an LLM.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.ai.prompts.intake_match import SYSTEM_PROMPT, build_prompt
from app.ai.provider import LLMProvider

_TOKEN_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)


@dataclass(frozen=True)
class MatchResult:
    slug: str
    title: str
    why: str


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text)}


def keyword_match(query: str, catalog: list[dict]) -> list[MatchResult]:
    """Pure, offline, non-LLM ranking by token overlap over title/summary/category."""
    query_tokens = _tokens(query)
    scored: list[tuple[int, set[str], dict]] = []
    for entry in catalog:
        haystack = " ".join(str(entry.get(field, "")) for field in ("title", "summary_plain", "category"))
        overlap = query_tokens & _tokens(haystack)
        if overlap:
            scored.append((len(overlap), overlap, entry))
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored:
        # Honest "nothing obviously matched" fallback: surface the first catalog
        # entries rather than an empty list, so the caller always has something to show.
        scored = [(0, set(), entry) for entry in catalog[:3]]
    results = []
    for _, overlap, entry in scored[:3]:
        why = (
            f"Совпадение по словам: {', '.join(sorted(overlap))}"
            if overlap
            else "Точных совпадений по описанию не найдено — популярная мера по умолчанию"
        )
        results.append(MatchResult(slug=entry["slug"], title=entry.get("title", entry["slug"]), why=why))
    return results


def _parse_llm_matches(text: str, catalog: list[dict]) -> list[MatchResult]:
    known = {entry["slug"]: entry for entry in catalog}
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("intake_match response must be a JSON array")
    results = []
    for item in parsed[:3]:
        slug = item.get("slug") if isinstance(item, dict) else None
        if not isinstance(slug, str) or slug not in known:
            continue
        title = known[slug].get("title") or slug
        results.append(MatchResult(slug=slug, title=title, why=str(item.get("why", ""))))
    if not results:
        raise ValueError("no known catalog slugs in LLM response")
    return results


async def match_services(provider: LLMProvider, query: str, catalog: list[dict]) -> tuple[list[MatchResult], str]:
    """Returns `(matches, method)`, `method` being `"llm"` or `"keyword"`."""
    if provider.name != "mock":
        try:
            result = await provider.complete(system=SYSTEM_PROMPT, prompt=build_prompt(query, catalog))
            return _parse_llm_matches(result.text, catalog), "llm"
        except Exception:  # noqa: BLE001 - any provider/parse failure degrades, it never 500s
            pass
    return keyword_match(query, catalog), "keyword"
