"""Unit tests for `app.ai.intake` — the non-LLM keyword fallback (SPEC.md §7.1
"keyword-fallback без LLM") plus `match_services`'s mock routing, no DB/network.
"""
from __future__ import annotations

import pytest

from app.ai.intake import keyword_match, match_services
from app.ai.mock_provider import MockLLMProvider

pytestmark = pytest.mark.asyncio(loop_scope="session")

_CATALOG = [
    {
        "slug": "oborotnoe-msb",
        "title": "Оборотное кредитование для МСБ",
        "summary_plain": "Кредит на пополнение оборотных средств для малого и среднего бизнеса.",
        "category": "credit",
    },
    {
        "slug": "garantiya-eksport",
        "title": "Гарантия по кредиту для экспортёров",
        "summary_plain": "Частичная гарантия по банковскому кредиту для компаний-экспортёров.",
        "category": "guarantee",
    },
]


def test_keyword_match_ranks_by_token_overlap():
    results = keyword_match("нужен кредит для пополнения оборотных средств бизнеса", _CATALOG)

    assert results[0].slug == "oborotnoe-msb"
    assert "почему" not in results[0].why  # sanity: `why` is a real explanation, not a placeholder
    assert results[0].why


def test_keyword_match_falls_back_to_catalog_head_when_nothing_overlaps():
    results = keyword_match("совершенно не связанный запрос про зоопарк", _CATALOG)

    assert len(results) == min(3, len(_CATALOG))
    assert {r.slug for r in results} == {entry["slug"] for entry in _CATALOG}


def test_keyword_match_caps_at_three_results():
    catalog = [{**_CATALOG[0], "slug": f"svc-{i}", "title": f"Кредит {i}"} for i in range(5)]

    results = keyword_match("кредит", catalog)

    assert len(results) == 3


async def test_match_services_with_mock_provider_uses_keyword_fallback_method():
    provider = MockLLMProvider()

    matches, method = await match_services(provider, "гарантия по кредиту для экспортёров", _CATALOG)

    assert method == "keyword"
    assert matches[0].slug == "garantiya-eksport"
