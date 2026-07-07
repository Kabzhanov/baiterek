import { constructorStages, serviceDefinitions, services } from "./mock-data";
import type { ConstructorStage, Service, ServiceDefinition } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/baiterek/api";

async function request<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${API_URL}${path}`, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) throw new Error(`API ${response.status}`);
    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

export const portalApi = {
  listServices: () => request<Service[]>("/services", services),
  // GET /api/v1/services — договорной контракт: {id, slug, meta{title, org, category,
  // audience, summary_plain, conditions[], documents_checklist[], result, sla_days}}[].
  // При недоступности backend — фолбэк на mock-data.
  listServiceDefinitions: () => request<ServiceDefinition[]>("/v1/services", serviceDefinitions),
  getConstructorDraft: () => request<ConstructorStage[]>("/admin/definitions/draft", constructorStages),
};
