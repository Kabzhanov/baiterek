export type Service = {
  id: string;
  title: string;
  summary: string;
  category: string;
  duration: string;
  audience: string;
  tags: string[];
};

export type FieldDefinition = {
  key: string;
  label: string;
  type: "text" | "select" | "number" | "textarea";
  required?: boolean;
  placeholder?: string;
  options?: string[];
  hint?: string;
};

export type ConstructorStage = { id: string; title: string; steps: number; fields: number };

export type ServiceCondition = { label: string; value: string };

export type ServiceMeta = {
  title: string;
  org: string;
  category: string;
  audience: string;
  summary_plain: string;
  conditions: ServiceCondition[];
  documents_checklist: string[];
  result: string;
  sla_days: number;
};

export type ServiceDefinition = { id: string; slug: string; meta: ServiceMeta };

// Content module (SPEC.md §4.5-4.7): карта проектов / аналитика / инструменты и
// материалы. Mirrors `backend/app/api/contracts.py`'s Map*/AnalyticsMaterial*/
// KnowledgeItem* Pydantic models.

export type MapProject = {
  id: string;
  org_id: string;
  organization: string;
  name: string;
  region_code: string;
  locality: string | null;
  lat: string;
  lng: string;
  industry: string | null;
  amount: string | null;
  period_start: string | null;
  period_end: string | null;
  status: string;
  description: string | null;
  is_demo: boolean;
};

export type MapRegionSummary = { region_code: string; count: number; amount: string };

export type MapSummary = { total_count: number; total_amount: string; by_region: MapRegionSummary[] };

export type MapFilters = { organization?: string; region?: string; industry?: string; status?: string };

export type AnalyticsMaterial = {
  id: string;
  org_id: string;
  organization: string;
  type: "dashboard" | "report" | "financial" | "research";
  title: string;
  description: string | null;
  source: string | null;
  period: string | null;
  url: string | null;
  embed_allowed: boolean;
};

export type AnalyticsFilters = { organization?: string; type?: string };

export type KnowledgeItem = {
  id: string;
  category: "guide" | "template" | "checklist" | "calculator" | "review";
  title: string;
  description: string | null;
  content: string | null;
  url: string | null;
};
