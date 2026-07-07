# Траектория реализации ЕППБ MVP

Обновлено: 07.07.2026. Ветка: `main`. Источник: `docs/IMPLEMENTATION_PLAN.md`.

Статусы: `[ ]` очередь · `[~]` в работе · `[x]` реализовано и проверено · `[!]` блокер.

## Этап 0 — окружение и каркас

- [~] T0.1 Backend scaffold, health и единый формат ошибок
- [~] T0.2 Frontend scaffold и shell `/baiterek/take`, `/baiterek/create`
- [~] T0.3 Docker Compose, nginx, Makefile, ENV и CI
- [ ] T0.4 Интеграционная проверка и первый локальный запуск

## Этап 1 — данные и DSL

- [~] T1.1 SQLAlchemy-модели и миграция базовой схемы
- [~] T1.2 Pydantic Service Definition DSL v1 и JSON Schema
- [ ] T1.3 Версионирование, import/export и справочники
- [ ] T1.4 Инвариант отсутствия hardcode контрольных услуг

## Этап 2 — runtime engine

- [~] T2.1 Rules engine
- [~] T2.2 Formula engine на Decimal
- [~] T2.3 Renderer contract и дробление 3–6 полей
- [~] T2.4 Server validator и lifecycle
- [ ] T2.5 Unit/property/API tests и приёмка обеих Definition

## Этап 3 — `/baiterek/take`

- [ ] T3.1 Каталог, карточка и AI-intake/fallback
- [ ] T3.2 Draft/checkpoint API с optimistic revision
- [ ] T3.3 Form engine, autosave/resume и provenance
- [ ] T3.4 Upload, submit, mock-ЭЦП и кабинет
- [ ] T3.5 E2E happy/negative paths

## Этап 4 — `/baiterek/create`

- [ ] T4.1 Registry и visual constructor
- [ ] T4.2 AI generator + schema/semantic validation
- [ ] T4.3 Preview, publish, versioning и audit
- [ ] T4.4 Создание третьей услуги без изменения кода

## Этап 5–8

- [ ] T5.1 Реестр `[VERIFY]` и Service Definition A/B
- [ ] T6.1 Аналитика, карта, материалы и калькуляторы
- [ ] T7.1 RBAC, uploads, AI security и negative tests
- [ ] T8.1 Traceability и обязательные E2E

## Этап 9 — VM и выпуск

- [ ] T9.1 VM deploy, migration, health и external smoke
- [ ] T9.2 Backup/restore, rollback и наблюдаемость
- [ ] T9.3 README/screenshots и самостоятельный путь жюри
- [ ] T9.4 Release freeze и tag `v0.1.0-submission`

## Журнал Git

| Дата | Коммит | Пункты | Проверка |
|---|---|---|---|
| 07.07.2026 | `0f35c37` | План реализации | Документ опубликован в `main` |

