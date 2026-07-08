// Client for the admin definitions API (SPEC.md §5, IMPLEMENTATION_PLAN.md §9).
// Built on the same `call()` transport as lib/application-api.ts — deliberately NOT on
// lib/api.ts's mock-fallback `request()`: админ-контур обязан честно показывать
// «стенд недоступен» (BackendUnavailableError), а не рисовать фейковый реестр.
//
// Контракт (бэкенд реализуется параллельно, см. definition-admin-types.ts):
//   GET    /api/v1/admin/definitions                 → DefinitionListItem[]
//   GET    /api/v1/admin/definitions/{id}            → DefinitionDetail
//   POST   /api/v1/admin/definitions {slug, definition} → DefinitionDetail (draft)
//   PUT    /api/v1/admin/definitions/{id} {definition}  → DefinitionDetail (только draft)
//   POST   /api/v1/admin/definitions/{id}/publish    → DefinitionDetail (version+1)
//   POST   /api/v1/admin/definitions/{id}/duplicate  → DefinitionDetail (новый draft)
//   GET    /api/v1/admin/definitions/{id}/export     → JSON формы Definition
//   POST   /api/v1/admin/definitions/generate {text} → GenerateOut

import { call } from "./application-api";
import type {
  AdminDefinitionDoc,
  DefinitionDetail,
  DefinitionListItem,
  GenerateOut,
} from "./definition-admin-types";

const BASE = "/v1/admin/definitions";

export const definitionAdminApi = {
  // Бэкенд отдаёт список в обёртке {items: [...]} (как и кабинет), поэтому разворачиваем
  // до массива — компонент реестра работает с DefinitionListItem[].
  list: async () => (await call<{ items: DefinitionListItem[] }>(BASE)).items,
  get: (id: string) => call<DefinitionDetail>(`${BASE}/${encodeURIComponent(id)}`),
  create: (slug: string, definition: AdminDefinitionDoc) =>
    call<DefinitionDetail>(BASE, {
      method: "POST",
      body: JSON.stringify({ slug, definition }),
    }),
  update: (id: string, definition: AdminDefinitionDoc) =>
    call<DefinitionDetail>(`${BASE}/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify({ definition }),
    }),
  publish: (id: string) =>
    call<DefinitionDetail>(`${BASE}/${encodeURIComponent(id)}/publish`, { method: "POST" }),
  duplicate: (id: string) =>
    call<DefinitionDetail>(`${BASE}/${encodeURIComponent(id)}/duplicate`, { method: "POST" }),
  exportJson: (id: string) => call<unknown>(`${BASE}/${encodeURIComponent(id)}/export`),
  generate: (text: string) =>
    call<GenerateOut>(`${BASE}/generate`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
};

/** Скачивает произвольный JSON как файл (экспорт Definition из реестра). */
export function downloadJson(payload: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
