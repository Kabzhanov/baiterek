// Client for the public read-only content endpoints (SPEC.md §4.5-4.7):
// GET /map/projects, /map/summary, /analytics/materials, /knowledge/items.
// See `backend/app/api/content.py` for the exact routes/filters this mirrors.
//
// Same silent-fallback shape as `lib/api.ts`'s `portalApi` (these are public catalog
// reads, not user-owned mutating flows like `lib/application-api.ts`) — on any network
// error the caller gets an empty list instead of a thrown exception, so a page never
// crashes just because the backend is briefly unavailable.
import type { AnalyticsFilters, AnalyticsMaterial, KnowledgeItem, MapFilters, MapProject, MapSummary } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/baiterek/api";

const EMPTY_SUMMARY: MapSummary = { total_count: 0, total_amount: "0", by_region: [] };

function buildQuery(params: Record<string, string | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) search.set(key, value);
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

async function getJson<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${API_URL}${path}`, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) throw new Error(`API ${response.status}`);
    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

export const contentApi = {
  listMapProjects: (filters: MapFilters = {}) =>
    getJson<{ items: MapProject[] }>(`/v1/map/projects${buildQuery(filters)}`, { items: [] }).then((r) => r.items),
  getMapSummary: (filters: MapFilters = {}) => getJson<MapSummary>(`/v1/map/summary${buildQuery(filters)}`, EMPTY_SUMMARY),
  listAnalyticsMaterials: (filters: AnalyticsFilters = {}) =>
    getJson<{ items: AnalyticsMaterial[] }>(`/v1/analytics/materials${buildQuery(filters)}`, { items: [] }).then(
      (r) => r.items,
    ),
  listKnowledgeItems: (category?: string) =>
    getJson<{ items: KnowledgeItem[] }>(`/v1/knowledge/items${buildQuery({ category })}`, { items: [] }).then(
      (r) => r.items,
    ),
};
