# План реализации ЕППБ MVP

**Статус:** на утверждении владельца  
**Дата:** 07.07.2026 · **Дедлайн:** 12.07.2026  
**GitHub:** https://github.com/Kabzhanov/baiterek  
**Ветка последующих push:** `main`  
**Маршруты:** `/baiterek/take` — получить услугу; `/baiterek/create` — создать услугу.

Разработка начинается после утверждения. План — исполняемый backlog: изменение
архитектуры сначала фиксируется здесь или в ADR, затем реализуется.

## 1. ЦКП и готовность MVP

ЦКП — публичный портал, где предприниматель подбирает, заполняет и отслеживает
услугу, а администратор создаёт новую услугу без отдельной разработки формы.

MVP готов, когда одновременно выполнено:

1. Оба URL работают по HTTPS с внешней сети.
2. Две контрольные услуги хранятся как версии `Service Definition`; runtime не
   содержит их названий и специальной логики.
3. Работает путь: подбор → карточка → draft → checkpoint → mock-ЭЦП → отправка →
   кабинет → изменение статуса → следующий этап.
4. Работает путь: текст программы → AI Definition → validation → preview →
   human publish → услуга появляется в `/take` без redeploy.
5. На странице 3–6 ручных полей одной темы; переход сохраняет всё введённое.
6. Draft продолжается с другого устройства; старый PATCH не затирает новый.
7. Rules, formulas, validation и lifecycle проверяются сервером и тестами.
8. Mock-интеграции явно маркированы; неподтверждённые цифры не выдаются за факты.
9. GitHub содержит воспроизводимый запуск, архитектуру, тесты и runbook.

Вне MVP: реальные eGov/ГБД/ЭЦП/BPM без доступов, полный KZ-перевод, миграция
draft между Definition versions, отдельный demo-mode, SMS, enterprise BPM и
обязательный антивирусный сервис.

## 2. Приоритеты

| Приоритет | Результат |
|---|---|
| P0 | DSL + engine + две услуги без hardcode |
| P0 | `/take`, `/create`, AI/fallback, публичный deploy |
| P1 | кабинет, многоэтапность, mock BPM, тесты ядра |
| P1 | карта, аналитика, инструменты — работающие срезы |
| P2 | расширенная админка, полировка, дополнительные данные |

За 24 часа до дедлайна scope замораживается. P2 не блокирует P0/P1.

## 3. Архитектура

```text
Internet → Nginx
              ├─ /baiterek/take/*   → Next.js
              ├─ /baiterek/create/* → Next.js
              └─ /baiterek/api/*    → FastAPI
                                           ├─ PostgreSQL
                                           ├─ LLMProvider real/mock
                                           └─ integration ports real/mock
```

Структура:

```text
backend/app/{api,models,schemas,engine,ai,integrations,seed}
backend/{alembic,tests}
frontend/app/baiterek/{take,create}
frontend/components/{form-engine,constructor}
docs/{service-definition,integration-contracts,traceability,verify-register,runbook}
deploy/nginx
```

Инварианты:

- published Definition-version неизменяема;
- application всегда ссылается на точную версию;
- frontend не источник истины для validation/computed;
- rules/formulas — whitelist без `eval`;
- AI проходит JSON Schema и semantic validation;
- mock и real adapters реализуют один интерфейс;
- AI не публикует автономно; admin actions пишутся в audit log.

## 4. Git-процесс

Рабочая ветка — `main`. Все последующие push:

```bash
git status --short
git diff --check
make lint
make test
git push origin main
```

Один коммит — один результат. Форматы: `feat(engine): ...`, `feat(take): ...`,
`feat(create): ...`, `test(engine): ...`, `fix(draft): ...`.

Нельзя коммитить `.env`, ключи, ПДн, файлы пользователей, dumps, cache/build.
DoD задачи: код, тест, negative path, docs, lint/test и доказательство приёмки.

## 5. Этап 0 — окружение и каркас

### Backend

- Python 3.12, FastAPI, Pydantic Settings, SQLAlchemy async, Alembic.
- `/health/live`, `/health/ready`; ready проверяет БД.
- JSON logs, trace ID, ошибка `{code,message,details,trace_id}`.

### Frontend

- Next.js App Router, TypeScript strict, Tailwind, shadcn, react-hook-form.
- Base path `/baiterek`; shell `take/create`; responsive/accessibility baseline.

### Infrastructure

- Multi-stage Dockerfiles; Compose: nginx, web, api, postgres.
- Healthchecks, restart, volume, `.env.example`, Makefile.
- CI: backend tests, frontend lint/typecheck/build, secret scan.

**Приёмка:** чистая машина поднимает проект по README; оба URL доступны; БД не
публикуется наружу. Первый VM deploy выполняется на этом этапе.

## 6. Этап 1 — данные и Service Definition DSL

### Миграции

Таблицы: organizations, users, service_definitions, applications, documents,
dictionaries, notifications, analytics_materials, map_projects, knowledge_items,
audit_log. Ограничения:

- unique `(service_id, version)`;
- FK application на Definition/version;
- optimistic `revision` у application;
- один active draft на `(user, service, service_version)`;
- индексы status/user/service/org/updated_at; UTC timestamps.

### DSL v1

- meta, stages, steps, fields, rules, computed, statuses, integrations;
- discriminated union типов полей;
- уникальные keys и проверка ссылок;
- обнаружение циклов formulas и неверных transitions;
- `schema_version` и экспорт JSON Schema.

### Версии

- draft редактируем; publish транзакционно создаёт version+1;
- published version неизменяема; archive не ломает старые заявки;
- import/export выполняет lossless round trip.

**Приёмка:** неверные ссылки/formulas/statuses отклоняются; v2 не меняет v1;
grep/test подтверждает отсутствие hardcode контрольных услуг.

## 7. Этап 2 — runtime engine

### Rules

eq/ne/gt/gte/lt/lte/in/contains/and/or/not; show/hide, require/optional,
enable/disable и transitions. Результат содержит trace объяснения.

### Formulas

Decimal для денег; arithmetic, sum, min/max/round, if, annuity. Dependency graph,
защита от zero division/unknown function, объяснение результата.

### Renderer contract

Вход: Definition version + data + checkpoint + user context. Выход: stage/step/screen,
3–6 тематических ручных полей, prefill/computed отдельно, visibility, required,
validation, progress, explanations и переходы. Дробление экрана детерминировано.

### Validation/lifecycle

- delta validation на PATCH, полная — на submit;
- hidden field не required; computed нельзя подменить;
- state machine допускает только объявленные переходы;
- номер заявки, timeline и audit event создаются транзакционно;
- approval этапа I открывает этап II той же заявки.

**Тесты:** unit/property-based rules/formulas, API и lifecycle. Обе услуги работают
через один engine без специальных веток.

## 8. Этап 3 — клиентский контур /take

### Каталог и AI-intake

- hero, направления, услуги, поиск/фильтры, карточка из Definition.meta;
- AI выбирает из published catalog и задаёт уточнения;
- `meta.intake_mapping` переносит ответы в draft с provenance;
- keyword/MockLLM fallback работает без внешнего LLM.

### Draft/checkpoint API

- POST applications идемпотентно возвращает active draft;
- PATCH принимает delta, checkpoint, `expected_revision`;
- stale revision → 409; старый запрос не затирает новый;
- переход страницы делает flush поверх debounce 800 мс;
- resume возвращает Definition, data, provenance, checkpoint и renderer contract;
- «Начать заново» подтверждается и архивирует старый draft.

### Form engine

- 3–6 ручных полей одной темы; короткая тема может иметь меньше трёх;
- prefill — сводка с «Изменить»; inline errors не блокируют сохранение;
- repeaters, computed explanations, progress и возврат без потери;
- saving/saved/error/offline; keyboard/focus/contrast accessibility.

### Files, submit, кабинет

- allowlist, magic MIME, size limit, server filename, storage вне web-root;
- FileStorage interface с будущей заменой volume на S3/MinIO;
- review, AI completeness как совет, обязательная server validation;
- маркированная mock-ЭЦП; кабинет с drafts, timeline и дозагрузкой.

**Приёмка:** resume с другого браузера; переставленные PATCH не теряют новое;
back/forward сохраняют данные; обе услуги имеют happy и negative paths.

## 9. Этап 4 — административный контур /create

### Registry/constructor

- filters, statuses, versions, duplicate/archive/import/export;
- дерево stages→steps→fields, reorder, properties, rules/formulas/integrations;
- live preview на общем form-engine; autosave revision; session undo/redo.

### AI generator

```text
text/document → LLM → JSON extraction → JSON Schema → semantic validation
→ [VERIFY] warnings → draft → human preview/edit → publish
```

- prompt запрещает придумывать неизвестное;
- invalid output не портит draft; retry ограничен;
- MockLLMProvider детерминирован для CI/fallback;
- AI никогда не публикует самостоятельно.

### Publish

Preflight проверяет schema/references/formulas/meta/preview. Publish транзакционно
создаёт версию и audit event. Услуга появляется в `/take` без redeploy.

**Приёмка:** третья услуга создаётся без кода; v2 не ломает v1; invalid AI JSON
не публикуется; import/export сохраняет Definition полностью.

## 10. Этап 5 — контрольные услуги и достоверность

`docs/verify-register.md`: ID, услуга, условие, значение, официальный источник,
ответственный, статус, дата и решение UI. Без подтверждения точная цифра убирается,
используется «по условиям программы», значение не становится blocking validation.

Услуга A: два этапа; ЮЛ/ИП, вагон/авиа, новый/б.у., субсидия; repeater;
total/advance/financing/annuity; indicative approval открывает stage II.

Услуга B: КХ/ИП/ТОО/СПК, виды скота, пастбища, племенное назначение; repeaters;
расчёт по подтверждённой ставке; запрос дозагрузки.

Definitions загружаются через общий import/service API. Demo projects имеют
`is_demo=true`; test users полностью синтетические.

## 11. Этап 6 — конкурсные модули

- Аналитика: organization/type/period/source, проверенные links, controlled embed.
- Карта: Leaflet/OSM, GeoJSON, clustering, filters, summary, demo label.
- Материалы: guides, templates, checklists, reviews.
- Калькуляторы annuity/subsidy используют общий formula engine и disclaimer.

При дефиците времени — короткие работающие срезы без неработающих кнопок.

## 12. Этап 7 — безопасность

- HTTPS, headers, exact CORS, secure cookies или short JWT;
- RBAC entrepreneur/author/admin, CSRF при cookie auth, rate limits;
- synthetic-only public data; logs без ИИН/БИН, файлов и sensitive prompts;
- owner/role authorization; draft retention 30 дней;
- AI document — данные, не system instructions; limits/timeouts;
- ENV secrets и audit admin actions.

Security gate: dependency/secret scan, IDOR двух пользователей, fake MIME,
oversized file, forbidden transition и prompt-injection regression.

## 13. Этап 8 — тестирование

Пирамида: unit engine → PostgreSQL repositories → API → components → Playwright E2E.

Обязательные E2E:

1. Услуга A: draft/resume/submit I → approve → II.
2. Услуга B: AI-intake → prefill → branch → formula → submit.
3. Constructor: generate → edit → preview → publish → открыть в /take.
4. Revision conflict, v1/v2, RBAC/IDOR, LLM unavailable.

`docs/traceability.md`: REQ-ID → SPEC → implementation → test → public scenario.
Coverage engine ≥85%; frontend typecheck/build и P0 E2E на стенде зелёные.

## 14. Этап 9 — VM, эксплуатация и rollback

- nginx публикует HTTPS `/baiterek/*`; сервисы internal/localhost;
- deploy: pull main → build → migration → up → health → external smoke;
- additive migrations; DB backup перед migration и ежедневно, retention 7;
- один restore test; предыдущий image/tag сохраняется;
- JSON logs, rotation, disk/DB health, AI errors, autosave conflicts;
- alert владельцу при недоступности обоих URL.

```bash
git pull --ff-only origin main
docker compose build
docker compose run --rm api alembic upgrade head
docker compose up -d
curl -fsS https://bizdnai.com/baiterek/api/health/ready
```

## 15. Самостоятельная проверка жюри

Отдельного demo-mode нет. /take содержит примеры и две услуги. /create получает
безопасный test author account/одноразовый код. Mock-действия подписаны. README
содержит путь проверки за 5 минут, screenshots и ограничения.

Финальный smoke из чистого браузера/mobile: оба URL, draft/resume, обе услуги,
AI/fallback, публикация, карта, аналитика, calculator, 404/500, отсутствие
console errors, mixed content и stack traces.

## 16. Календарь до 12.07.2026

### 07.07 — архитектура и skeleton

Утвердить план; Этап 0; migrations/DSL skeleton; JSON Schema v1; fixtures; shell deploy.
Контроль: оба URL открываются, CI зелёный.

### 08.07 — engine и draft backend

Этапы 1–2; revision/checkpoint API; unit/API tests; dictionaries.
Контроль: обе Definition исполняются через API без UI.

### 09.07 — /take

Catalog, form engine, autosave/resume, prefill, computed, submit, cabinet, mocks.
Контроль: полный путь услуги B на публичном стенде.

### 10.07 — /create и многоэтапность

Registry, constructor, preview, import/export, AI generator, publish/versioning, услуга A.
Контроль: третья услуга создаётся без изменения кода.

### 11.07 — модули и hardening

Карта/аналитика/materials; security tests; E2E; [VERIFY]; backup/restore; runbook.
Контроль: release candidate и scope freeze.

### 12.07 — выпуск

Production build/migrations; external/mobile smoke; screenshots/docs; secret scan;
после утверждения tag `v0.1.0-submission`. Новые функции запрещены.

## 17. Критический путь и риски

```text
Environment → DSL → Engine → Draft API → /take → deploy → E2E
                    └──────── Definition API → /create
```

| Риск | Мера |
|---|---|
| Scope на 5 дней | P0 freeze, vertical slices, P2 последним |
| Hardcode услуг | grep/test invariant, только Definition |
| Невалидный AI JSON | schema + semantics + retry + mock fallback |
| Непроверенные условия | [VERIFY], без точной цифры |
| Autosave теряет данные | revision + flush + conflict E2E |
| Prefix ломает assets/API | ранний deploy/smoke |
| Public admin портит данные | test role/tenant, limits, reset seed |
| Mock принят за интеграцию | явная маркировка |
| VM/DB отказ | health, backup, restore, rollback, alert |
| Секрет в GitHub | staged review, gitignore, secret scan |

## 18. Решения на утверждение

Утверждение означает:

1. `main` — ветка MVP и всех последующих push.
2. Сначала engine и клиентский critical path, затем дополнительные модули.
3. Публичный production-like стенд без отдельного demo-mode.
4. Маркированные mocks вместо недоступных госинтеграций.
5. Неподтверждённые цифры не становятся фактами/blocking rules.
6. AI всегда проходит validation и human publish.
7. Scope freeze за 24 часа до дедлайна.
