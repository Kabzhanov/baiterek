// Types for the admin definitions contour (SPEC.md §5, IMPLEMENTATION_PLAN.md §9):
// registry rows, editor document, AI-generator response. The backend admin API
// (/api/v1/admin/definitions*) is being built in parallel — these mirror the agreed
// contract, with `definition` itself matching `backend/app/schemas/definition.py`
// (the authoritative Pydantic schema, exported to docs/service-definition.schema.json).
//
// Kept separate from application-types.ts (client contour) the same way that file is
// kept separate from types.ts: the admin rows carry DB columns (status/version/slug)
// that are NOT part of the definition JSON blob itself.

import type { DefinitionField, ServiceDefinitionDoc } from "./application-types";

/** Статус строки service_definitions (колонка БД, не поле JSON). */
export type DefinitionStatus = "draft" | "published" | "archived";

/** Строка реестра: GET /api/v1/admin/definitions. */
export type DefinitionListItem = {
  id: string;
  service_id: string;
  slug: string;
  status: DefinitionStatus;
  version: number;
  title: string;
  updated_at: string;
};

/** Детальная карточка: GET /api/v1/admin/definitions/{id}. */
export type DefinitionDetail = DefinitionListItem & {
  definition: AdminDefinitionDoc;
};

/** Ответ AI-генератора: POST /api/v1/admin/definitions/generate {text}. */
export type GenerateOut = {
  id: string;
  warnings: string[];
  /** true — LLM-бюджет исчерпан, сработал MockLLMProvider (SPEC §7.3 «AI временно в демо-режиме»). */
  degraded?: boolean;
};

// --- Расширения формы Definition для редактора -------------------------------------
// Бэкенд-схема v1 (definition.py) знает только key/label/topic/required + типовые
// extras (number: minimum/maximum, select: options). Поля ниже (`hint`, meta.conditions,
// meta.documents_checklist) заявлены в SPEC §3.2/§5.2 и редактируются в конструкторе;
// вложенные Pydantic-модели их молча игнорируют (extra="forbid" стоит только на верхнем
// уровне ServiceDefinition), поэтому их наличие в JSON не ломает PUT/publish.

export type AdminField = DefinitionField & {
  /** Подсказка под полем (SPEC §5.2 «Редактор поля: … hint …»); бэкенд v1 игнорирует. */
  hint?: string;
};

export type AdminStep = { key: string; title: string; fields: AdminField[] };
export type AdminStage = { key: string; title: string; steps: AdminStep[] };

export type AdminMeta = {
  title: string;
  description: string;
  labels_plain?: Record<string, string>;
  /** Условия участия (карточка услуги «глазами клиента»); бэкенд v1 игнорирует. */
  conditions?: { label: string; value: string }[];
  /** Чек-лист документов; бэкенд v1 игнорирует. */
  documents_checklist?: string[];
};

export type AdminDefinitionDoc = Omit<ServiceDefinitionDoc, "meta" | "stages"> & {
  meta: AdminMeta;
  stages: AdminStage[];
};
