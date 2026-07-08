// Types mirroring `backend/app/api/contracts.py` and the JSON shapes produced by
// `backend/app/engine/runtime.render()` / `backend/app/api/screen.py` (checkpoint,
// screen contract). Kept separate from `lib/types.ts` (the catalog/constructor mock
// types) because that file's `ServiceDefinition`/`ServiceMeta` do not match this
// backend's actual response shape (e.g. `audience` is a list here, a mock string
// there) — conflating them would make one of the two wrong.

export type FieldKind = "text" | "number" | "boolean" | "select" | "repeater" | string;

export type DefinitionField = {
  key: string;
  label: string;
  type: FieldKind;
  topic?: string;
  required?: boolean;
  minimum?: number | null;
  maximum?: number | null;
  options?: string[];
  // Предзаполнение по БИН (SPEC.md §3.2, "Обязательное расширение" §1) — см.
  // `backend/app/schemas/definition.py::FieldBase` for the "gbd_ul.lookup" /
  // "gbd_ul.<attr>" convention this mirrors. `hint` is independent free-text help.
  prefill?: string | null;
  hint?: string | null;
};

export type DefinitionStep = { key: string; title: string; fields: DefinitionField[] };
export type DefinitionStage = { key: string; title: string; steps: DefinitionStep[] };

export type ServiceDefinitionDoc = {
  schema_version: string;
  service_id: string;
  version: number;
  meta: { title: string; description: string; labels_plain?: Record<string, string> };
  stages: DefinitionStage[];
  rules: unknown[];
  computed: { key: string; expression: unknown }[];
  statuses: string[];
  transitions: unknown[];
  integrations: string[];
};

export type ScreenField = {
  key: string;
  type: FieldKind;
  label: string;
  visible: boolean;
  required: boolean;
  enabled: boolean;
  // Всегда присутствуют в ответе (`backend/app/api/screen.py`/`app/engine/runtime.render()`
  // ferry both through unconditionally) — `null` when the Definition field carries none.
  prefill: string | null;
  hint: string | null;
};

export type ScreenValidationItem = { field?: string | null; code: string; message?: string };

export type ScreenContract = {
  stage: string;
  step: string;
  screen: number;
  fields: ScreenField[];
  computed: Record<string, unknown>;
  validation: ScreenValidationItem[];
  progress: { current: number; total: number };
  explanations: { rules: string[]; computed: Record<string, string[]> };
};

// `screen_key`/`stage_key`/`step_key` are `null` before the first render (POST
// /applications derives one immediately, so in practice this is only ever null for a
// step with zero fields — see `screen.py::to_checkpoint`).
export type Checkpoint = { stage_key: string | null; step_key: string | null; screen_key: string | null };

export type ApplicationOut = {
  id: string;
  service_id: string;
  service_version: number;
  status: string;
  revision: number;
  number: string | null;
  checkpoint: Checkpoint;
  data: Record<string, unknown>;
};

export type DraftPatchOut = { id: string; revision: number; checkpoint: Checkpoint; screen: ScreenContract };

export type ResumeOut = {
  id: string;
  service_id: string;
  service_version: number;
  status: string;
  revision: number;
  data: Record<string, unknown>;
  checkpoint: Checkpoint;
  definition: ServiceDefinitionDoc;
  screen: ScreenContract;
  // Многоэтапность (SPEC.md §4.3, "Обязательное расширение" контракт A): ключи уже
  // отправленных этапов и признак, что этап, на который сейчас указывает checkpoint,
  // ещё открыт для правки. См. lib/stage-progress.ts для чистой логики поверх этого.
  completed_stages: string[];
  stage_open: boolean;
};

// `event: "submitted"` несёт `stage` (какой этап отправлен); `event: "admin_status_change"`
// несёт `comment`; `event: "stage_opened"` несёт `stage` (какой этап открылся). Все три
// формы делят один и тот же JSON-блоб `application.timeline` на бэке — оба свойства
// оставляем опциональными, а не заводим union, т.к. вызывающий код читает конкретное поле
// только когда оно осмысленно (SubmitOut.timeline — `stage`, см. application-wizard.tsx).
export type TimelineEntry = { status: string; at: string; event: string; stage?: string | null; comment?: string | null };

export type SubmitOut = {
  id: string;
  number: string;
  status: string;
  timeline: TimelineEntry[];
};

export type ApiErrorBody = { code: string; message: string; details: Record<string, unknown>; trace_id: string };

// Личный кабинет (SPEC.md §4.4, "Обязательное расширение" §2) — зеркала
// `CabinetApplicationItem`/`CabinetApplicationDetail` из backend/app/api/contracts.py.
export type CabinetServiceInfo = { slug: string; title: string };

export type CabinetApplicationItem = {
  id: string;
  number: string | null;
  status: string;
  service: CabinetServiceInfo;
  service_version: number;
  checkpoint: Checkpoint;
  // Заполненные видимые поля / все видимые поля, 0-100 («заполнена на N%»).
  progress_percent: number;
  labels_plain: Record<string, string>;
  updated_at: string;
};

export type CabinetListOut = { items: CabinetApplicationItem[] };

export type CabinetNotification = {
  id: string;
  type: string;
  title: string;
  body: string;
  created_at: string;
  read_at: string | null;
};

export type CabinetApplicationDetail = CabinetApplicationItem & {
  created_at: string;
  timeline: TimelineEntry[];
  documents: unknown[]; // файловый контур ещё не реализован — приходит пустым
  notifications: CabinetNotification[];
};

// Mock ГБД ЮЛ (SPEC.md §8) — зеркало `backend/app/api/integrations.py::GbdUlOut`.
// Предзаполнение по БИН распределяет эти поля по целевым полям экрана, см.
// lib/gbd-ul-prefill.ts.
export type GbdUlOut = {
  bin: string;
  name: string;
  oked: string;
  oked_name: string;
  address: string;
  director: string;
  mock: boolean;
  disclaimer: string;
};

// AI-копайлоты (SPEC.md §7.1, AI-критерий 9.4) — зеркала `ExplainServiceOut`/
// `ApplicationCompletenessOut` из backend/app/api/contracts.py.
export type ExplainServiceOut = { text: string; degraded: boolean };

export type ApplicationCompletenessOut = { suggestions: string[]; degraded: boolean };

export type ServiceSummaryOut = {
  id: string;
  slug: string;
  meta: {
    title: string;
    org: string | null;
    category: string | null;
    audience: string[];
    summary_plain: string;
    conditions: { label: string; value: string }[];
    documents_checklist: string[];
    result: string | null;
    sla_days: number | null;
  };
};
