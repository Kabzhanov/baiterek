// Pure tree operations for the definitions constructor (SPEC.md §5.2: дерево
// этапы→шаги→поля, add/remove/move, свойства элемента; IMPLEMENTATION_PLAN.md §9).
// Kept free of React/DOM/fetch so it is unit-testable directly
// (see definition-editor.test.ts) — the editor component owns all I/O.
//
// Все операции иммутабельны: возвращают новый документ, не трогая исходный.
// Ключи (key) генерируются автоматически и уникальны в своей области видимости —
// это зеркалит серверный валидатор definition.py («duplicate stage/step/field key»).

import type { FieldKind } from "./application-types";
import type {
  AdminDefinitionDoc,
  AdminField,
  AdminStage,
  AdminStep,
} from "./definition-admin-types";

// --- Выбор элемента в дереве --------------------------------------------------------

export type EditorSelection =
  | { kind: "meta" }
  | { kind: "stage"; stage: string }
  | { kind: "step"; stage: string; step: string }
  | { kind: "field"; stage: string; step: string; field: string };

// --- Генерация ключей ----------------------------------------------------------------

/** Возвращает `base`, либо `base-2`, `base-3`, … — первый не занятый в `existing`. */
export function uniqueKey(base: string, existing: string[]): string {
  const taken = new Set(existing);
  if (!taken.has(base)) return base;
  let n = 2;
  while (taken.has(`${base}-${n}`)) n += 1;
  return `${base}-${n}`;
}

function stageKeys(doc: AdminDefinitionDoc): string[] {
  return doc.stages.map((s) => s.key);
}

function stepKeys(doc: AdminDefinitionDoc): string[] {
  return doc.stages.flatMap((s) => s.steps.map((st) => st.key));
}

/** Ключи полей и computed живут в одном пространстве имён (валидатор definition.py). */
function fieldKeys(doc: AdminDefinitionDoc): string[] {
  return [
    ...doc.stages.flatMap((s) => s.steps.flatMap((st) => st.fields.map((f) => f.key))),
    ...doc.computed.map((c) => c.key),
  ];
}

// --- Заготовки ------------------------------------------------------------------------

function generateUuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = Math.floor(Math.random() * 16);
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/** Новое поле с типовыми значениями по умолчанию (select сразу получает options —
 * пустой список options не проходит серверную схему осмысленно). */
export function createField(type: FieldKind, existingKeys: string[]): AdminField {
  const key = uniqueKey("field", existingKeys);
  const base: AdminField = { key, label: "Новое поле", type, topic: "main", required: false };
  if (type === "select") return { ...base, options: ["Вариант 1", "Вариант 2"] };
  if (type === "number") return { ...base, minimum: null, maximum: null };
  return base;
}

/** Пустой draft новой услуги: один этап → один шаг → одно текстовое поле, чтобы превью
 * «глазами клиента» сразу было живым, плюс статусный поток по умолчанию. */
export function createEmptyDefinition(title: string): AdminDefinitionDoc {
  return {
    schema_version: "1.0",
    service_id: generateUuid(),
    version: 1,
    meta: {
      title,
      description: "",
      labels_plain: {
        submitted: "Заявка отправлена",
        in_review: "Заявка на рассмотрении",
        approved: "Заявка одобрена",
        rejected: "Заявка отклонена",
      },
      conditions: [],
      documents_checklist: [],
    },
    stages: [
      {
        key: "stage-1",
        title: "Основные сведения",
        steps: [
          {
            key: "step-1",
            title: "О заявителе",
            fields: [
              { key: "applicant_name", label: "Наименование заявителя", type: "text", topic: "main", required: true },
            ],
          },
        ],
      },
    ],
    rules: [],
    computed: [],
    statuses: ["submitted", "in_review", "approved", "rejected"],
    transitions: [],
    integrations: [],
  };
}

// --- Вспомогательные обходы -----------------------------------------------------------

function mapStage(
  doc: AdminDefinitionDoc,
  stageKey: string,
  fn: (stage: AdminStage) => AdminStage,
): AdminDefinitionDoc {
  return { ...doc, stages: doc.stages.map((s) => (s.key === stageKey ? fn(s) : s)) };
}

function mapStep(
  doc: AdminDefinitionDoc,
  stageKey: string,
  stepKey: string,
  fn: (step: AdminStep) => AdminStep,
): AdminDefinitionDoc {
  return mapStage(doc, stageKey, (stage) => ({
    ...stage,
    steps: stage.steps.map((st) => (st.key === stepKey ? fn(st) : st)),
  }));
}

function moveItem<T>(items: T[], index: number, direction: -1 | 1): T[] {
  const target = index + direction;
  if (index < 0 || target < 0 || target >= items.length) return items;
  const next = [...items];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

export function findStage(doc: AdminDefinitionDoc, stageKey: string): AdminStage | undefined {
  return doc.stages.find((s) => s.key === stageKey);
}

export function findStep(
  doc: AdminDefinitionDoc,
  stageKey: string,
  stepKey: string,
): AdminStep | undefined {
  return findStage(doc, stageKey)?.steps.find((st) => st.key === stepKey);
}

export function findField(
  doc: AdminDefinitionDoc,
  stageKey: string,
  stepKey: string,
  fieldKey: string,
): AdminField | undefined {
  return findStep(doc, stageKey, stepKey)?.fields.find((f) => f.key === fieldKey);
}

// --- Этапы ------------------------------------------------------------------------------

export function addStage(doc: AdminDefinitionDoc): { doc: AdminDefinitionDoc; key: string } {
  const key = uniqueKey("stage", stageKeys(doc));
  const step: AdminStep = { key: uniqueKey("step", stepKeys(doc)), title: "Новый шаг", fields: [] };
  const stage: AdminStage = { key, title: "Новый этап", steps: [step] };
  return { doc: { ...doc, stages: [...doc.stages, stage] }, key };
}

export function removeStage(doc: AdminDefinitionDoc, stageKey: string): AdminDefinitionDoc {
  return { ...doc, stages: doc.stages.filter((s) => s.key !== stageKey) };
}

export function moveStage(
  doc: AdminDefinitionDoc,
  stageKey: string,
  direction: -1 | 1,
): AdminDefinitionDoc {
  const index = doc.stages.findIndex((s) => s.key === stageKey);
  return { ...doc, stages: moveItem(doc.stages, index, direction) };
}

export function updateStage(
  doc: AdminDefinitionDoc,
  stageKey: string,
  patch: Partial<Pick<AdminStage, "title">>,
): AdminDefinitionDoc {
  return mapStage(doc, stageKey, (stage) => ({ ...stage, ...patch }));
}

// --- Шаги --------------------------------------------------------------------------------

export function addStep(
  doc: AdminDefinitionDoc,
  stageKey: string,
): { doc: AdminDefinitionDoc; key: string } {
  const key = uniqueKey("step", stepKeys(doc));
  const next = mapStage(doc, stageKey, (stage) => ({
    ...stage,
    steps: [...stage.steps, { key, title: "Новый шаг", fields: [] }],
  }));
  return { doc: next, key };
}

export function removeStep(
  doc: AdminDefinitionDoc,
  stageKey: string,
  stepKey: string,
): AdminDefinitionDoc {
  return mapStage(doc, stageKey, (stage) => ({
    ...stage,
    steps: stage.steps.filter((st) => st.key !== stepKey),
  }));
}

export function moveStep(
  doc: AdminDefinitionDoc,
  stageKey: string,
  stepKey: string,
  direction: -1 | 1,
): AdminDefinitionDoc {
  return mapStage(doc, stageKey, (stage) => {
    const index = stage.steps.findIndex((st) => st.key === stepKey);
    return { ...stage, steps: moveItem(stage.steps, index, direction) };
  });
}

export function updateStep(
  doc: AdminDefinitionDoc,
  stageKey: string,
  stepKey: string,
  patch: Partial<Pick<AdminStep, "title">>,
): AdminDefinitionDoc {
  return mapStep(doc, stageKey, stepKey, (step) => ({ ...step, ...patch }));
}

// --- Поля --------------------------------------------------------------------------------

export function addField(
  doc: AdminDefinitionDoc,
  stageKey: string,
  stepKey: string,
  type: FieldKind = "text",
): { doc: AdminDefinitionDoc; key: string } {
  const field = createField(type, fieldKeys(doc));
  const next = mapStep(doc, stageKey, stepKey, (step) => ({
    ...step,
    fields: [...step.fields, field],
  }));
  return { doc: next, key: field.key };
}

export function removeField(
  doc: AdminDefinitionDoc,
  stageKey: string,
  stepKey: string,
  fieldKey: string,
): AdminDefinitionDoc {
  return mapStep(doc, stageKey, stepKey, (step) => ({
    ...step,
    fields: step.fields.filter((f) => f.key !== fieldKey),
  }));
}

export function moveField(
  doc: AdminDefinitionDoc,
  stageKey: string,
  stepKey: string,
  fieldKey: string,
  direction: -1 | 1,
): AdminDefinitionDoc {
  return mapStep(doc, stageKey, stepKey, (step) => {
    const index = step.fields.findIndex((f) => f.key === fieldKey);
    return { ...step, fields: moveItem(step.fields, index, direction) };
  });
}

export function updateField(
  doc: AdminDefinitionDoc,
  stageKey: string,
  stepKey: string,
  fieldKey: string,
  patch: Partial<AdminField>,
): AdminDefinitionDoc {
  return mapStep(doc, stageKey, stepKey, (step) => ({
    ...step,
    fields: step.fields.map((f) => (f.key === fieldKey ? { ...f, ...patch } : f)),
  }));
}

/** Смена типа поля с приведением типовых свойств: select всегда получает options,
 * number — minimum/maximum; свойства чужого типа снимаются, чтобы JSON оставался
 * валидным для дискриминированной union-схемы definition.py. */
export function changeFieldType(
  doc: AdminDefinitionDoc,
  stageKey: string,
  stepKey: string,
  fieldKey: string,
  type: FieldKind,
): AdminDefinitionDoc {
  return mapStep(doc, stageKey, stepKey, (step) => ({
    ...step,
    fields: step.fields.map((f) => {
      if (f.key !== fieldKey) return f;
      const next: AdminField = {
        key: f.key,
        label: f.label,
        type,
        topic: f.topic,
        required: f.required,
      };
      if (f.hint) next.hint = f.hint;
      if (type === "select") next.options = f.options?.length ? f.options : ["Вариант 1"];
      if (type === "number") {
        next.minimum = f.minimum ?? null;
        next.maximum = f.maximum ?? null;
      }
      return next;
    }),
  }));
}

// --- Meta ---------------------------------------------------------------------------------

export function updateMeta(
  doc: AdminDefinitionDoc,
  patch: Partial<AdminDefinitionDoc["meta"]>,
): AdminDefinitionDoc {
  return { ...doc, meta: { ...doc.meta, ...patch } };
}

// --- Валидация (инлайн-подсказки редактора; зеркалит серверные проверки definition.py) -----

export type ValidationIssue = {
  /** Куда указывает проблема — в формате selection, чтобы редактор мог подсветить узел. */
  selection: EditorSelection;
  message: string;
};

export function validateDefinition(doc: AdminDefinitionDoc): ValidationIssue[] {
  const issues: ValidationIssue[] = [];

  if (!doc.meta.title.trim()) {
    issues.push({ selection: { kind: "meta" }, message: "Укажите название услуги" });
  }
  if (doc.stages.length === 0) {
    issues.push({ selection: { kind: "meta" }, message: "Добавьте хотя бы один этап" });
  }

  const seenStages = new Set<string>();
  const seenSteps = new Set<string>();
  const seenFields = new Set<string>(doc.computed.map((c) => c.key));

  for (const stage of doc.stages) {
    const stageSel: EditorSelection = { kind: "stage", stage: stage.key };
    if (!stage.title.trim()) issues.push({ selection: stageSel, message: "Пустое название этапа" });
    if (seenStages.has(stage.key)) {
      issues.push({ selection: stageSel, message: `Дублируется ключ этапа «${stage.key}»` });
    }
    seenStages.add(stage.key);
    if (stage.steps.length === 0) {
      issues.push({ selection: stageSel, message: "В этапе нет ни одного шага" });
    }

    for (const step of stage.steps) {
      const stepSel: EditorSelection = { kind: "step", stage: stage.key, step: step.key };
      if (!step.title.trim()) issues.push({ selection: stepSel, message: "Пустое название шага" });
      if (seenSteps.has(step.key)) {
        issues.push({ selection: stepSel, message: `Дублируется ключ шага «${step.key}»` });
      }
      seenSteps.add(step.key);

      for (const field of step.fields) {
        const fieldSel: EditorSelection = {
          kind: "field",
          stage: stage.key,
          step: step.key,
          field: field.key,
        };
        if (!field.label.trim()) {
          issues.push({ selection: fieldSel, message: "Пустой label поля" });
        }
        if (!field.key.trim()) {
          issues.push({ selection: fieldSel, message: "Пустой ключ поля" });
        }
        if (seenFields.has(field.key)) {
          issues.push({ selection: fieldSel, message: `Дублируется ключ поля «${field.key}»` });
        }
        seenFields.add(field.key);
        if (field.type === "select" && !(field.options ?? []).some((o) => o.trim())) {
          issues.push({ selection: fieldSel, message: "У справочника нет ни одного варианта" });
        }
        if (
          field.type === "number" &&
          field.minimum != null &&
          field.maximum != null &&
          field.minimum > field.maximum
        ) {
          issues.push({ selection: fieldSel, message: "Минимум больше максимума" });
        }
      }
    }
  }

  if (doc.statuses.length === 0) {
    issues.push({ selection: { kind: "meta" }, message: "Не задан ни один статус заявки" });
  }

  return issues;
}

/** true, если issue указывает ровно на этот элемент дерева. */
export function issueMatches(issue: ValidationIssue, selection: EditorSelection): boolean {
  const a = issue.selection;
  if (a.kind !== selection.kind) return false;
  if (a.kind === "meta") return true;
  if (a.kind === "stage" && selection.kind === "stage") return a.stage === selection.stage;
  if (a.kind === "step" && selection.kind === "step") {
    return a.stage === selection.stage && a.step === selection.step;
  }
  if (a.kind === "field" && selection.kind === "field") {
    return a.stage === selection.stage && a.step === selection.step && a.field === selection.field;
  }
  return false;
}
