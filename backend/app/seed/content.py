"""Idempotent seed for map_projects / analytics_materials / knowledge_items
(SPEC.md §4.5-4.7, docs/IMPLEMENTATION_PLAN.md §11 "Этап 6"). Run with
`python -m app.seed.content` — separate from `app/seed/__init__.py`'s core seed
(organizations, dictionaries, two neutral demo Definitions) so this module can be
re-run on its own to refresh demo content.

Idempotency: organizations are matched by `short_name` (delegated to
`app.seed._seed_organizations`, same matching rule the core seed uses); map_projects
match on `(org_id, name)`; analytics_materials match on `(org_id, title)`;
knowledge_items match on `title`. All three sets are looked up once per run and only
the missing rows are inserted, so re-running never duplicates data.

map_projects are all `is_demo=true` (SPEC.md §4.6: "сид ~120-150 демо-проектов ...
с пометкой «демонстрационные данные»") — synthetic, deterministically generated
(fixed RNG seed) so re-runs are stable, spread across all 20 regions of Kazakhstan
(17 oblasts + 3 cities of republican significance; KATO region codes `KZ-10`..`KZ-79`)
and the 9 seeded organizations.

analytics_materials use real, verified public URLs (SPEC.md §4.5: "ссылки на реальные
публичные ресурсы"): each subsidiary's official site, plus two KASE-hosted PDF
statements of the Holding that were checked to serve no `X-Frame-Options`/
`frame-ancestors` header (`embed_allowed=true` — everything else stays `false`
because the subsidiaries' own sites send `X-Frame-Options: SAMEORIGIN`, verified the
same way).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Session
from app.models import (
    AnalyticsMaterial,
    AnalyticsMaterialType,
    KnowledgeItem,
    KnowledgeItemCategory,
    MapProject,
    Organization,
)
from app.seed import SeedSummary, _seed_organizations

_RNG_SEED = 20260707  # fixed seed -> deterministic, stable demo dataset across re-runs

# ---------------------------------------------------------------------------
# map_projects (SPEC.md §4.6)
# ---------------------------------------------------------------------------

# (region_code КАТО, region name, center lat, center lng, representative locality)
REGIONS: tuple[tuple[str, str, float, float, str], ...] = (
    ("KZ-10", "Абайская область", 50.4111, 80.2275, "Семей"),
    ("KZ-11", "Акмолинская область", 53.2833, 69.3833, "Кокшетау"),
    ("KZ-15", "Актюбинская область", 50.2839, 57.1670, "Актобе"),
    ("KZ-19", "Алматинская область", 43.8756, 77.0546, "Конаев"),
    ("KZ-23", "Атырауская область", 47.1164, 51.8825, "Атырау"),
    ("KZ-27", "Западно-Казахстанская область", 51.2333, 51.3667, "Уральск"),
    ("KZ-31", "Жамбылская область", 42.9000, 71.3667, "Тараз"),
    ("KZ-33", "Жетысуская область", 45.0167, 78.3667, "Талдыкорган"),
    ("KZ-35", "Карагандинская область", 49.8047, 73.1094, "Караганда"),
    ("KZ-39", "Костанайская область", 53.2144, 63.6246, "Костанай"),
    ("KZ-43", "Кызылординская область", 44.8479, 65.4999, "Кызылорда"),
    ("KZ-47", "Мангистауская область", 43.6481, 51.1978, "Актау"),
    ("KZ-55", "Павлодарская область", 52.2873, 76.9674, "Павлодар"),
    ("KZ-59", "Северо-Казахстанская область", 54.8667, 69.1500, "Петропавловск"),
    ("KZ-61", "Туркестанская область", 43.2975, 68.2517, "Туркестан"),
    ("KZ-62", "Улытауская область", 47.7833, 67.7000, "Жезказган"),
    ("KZ-63", "Восточно-Казахстанская область", 49.9714, 82.6059, "Усть-Каменогорск"),
    ("KZ-71", "г. Астана", 51.1694, 71.4491, "Астана"),
    ("KZ-75", "г. Алматы", 43.2220, 76.8512, "Алматы"),
    ("KZ-79", "г. Шымкент", 42.3417, 69.5901, "Шымкент"),
)

INDUSTRY_TEMPLATES: dict[str, tuple[str, ...]] = {
    "Обрабатывающая промышленность": (
        "Модернизация производственной линии, {locality}",
        "Строительство цеха металлообработки в {locality}",
        "Расширение производства стройматериалов, {locality}",
    ),
    "Сельское хозяйство": (
        "Обновление парка сельхозтехники, {locality}",
        "Строительство зернохранилища в {locality}",
        "Развитие тепличного комплекса, {locality}",
    ),
    "Пищевая промышленность": (
        "Модернизация мукомольного комбината, {locality}",
        "Строительство молочного завода в {locality}",
        "Расширение линии переработки овощей, {locality}",
    ),
    "Строительство": (
        "Строительство индустриального парка в {locality}",
        "Возведение логистического терминала, {locality}",
    ),
    "Транспорт и логистика": (
        "Создание транспортно-логистического хаба в {locality}",
        "Модернизация автопарка перевозчика, {locality}",
    ),
    "Торговля": (
        "Открытие торгово-распределительного центра в {locality}",
        "Развитие сети магазинов формата у дома, {locality}",
    ),
    "Туризм": (
        "Строительство туристического комплекса в {locality}",
        "Развитие придорожного сервиса на трассе у {locality}",
    ),
    "IT и инновации": (
        "Запуск цифровой платформы для бизнеса, {locality}",
        "Создание IT-хаба в {locality}",
    ),
    "Энергетика и добыча": (
        "Модернизация котельной в {locality}",
        "Строительство солнечной электростанции у {locality}",
    ),
    "Химическая промышленность": (
        "Расширение производства удобрений в {locality}",
        "Модернизация химического завода, {locality}",
    ),
}

STATUSES: tuple[str, ...] = ("Планируется", "Финансируется", "Реализуется", "Завершён")
_STATUS_WEIGHTS: tuple[float, ...] = (0.15, 0.20, 0.40, 0.25)

TOTAL_MAP_PROJECTS = 120


def _generate_map_projects(orgs: dict[str, Organization], rng: random.Random) -> list[dict]:
    org_short_names = list(orgs.keys())
    industries = list(INDUSTRY_TEMPLATES.keys())
    seen_names: dict[tuple, int] = {}
    projects: list[dict] = []

    for _ in range(TOTAL_MAP_PROJECTS):
        region_code, region_name, lat, lng, locality = rng.choice(REGIONS)
        org_short = rng.choice(org_short_names)
        org = orgs[org_short]
        industry = rng.choice(industries)
        template = rng.choice(INDUSTRY_TEMPLATES[industry])
        name = template.format(locality=locality)

        key = (org.id, name)
        seen_names[key] = seen_names.get(key, 0) + 1
        if seen_names[key] > 1:
            name = f"{name} (№{seen_names[key]})"

        status = rng.choices(STATUSES, weights=_STATUS_WEIGHTS, k=1)[0]
        amount = Decimal(rng.randrange(200, 35_000)) * Decimal("100000")  # 20 млн..3.5 млрд ₸, ровно до сотен тыс.
        period_start = date(2022, 1, 1) + timedelta(days=rng.randrange(0, 1600))
        period_end = period_start + timedelta(days=rng.randrange(180, 1460))
        jitter_lat = round(lat + rng.uniform(-0.35, 0.35), 6)
        jitter_lng = round(lng + rng.uniform(-0.35, 0.35), 6)

        projects.append(
            {
                "org_id": org.id,
                "name": name,
                "region_code": region_code,
                "locality": locality,
                "lat": Decimal(str(jitter_lat)),
                "lng": Decimal(str(jitter_lng)),
                "industry": industry,
                "amount": amount,
                "period_start": period_start,
                "period_end": period_end,
                "status": status,
                "description": (
                    f"Проект по направлению «{industry}» в {region_name} ({locality}). "
                    f"Партнёр финансирования — {org.name}. Статус: {status.lower()}."
                ),
                "is_demo": True,
            }
        )
    return projects


async def _seed_map_projects(session: AsyncSession, orgs: dict[str, Organization], summary: "ContentSeedSummary") -> None:
    rng = random.Random(_RNG_SEED)
    generated = _generate_map_projects(orgs, rng)

    existing_rows = (await session.execute(select(MapProject.org_id, MapProject.name))).all()
    existing = {(row.org_id, row.name) for row in existing_rows}

    for spec in generated:
        key = (spec["org_id"], spec["name"])
        if key in existing:
            summary.map_projects_existing += 1
            continue
        session.add(MapProject(**spec))
        existing.add(key)
        summary.map_projects_created += 1
    await session.commit()


# ---------------------------------------------------------------------------
# analytics_materials (SPEC.md §4.5) — real public URLs, verified headers
# ---------------------------------------------------------------------------

ANALYTICS_MATERIALS: tuple[dict, ...] = (
    {
        "org_short_name": "Холдинг",
        "type": AnalyticsMaterialType.REPORT,
        "title": "Годовой отчёт АО «НУХ «Байтерек» за 2024 год",
        "description": "Официальный годовой отчёт Холдинга: итоги года, портфель проектов, финансовые показатели.",
        "source": "baiterek.gov.kz / KASE",
        "period": "2024",
        "url": "https://kase.kz/files/emitters/BTRK/btrkp_2024_rus.pdf",
        # Проверено: сервер kase.kz/files отдаёт PDF без X-Frame-Options/CSP frame-ancestors — embed безопасен.
        "embed_allowed": True,
    },
    {
        "org_short_name": "Холдинг",
        "type": AnalyticsMaterialType.FINANCIAL,
        "title": "Консолидированная финансовая отчётность Холдинга (1 полугодие 2025)",
        "description": "Промежуточная консолидированная финансовая отчётность группы компаний Холдинга.",
        "source": "KASE (раскрытие эмитента BTRK)",
        "period": "1 полугодие 2025",
        "url": "https://kase.kz/files/emitters/BTRK/btrkf6m2_2025_cons_rus.pdf",
        "embed_allowed": True,
    },
    {
        "org_short_name": "Даму",
        "type": AnalyticsMaterialType.DASHBOARD,
        "title": "Фонд «Даму» — программы и показатели поддержки МСБ",
        "description": "Официальный раздел фонда о механизмах поддержки предпринимательства.",
        "source": "damu.kz",
        "period": "актуально",
        "url": "https://damu.kz/ru/o-fonde/",
        "embed_allowed": False,
    },
    {
        "org_short_name": "БРК",
        "type": AnalyticsMaterialType.DASHBOARD,
        "title": "Банк Развития Казахстана — проекты и отчётность",
        "description": "Официальный сайт БРК: финансируемые проекты в обрабатывающем секторе.",
        "source": "kdb.kz",
        "period": "актуально",
        "url": "https://www.kdb.kz/",
        "embed_allowed": False,
    },
    {
        "org_short_name": "КАФ",
        "type": AnalyticsMaterialType.DASHBOARD,
        "title": "КазАгроФинанс — лизинг сельхозтехники и оборудования",
        "description": "Официальный сайт КАФ: условия лизинга и кредитования агробизнеса.",
        "source": "kaf.kz",
        "period": "актуально",
        "url": "https://kaf.kz/ru/",
        "embed_allowed": False,
    },
    {
        "org_short_name": "АКК",
        "type": AnalyticsMaterialType.DASHBOARD,
        "title": "Аграрная кредитная корпорация — кредитование АПК",
        "description": "Официальный сайт АКК: программы кредитования агропромышленного комплекса.",
        "source": "agrocredit.kz",
        "period": "актуально",
        "url": "https://agrocredit.kz/ru/",
        "embed_allowed": False,
    },
    {
        "org_short_name": "KazakhExport",
        "type": AnalyticsMaterialType.DASHBOARD,
        "title": "KazakhExport — страхование и поддержка экспорта",
        "description": "Официальный сайт экспортно-кредитного агентства: страхование экспортных операций.",
        "source": "kazakhexport.kz",
        "period": "актуально",
        "url": "https://kazakhexport.kz/ru/",
        "embed_allowed": False,
    },
    {
        "org_short_name": "Отбасы банк",
        "type": AnalyticsMaterialType.DASHBOARD,
        "title": "Отбасы банк — жилищные строительные сбережения",
        "description": "Официальный сайт банка: система жилстройсбережений и ипотечные программы.",
        "source": "hcsbk.kz",
        "period": "актуально",
        "url": "https://hcsbk.kz/",
        "embed_allowed": False,
    },
    {
        "org_short_name": "КЖК",
        "type": AnalyticsMaterialType.DASHBOARD,
        "title": "Казахстанская жилищная компания — программы жилищного строительства",
        "description": "Официальный сайт КЖК: единый оператор жилищного строительства.",
        "source": "khc.kz",
        "period": "актуально",
        "url": "https://khc.kz/ru",
        "embed_allowed": False,
    },
    {
        "org_short_name": "QIC",
        "type": AnalyticsMaterialType.RESEARCH,
        "title": "Qazaqstan Investment Corporation — соинвестирование в фонды прямых инвестиций",
        "description": "Официальный сайт QIC: участие в фондах прямых инвестиций и привлечение соинвесторов.",
        "source": "qic.kz",
        "period": "актуально",
        "url": "https://qic.kz/ru/about-the-company/",
        "embed_allowed": False,
    },
)


async def _seed_analytics_materials(
    session: AsyncSession, orgs: dict[str, Organization], summary: "ContentSeedSummary"
) -> None:
    existing_rows = (await session.execute(select(AnalyticsMaterial.org_id, AnalyticsMaterial.title))).all()
    existing = {(row.org_id, row.title) for row in existing_rows}

    for spec in ANALYTICS_MATERIALS:
        org = orgs[spec["org_short_name"]]
        key = (org.id, spec["title"])
        if key in existing:
            summary.analytics_materials_existing += 1
            continue
        session.add(
            AnalyticsMaterial(
                org_id=org.id,
                type=spec["type"],
                title=spec["title"],
                description=spec["description"],
                source=spec["source"],
                period=spec["period"],
                url=spec["url"],
                embed_allowed=spec["embed_allowed"],
            )
        )
        existing.add(key)
        summary.analytics_materials_created += 1
    await session.commit()


# ---------------------------------------------------------------------------
# knowledge_items (SPEC.md §4.7)
# ---------------------------------------------------------------------------

KNOWLEDGE_ITEMS: tuple[dict, ...] = (
    {
        "category": KnowledgeItemCategory.GUIDE,
        "title": "Как выбрать программу поддержки бизнеса",
        "description": "Пошаговый разбор: с чего начать поиск подходящей меры поддержки.",
        "content": (
            "1) Определите цель финансирования (оборотные средства, оборудование, экспорт, жильё для сотрудников). "
            "2) Проверьте соответствие ОКЭД и региона условиям программы. "
            "3) Сравните ставку, срок, требования к залогу у разных организаций Холдинга. "
            "4) Соберите пакет документов по чек-листу услуги. 5) Подайте заявку через раздел «Получить услугу»."
        ),
        "url": None,
    },
    {
        "category": KnowledgeItemCategory.GUIDE,
        "title": "Что такое лизинг оборудования: основы для предпринимателя",
        "description": "Простыми словами о том, чем лизинг отличается от кредита и когда он выгоднее.",
        "content": (
            "Лизинг — форма финансирования, при которой лизингодатель покупает оборудование и передаёт его "
            "предпринимателю в пользование за периодические платежи с правом выкупа. В отличие от кредита, "
            "предмет лизинга остаётся в собственности лизингодателя до полного расчёта, что снижает требования "
            "к залоговому обеспечению."
        ),
        "url": None,
    },
    {
        "category": KnowledgeItemCategory.TEMPLATE,
        "title": "Шаблон структуры бизнес-плана для заявки на финансирование",
        "description": "Универсальная структура разделов бизнес-плана, которую принимают организации Холдинга.",
        "content": (
            "1. Резюме проекта. 2. Описание бизнеса и продукта. 3. Анализ рынка и конкурентов. "
            "4. Организационный план. 5. Производственный план. 6. Маркетинговый план. "
            "7. Финансовый план (прогноз доходов/расходов, точка безубыточности). 8. Оценка рисков."
        ),
        "url": None,
    },
    {
        "category": KnowledgeItemCategory.TEMPLATE,
        "title": "Шаблон гарантийного письма для банка-партнёра",
        "description": "Базовая форма гарантийного письма при подтверждении обеспечения по кредиту.",
        "content": (
            "Гарантийное письмо содержит: реквизиты заявителя и банка-партнёра, сумму и срок обязательства, "
            "предмет обеспечения, подписи уполномоченных лиц и печать. Итоговую форму уточняйте у конкретного "
            "банка-партнёра — требования к формулировкам различаются."
        ),
        "url": None,
    },
    {
        "category": KnowledgeItemCategory.CHECKLIST,
        "title": "Чек-лист документов для заявки на финансирование ИП/ТОО",
        "description": "Базовый пакет документов, который запрашивают большинство программ поддержки.",
        "content": (
            "Справка о государственной регистрации; устав (для ТОО); удостоверение личности руководителя; "
            "финансовая отчётность за последний период; справка об отсутствии налоговой задолженности; "
            "технико-экономическое обоснование или бизнес-план проекта."
        ),
        "url": None,
    },
    {
        "category": KnowledgeItemCategory.CHECKLIST,
        "title": "Чек-лист готовности к комплаенс-проверке (KYC) банка-партнёра",
        "description": "Что проверяют перед одобрением финансирования и как подготовиться заранее.",
        "content": (
            "Актуальность учредительных документов; отсутствие связей с санкционными лицами; прозрачная структура "
            "собственников; подтверждённые источники происхождения средств; отсутствие просроченной задолженности "
            "перед другими банками."
        ),
        "url": None,
    },
    {
        "category": KnowledgeItemCategory.CALCULATOR,
        "title": "Калькулятор аннуитетного платежа",
        "description": "Расчёт ежемесячного платежа по кредиту или лизингу с равными платежами.",
        "content": (
            "Использует ту же формулу аннуитета, что и движок расчётов конструктора услуг: "
            "платёж = P × r × (1+r)^n / ((1+r)^n − 1), где P — сумма, r — месячная ставка, n — число месяцев."
        ),
        "url": "/take/tools#annuity",
    },
    {
        "category": KnowledgeItemCategory.CALCULATOR,
        "title": "Калькулятор субсидируемой ставки",
        "description": "Сравнение платежа по полной рыночной ставке и по ставке с учётом субсидирования.",
        "content": (
            "Показывает платёж по полной ставке, платёж по субсидированной ставке (разница компенсируется "
            "программой поддержки) и итоговую экономию заявителя за весь срок."
        ),
        "url": "/take/tools#subsidy",
    },
    {
        "category": KnowledgeItemCategory.REVIEW,
        "title": "Обзор мер поддержки агропромышленного комплекса от Холдинга «Байтерек»",
        "description": "Краткий обзор направлений: лизинг техники, кредитование, страхование экспорта продукции АПК.",
        "content": (
            "КазАгроФинанс — лизинг сельхозтехники и оборудования переработки; Аграрная кредитная корпорация — "
            "кредитование через кредитные товарищества и напрямую; KazakhExport — страхование экспортных поставок "
            "продукции АПК. Программы дополняют друг друга на разных этапах цикла: от закупки техники до продажи "
            "готовой продукции за рубеж."
        ),
        "url": None,
    },
)


async def _seed_knowledge_items(session: AsyncSession, summary: "ContentSeedSummary") -> None:
    existing_titles = {row[0] for row in (await session.execute(select(KnowledgeItem.title))).all()}

    for spec in KNOWLEDGE_ITEMS:
        if spec["title"] in existing_titles:
            summary.knowledge_items_existing += 1
            continue
        session.add(
            KnowledgeItem(
                category=spec["category"],
                title=spec["title"],
                description=spec["description"],
                content=spec["content"],
                url=spec["url"],
            )
        )
        existing_titles.add(spec["title"])
        summary.knowledge_items_created += 1
    await session.commit()


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------


@dataclass
class ContentSeedSummary:
    organizations_created: int = 0
    organizations_existing: int = 0
    map_projects_created: int = 0
    map_projects_existing: int = 0
    analytics_materials_created: int = 0
    analytics_materials_existing: int = 0
    knowledge_items_created: int = 0
    knowledge_items_existing: int = 0

    def describe(self) -> str:
        return (
            f"organizations: +{self.organizations_created} (already had {self.organizations_existing}); "
            f"map_projects: +{self.map_projects_created} (already had {self.map_projects_existing}); "
            f"analytics_materials: +{self.analytics_materials_created} (already had {self.analytics_materials_existing}); "
            f"knowledge_items: +{self.knowledge_items_created} (already had {self.knowledge_items_existing})"
        )


async def run_content_seed() -> ContentSeedSummary:
    summary = ContentSeedSummary()
    async with Session() as session:
        # Delegates to the core seed's organization upsert (same matching rule, same
        # data) so this module works standalone even if `python -m app.seed` hasn't
        # run yet, and never diverges from the canonical organization list.
        org_summary = SeedSummary()
        orgs = await _seed_organizations(session, org_summary)
        summary.organizations_created = org_summary.organizations_created
        summary.organizations_existing = org_summary.organizations_existing

        await _seed_map_projects(session, orgs, summary)
        await _seed_analytics_materials(session, orgs, summary)
        await _seed_knowledge_items(session, summary)
    return summary


def main() -> None:
    import asyncio

    summary = asyncio.run(run_content_seed())
    print(f"content seed complete: {summary.describe()}")


if __name__ == "__main__":
    main()


__all__ = ["ContentSeedSummary", "run_content_seed"]
