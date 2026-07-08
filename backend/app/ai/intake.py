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

# Тематические словари синонимов по сферам услуг (SPEC.md §7.1 "keyword-fallback").
# Exact-token overlap ловит только буквальные совпадения ("кредит"↔"кредит"), из-за чего
# запрос вроде «ферма … поголовье» проходил МИМО аграрной услуги: «ферма»≠«ферм»,
# «поголовье» вообще нет в описании. Каждая группа — набор основ (stems): токен относится
# к теме, если начинается с любой основы группы (prefix-match, дешёвая замена стемминга,
# «ферма»/«фермер»/«ферме» → основа «ферм»). Мера получает тематический бонус, когда основа
# группы встречается И в запросе, И в её описании — так ранжирование идёт по СМЫСЛУ сферы,
# а не по конкретному slug (slug-и здесь принципиально не упоминаются).
_KEYWORD_GROUPS: tuple[tuple[str, ...], ...] = (
    # Аграрный сектор / хозяйства (описания мер содержат основы «скот», «ферм», «сельск»).
    ("сельск", "агро", "фермер", "ферм", "хозяйств", "скот", "поголов", "крестьян", "пастбищ", "птицевод"),
    # Экспорт / внешнеэкономическая деятельность.
    ("экспорт", "зарубеж", "внешнеэконом", "таможен"),
    # Гарантии / залоги / поручительство.
    ("гаранти", "поручит", "залог", "обеспечен"),
    # Оборотные средства / пополнение / ликвидность.
    ("оборот", "пополнен", "ликвидн"),
)
# Скромный вес: тематическая близость подталкивает профильную меру вверх, но не
# перебивает сильное буквальное совпадение (проверяется существующими тестами ранжирования).
_GROUP_BONUS = 2


@dataclass(frozen=True)
class MatchResult:
    slug: str
    title: str
    why: str


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text)}


def _group_stems_present(tokens: set[str], group: tuple[str, ...]) -> set[str]:
    """Основы группы, для которых нашёлся токен, начинающийся с этой основы."""
    return {stem for stem in group for token in tokens if token.startswith(stem)}


def _thematic_score(
    query_tokens: set[str], haystack_tokens: set[str]
) -> tuple[int, set[str]]:
    """Число тем, общих для запроса и описания, + токены запроса, задавшие тему (для «почему»)."""
    matched_groups = 0
    triggers: set[str] = set()
    for group in _KEYWORD_GROUPS:
        if _group_stems_present(haystack_tokens, group) and _group_stems_present(query_tokens, group):
            matched_groups += 1
            triggers |= {token for token in query_tokens for stem in group if token.startswith(stem)}
    return matched_groups, triggers


def keyword_match(query: str, catalog: list[dict]) -> list[MatchResult]:
    """Pure, offline, non-LLM ranking: literal token overlap over title/summary/category,
    plus a thematic synonym bonus (`_KEYWORD_GROUPS`) so a query in the vocabulary of a
    sphere (e.g. фермерское/сельское хозяйство) ranks the matching sphere's service first
    even when it shares no literal word with the description."""
    query_tokens = _tokens(query)
    scored: list[tuple[int, set[str], set[str], dict]] = []
    for entry in catalog:
        haystack_tokens = _tokens(
            " ".join(str(entry.get(field, "")) for field in ("title", "summary_plain", "category"))
        )
        overlap = query_tokens & haystack_tokens
        matched_groups, thematic = _thematic_score(query_tokens, haystack_tokens)
        score = len(overlap) + _GROUP_BONUS * matched_groups
        if score > 0:
            scored.append((score, overlap, thematic, entry))
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored:
        # Honest "nothing obviously matched" fallback: surface the first catalog
        # entries rather than an empty list, so the caller always has something to show.
        scored = [(0, set(), set(), entry) for entry in catalog[:3]]
    results = []
    for _, overlap, thematic, entry in scored[:3]:
        results.append(
            MatchResult(slug=entry["slug"], title=entry.get("title", entry["slug"]), why=_why(overlap, thematic))
        )
    return results


def _why(overlap: set[str], thematic: set[str]) -> str:
    parts = []
    if overlap:
        parts.append(f"Совпадение по словам: {', '.join(sorted(overlap))}")
    # Тематические слова, уже попавшие в буквальное совпадение, не дублируем.
    extra = sorted(thematic - overlap)
    if extra:
        parts.append(f"Совпадение по теме: {', '.join(extra)}")
    if not parts:
        return "Точных совпадений по описанию не найдено — популярная мера по умолчанию"
    return "; ".join(parts)


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
