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
};

export type DefinitionStep = { key: string; title: string; fields: DefinitionField[] };
export type DefinitionStage = { key: string; title: string; steps: DefinitionStep[] };

export type ServiceDefinitionDoc = {
  schema_version: string;
  service_id: string;
  version: number;
  meta: { title: string; description: string };
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
};

export type SubmitOut = {
  id: string;
  number: string;
  status: string;
  timeline: { status: string; at: string; event: string }[];
};

export type ApiErrorBody = { code: string; message: string; details: Record<string, unknown>; trace_id: string };

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
