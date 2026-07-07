"""Static seed data (SPEC.md §3.1, §6 "make seed"). Kept separate from `app/seed/__init__.py`
so the orchestration logic (idempotent upsert/import) stays readable next to the data
it feeds.

The two demo services below are intentionally generic financing programs (working
capital credit, export credit guarantee) — NOT the two contest control cases
(SPEC.md §9), which are created later, only through the constructor/AI-generator, and
never referenced by name in application code (SPEC.md §0 disqualification clause).
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# organizations (SPEC.md §3.1: "Даму, БРК, КАФ, АКК, KazakhExport, Отбасы, КЖК, QIC + Холдинг")
# ---------------------------------------------------------------------------

ORGANIZATIONS: tuple[dict[str, str], ...] = (
    {
        "short_name": "Холдинг",
        "name": 'АО «Национальный управляющий холдинг «Байтерек»',
        "color": "#0B3D91",
    },
    {"short_name": "Даму", "name": 'Фонд развития предпринимательства «Даму»', "color": "#00A651"},
    {"short_name": "БРК", "name": "Банк Развития Казахстана", "color": "#1F4E79"},
    {"short_name": "КАФ", "name": "КазАгроФинанс", "color": "#6AA84F"},
    {"short_name": "АКК", "name": "Аграрная кредитная корпорация", "color": "#38761D"},
    {
        "short_name": "KazakhExport",
        "name": "Экспортное страховое агентство KazakhExport",
        "color": "#B45F06",
    },
    {"short_name": "Отбасы банк", "name": "Отбасы банк", "color": "#674EA7"},
    {"short_name": "КЖК", "name": "Казахстанская жилищная компания", "color": "#A64D79"},
    {"short_name": "QIC", "name": "Qazaqstan Investment Corporation", "color": "#45818E"},
)

# ---------------------------------------------------------------------------
# dictionaries (SPEC.md §3.1 dictionaries: "КАТО-регионы, ... банки-партнеры")
# ---------------------------------------------------------------------------

DICTIONARIES: tuple[dict[str, Any], ...] = (
    {
        "code": "applicant_types",
        "name": "Тип заявителя",
        "items": [
            {"code": "ip", "label": "Индивидуальный предприниматель"},
            {"code": "too", "label": "Товарищество с ограниченной ответственностью"},
            {"code": "ao", "label": "Акционерное общество"},
        ],
    },
    {
        "code": "kato_regions",
        "name": "Регионы (КАТО, кратко)",
        "items": [
            {"code": "AST", "label": "г. Астана"},
            {"code": "ALA", "label": "г. Алматы"},
            {"code": "SHY", "label": "г. Шымкент"},
            {"code": "ABY", "label": "Абайская область"},
            {"code": "AKM", "label": "Акмолинская область"},
            {"code": "AKT", "label": "Актюбинская область"},
            {"code": "ALM", "label": "Алматинская область"},
            {"code": "ATY", "label": "Атырауская область"},
            {"code": "VKO", "label": "Восточно-Казахстанская область"},
            {"code": "JET", "label": "Жетысуская область"},
            {"code": "ZHA", "label": "Жамбылская область"},
            {"code": "ZKO", "label": "Западно-Казахстанская область"},
            {"code": "KAR", "label": "Карагандинская область"},
            {"code": "KOS", "label": "Костанайская область"},
            {"code": "KZY", "label": "Кызылординская область"},
            {"code": "MAN", "label": "Мангистауская область"},
            {"code": "PAV", "label": "Павлодарская область"},
            {"code": "SKO", "label": "Северо-Казахстанская область"},
            {"code": "TUR", "label": "Туркестанская область"},
            {"code": "ULY", "label": "Улытауская область"},
        ],
    },
    {
        "code": "partner_banks",
        "name": "Банки-партнеры",
        "items": [
            {"code": "halyk", "label": "Halyk Bank"},
            {"code": "kaspi", "label": "Kaspi Bank"},
            {"code": "centercredit", "label": "Bank CenterCredit"},
            {"code": "forte", "label": "ForteBank"},
            {"code": "eurasian", "label": "Eurasian Bank"},
        ],
    },
)

# ---------------------------------------------------------------------------
# demo service definitions (SPEC.md §6 item 3: "2 нейтральные демо-услуги")
# ---------------------------------------------------------------------------

_WORKING_CAPITAL_LOAN: dict[str, Any] = {
    "schema_version": "1.0",
    "service_id": "oborotnoe-msb",
    "version": 1,
    "meta": {
        "title": "Оборотное кредитование для МСБ",
        "description": "",
        "org": "damu",
        "category": "credit",
        "audience": ["ЮЛ", "ИП"],
        "summary_plain": "Кредит на пополнение оборотных средств для малого и среднего бизнеса.",
        "conditions": [
            {"label": "Сумма", "value": "до 50 000 000 ₸"},
            {"label": "Срок", "value": "до 36 месяцев"},
        ],
        "documents_checklist": ["Справка о гос. регистрации", "Финансовая отчетность за последний период"],
        "result": "Решение о кредитовании",
        "sla_days": 10,
    },
    "statuses": ["draft", "submitted", "in_review_bpm", "approved", "rejected"],
    "transitions": [
        {"source": "draft", "target": "submitted"},
        {"source": "submitted", "target": "in_review_bpm"},
        {"source": "in_review_bpm", "target": "approved"},
        {"source": "in_review_bpm", "target": "rejected"},
    ],
    "stages": [
        {
            "key": "main",
            "title": "Заявка на кредит",
            "steps": [
                {
                    "key": "applicant",
                    "title": "Заявитель",
                    "fields": [
                        {
                            "key": "applicant_type",
                            "label": "Тип заявителя",
                            "type": "select",
                            "options": ["ИП", "ТОО"],
                            "required": True,
                        },
                        {"key": "company_name", "label": "Наименование заявителя", "type": "text", "required": True},
                        {"key": "bin", "label": "БИН/ИИН", "type": "text", "required": True},
                    ],
                },
                {
                    "key": "terms",
                    "title": "Параметры кредита",
                    "fields": [
                        {"key": "amount", "label": "Сумма кредита, ₸", "type": "number", "required": True, "minimum": 1},
                        {
                            "key": "rate",
                            "label": "Ставка, % годовых",
                            "type": "number",
                            "required": True,
                            "minimum": 0.1,
                        },
                        {
                            "key": "term_months",
                            "label": "Срок, мес.",
                            "type": "number",
                            "required": True,
                            "minimum": 1,
                        },
                        {"key": "has_collateral", "label": "Есть залоговое обеспечение", "type": "boolean"},
                    ],
                },
                {
                    "key": "documents",
                    "title": "Документы и поручитель",
                    "fields": [
                        {
                            "key": "has_financial_statements",
                            "label": "Есть финансовая отчетность за последний период",
                            "type": "boolean",
                            "required": True,
                        },
                        {"key": "guarantor_name", "label": "ФИО/наименование поручителя", "type": "text"},
                    ],
                },
            ],
        }
    ],
    "rules": [
        {"target": "guarantor_name", "effect": "require", "when": {"op": "eq", "args": ["$has_collateral", False]}}
    ],
    "computed": [
        {
            "key": "monthly_payment",
            "expression": {"op": "annuity", "args": ["$amount", {"op": "div", "args": ["$rate", 100]}, "$term_months"]},
        }
    ],
    "integrations": ["egov_idp", "gbd_ul", "ecp_sign", "bpm"],
}

_EXPORT_GUARANTEE: dict[str, Any] = {
    "schema_version": "1.0",
    "service_id": "garantiya-eksport",
    "version": 1,
    "meta": {
        "title": "Гарантия по кредиту для экспортёров",
        "description": "",
        "org": "kazakhexport",
        "category": "guarantee",
        "audience": ["ЮЛ", "ИП"],
        "summary_plain": "Частичная гарантия по банковскому кредиту для компаний-экспортёров.",
        "conditions": [
            {"label": "Доля гарантии", "value": "до 50%"},
            {"label": "Сумма кредита", "value": "по решению банка-партнёра"},
        ],
        "documents_checklist": ["Справка о гос. регистрации", "Экспортный контракт (при наличии)"],
        "result": "Решение о предоставлении гарантии",
        "sla_days": 15,
    },
    "statuses": ["draft", "submitted", "in_review_bpm", "approved", "rejected"],
    "transitions": [
        {"source": "draft", "target": "submitted"},
        {"source": "submitted", "target": "in_review_bpm"},
        {"source": "in_review_bpm", "target": "approved"},
        {"source": "in_review_bpm", "target": "rejected"},
    ],
    "stages": [
        {
            "key": "main",
            "title": "Заявка на гарантию",
            "steps": [
                {
                    "key": "applicant",
                    "title": "Заявитель",
                    "fields": [
                        {
                            "key": "applicant_type",
                            "label": "Тип заявителя",
                            "type": "select",
                            "options": ["ИП", "ТОО"],
                            "required": True,
                        },
                        {"key": "company_name", "label": "Наименование заявителя", "type": "text", "required": True},
                        {"key": "bin", "label": "БИН/ИИН", "type": "text", "required": True},
                        {"key": "is_exporter", "label": "Компания уже экспортирует продукцию", "type": "boolean"},
                    ],
                },
                {
                    "key": "guarantee",
                    "title": "Параметры гарантии",
                    "fields": [
                        {
                            "key": "credit_amount",
                            "label": "Сумма кредита банка, ₸",
                            "type": "number",
                            "required": True,
                            "minimum": 1,
                        },
                        {
                            "key": "guarantee_share",
                            "label": "Доля гарантии, %",
                            "type": "number",
                            "required": True,
                            "minimum": 1,
                            "maximum": 50,
                        },
                        {
                            "key": "partner_bank",
                            "label": "Банк-партнер",
                            "type": "select",
                            "options": ["Halyk Bank", "Kaspi Bank", "Bank CenterCredit", "ForteBank", "Eurasian Bank"],
                        },
                        {"key": "export_plan", "label": "План выхода на экспортные рынки", "type": "text"},
                    ],
                },
                {
                    "key": "contacts",
                    "title": "Контактные лица",
                    "fields": [{"key": "contacts", "label": "Контактные лица", "type": "repeater"}],
                },
            ],
        }
    ],
    "rules": [{"target": "export_plan", "effect": "require", "when": {"op": "eq", "args": ["$is_exporter", False]}}],
    "computed": [
        {
            "key": "guarantee_amount",
            "expression": {
                "op": "round",
                "args": [{"op": "div", "args": [{"op": "mul", "args": ["$credit_amount", "$guarantee_share"]}, 100]}, 0],
            },
        }
    ],
    "integrations": ["egov_idp", "gbd_ul", "ecp_sign", "bpm"],
}

DEMO_SERVICES: tuple[dict[str, Any], ...] = (
    {"slug": "oborotnoe-msb", "org_short_name": "Даму", "definition": _WORKING_CAPITAL_LOAN},
    {"slug": "garantiya-eksport", "org_short_name": "KazakhExport", "definition": _EXPORT_GUARANTEE},
)
