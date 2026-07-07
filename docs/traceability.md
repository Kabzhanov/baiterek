# Матрица трассировки требований

Статусы: `PLAN`, `BUILD`, `PASS`, `BLOCKED`. Обновляется с каждым коммитом.

| REQ | Требование | Реализация | Доказательство | Статус |
|---|---|---|---|---|
| R-DSL-01 | Услуги только через Definition | engine + seed import | invariant test + grep | BUILD |
| R-DSL-02 | Immutable published versions | repository | DB/API test | PLAN |
| R-TAKE-01 | 3–6 тематических полей | renderer + form-engine | unit + E2E | BUILD |
| R-TAKE-02 | Сохранение перехода | revision PATCH + flush | conflict E2E | PLAN |
| R-TAKE-03 | Resume с другого устройства | server checkpoint | cross-context E2E | PLAN |
| R-AI-01 | AI schema validation | AI gate | invalid JSON test | PLAN |
| R-CREATE-01 | Третья услуга без кода | constructor/publish | public E2E | PLAN |
| R-SEC-01 | Нет IDOR заявок | owner/RBAC | negative API test | PLAN |
| R-UPLOAD-01 | Безопасный upload | MIME/size/storage | negative API test | PLAN |
| R-OPS-01 | Два URL по HTTPS | nginx/compose | external smoke | PLAN |
| R-DATA-01 | Нет ложных цифр | verify register | content audit | BUILD |

