"""Mock ГБД ЮЛ adapter (SPEC.md §8): "по БИН/ИИН возвращает реквизиты компании
(наименование, ОКЭД, адрес, руководитель) из тестового справочника → предзаполнение
форм". Backs the Definition DSL's `field.prefill: "integration:gbd_ul.bin"` hint
(SPEC.md §3.2 example) — the form-engine calls this by BIN to auto-fill the applicant
block instead of asking the user to retype company details already known to the state.

All companies below are entirely synthetic test fixtures (SPEC.md §9 "test users
полностью синтетические") — none refer to a real legal entity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CompanyRecord:
    bin: str
    name: str
    oked: str
    oked_name: str
    address: str
    director: str


# Тестовый справочник ГБД ЮЛ — синтетические компании (SPEC.md §8).
TEST_COMPANIES: tuple[CompanyRecord, ...] = (
    CompanyRecord(
        bin="990101400000",
        name='ТОО «Демо»',
        oked="62.01",
        oked_name="Разработка программного обеспечения",
        address="г. Алматы, ул. Тестовая, д. 1",
        director="Демонов Демо Демонович",
    ),
    CompanyRecord(
        bin="990101400001",
        name='ТОО «Алатау Сервис»',
        oked="46.90",
        oked_name="Неспециализированная оптовая торговля",
        address="г. Алматы, пр. Тестовый, д. 10",
        director="Алатаев Алатау Алатаевич",
    ),
    CompanyRecord(
        bin="990101400002",
        name='ТОО «Сарыарка Трейд»',
        oked="47.11",
        oked_name="Розничная торговля в неспециализированных магазинах",
        address="г. Астана, ул. Тестовая, д. 20",
        director="Сарыаркин Санжар Сарыаркинович",
    ),
    CompanyRecord(
        bin="990101400003",
        name='ТОО «Каспий Логистик»',
        oked="52.29",
        oked_name="Прочая вспомогательная транспортная деятельность",
        address="г. Атырау, ул. Тестовая, д. 5",
        director="Каспиев Дамир Каспиевич",
    ),
    CompanyRecord(
        bin="990101400004",
        name='ТОО «Есиль Строй»',
        oked="41.20",
        oked_name="Строительство жилых и нежилых зданий",
        address="г. Астана, ул. Тестовая, д. 30",
        director="Есилев Ерлан Есилевич",
    ),
    CompanyRecord(
        bin="990101400005",
        name='ТОО «Жетысу Экспорт»',
        oked="46.19",
        oked_name="Деятельность агентов по оптовой торговле универсальным ассортиментом товаров",
        address="г. Талдыкорган, ул. Тестовая, д. 7",
        director="Жетысуев Ержан Жетысуевич",
    ),
)


class GbdUlPort(Protocol):
    """Interface a real ГБД ЮЛ adapter must satisfy."""

    def lookup(self, bin_value: str) -> CompanyRecord | None: ...


class MockGbdUlAdapter:
    """Имитация ГБД ЮЛ — реквизиты компании из тестового справочника, не реальный госреестр."""

    def lookup(self, bin_value: str) -> CompanyRecord | None:
        return next((company for company in TEST_COMPANIES if company.bin == bin_value), None)


__all__ = ["CompanyRecord", "GbdUlPort", "MockGbdUlAdapter", "TEST_COMPANIES"]
