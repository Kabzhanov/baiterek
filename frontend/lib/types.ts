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
