# Матрица трассировки требований

Статусы: `PLAN` (спроектировано), `BUILD` (реализовано, автотеста ещё нет), `PASS`
(реализовано и покрыто зелёными автотестами), `BLOCKED`.

Актуально на прогон приёмки: **backend 136 pytest** (все зелёные, `backend/tests/`),
**frontend 87 vitest** (все зелёные, `frontend/lib/*.test.ts` + `frontend/components/**/**.test.tsx`).
Столбец «Доказательство» ссылается на реально существующие тест-файлы.

| REQ | Требование | Реализация | Доказательство (тест-файл) | Статус |
|---|---|---|---|---|
| R-DSL-01 | Услуги только через Definition | engine + seed import | `test_seed.py`, `test_engine.py`, `test_definition_runtime.py` | PASS |
| R-DSL-02 | Immutable published versions | repository/publish | `test_api_admin_definitions.py`, `test_api_services.py` | PASS |
| R-TAKE-01 | 3–6 тематических полей на экране | renderer + form-engine (`screen-plan`) | `test_definition_runtime.py`, `components/form-engine/dynamic-form.test.tsx` | PASS |
| R-TAKE-02 | Сохранение перехода без потерь (autosave + 409) | revision PATCH + flush | `test_api_applications.py`, `lib/draft-autosave.test.ts`, `lib/stage-progress.test.ts` | PASS |
| R-TAKE-03 | Resume заявки с checkpoint | server checkpoint / resume | `test_api_applications.py`, `test_multistage.py`, `test_api_cabinet.py` | PASS |
| R-TAKE-04 | «Начать заново» с подтверждением | frontend restart (clear+checkpoint→0) | `lib/restart-wizard.test.ts` | PASS |
| R-AI-01 | Schema-валидация ответа AI + деградация | AI gate + keyword-fallback | `test_ai_generation.py`, `test_ai_intake.py`, `test_api_intake.py` | PASS |
| R-AI-02 | Тематическое ранжирование подбора меры | `intake.keyword_match` синонимы | `test_ai_intake.py` (аграрный запрос → agro-livestock) | PASS |
| R-AI-03 | Копайлоты «объяснить»/«проверить полноту» (советуют, не блокируют) | copilot endpoints | `test_ai_explain.py`, `test_ai_completeness.py`, `test_api_copilot.py`, `lib/copilot.test.ts` | PASS |
| R-AI-04 | Учёт бюджета AI-вызовов | budget log | `test_ai_budget.py` | PASS |
| R-CREATE-01 | Третья услуга без кода (конструктор→публикация) | constructor/publish | `test_api_admin_definitions.py`, `lib/definition-editor.test.ts` | PASS |
| R-PREFILL-01 | Предзаполнение по БИН (ГБД ЮЛ, mock) | integrations + form-engine | `test_prefill.py`, `test_integrations.py`, `lib/gbd-ul-prefill.test.ts` | PASS |
| R-MULTI-01 | Многоэтапность заявки | stage lock/open + progress | `test_multistage.py`, `lib/stage-progress.test.ts` | PASS |
| R-SEC-01 | Нет IDOR заявок (404 по чужому id) | owner-check | `test_api_applications.py`, `test_api_cabinet.py`, `test_api_copilot.py` | PASS |
| R-SEC-02 | Open-access режим стенда | deps/roles | `test_open_access.py` | PASS |
| R-DATA-01 | Нет ложных цифр (контент из реестра) | verify register | `test_control_cases.py`, `test_api_content.py` | PASS |
| R-UPLOAD-01 | Безопасный upload (MIME/size) | — | автотест отсутствует | PLAN |
| R-OPS-01 | Два URL по HTTPS (портал + API) | nginx/compose | внешний smoke при деплое (не автотест) | BUILD |

Примечания:
- `R-UPLOAD-01` пока без реализации/теста — оставлен `PLAN`, чтобы матрица не завышала покрытие.
- `R-OPS-01` проверяется живым smoke после `docker compose up` (страницы `/take`, мастер, `POST /intake/match`), автоматизированного end-to-end HTTPS-теста в наборе нет — `BUILD`.
</content>
</invoke>
