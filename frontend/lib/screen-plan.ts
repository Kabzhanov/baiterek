// Client-side mirror of the backend's screen chunking (`backend/app/api/screen.py`'s
// `_screen_chunks` / `app/engine/runtime.render()`'s `[fields[i:i+6] ...]`): splits every
// step's field list into screens of at most `SCREEN_SIZE` manual fields (SPEC.md
// "Обязательное расширение" §1, "правило 3–6"). Chunking is positional over the
// Definition's raw field order, independent of rule-driven visibility, so it is stable
// for a given Definition version — exactly what lets the wizard compute "what's the next
// screen" / "which level is this field in" locally, while the server's `screen` response
// (visible/required/enabled) always remains the source of truth for what to actually show.
import type { DefinitionField, ServiceDefinitionDoc } from "./application-types";

export const SCREEN_SIZE = 6;

export type PlanScreen = {
  planIndex: number;
  stageIndex: number;
  stepIndex: number;
  screenIndex: number;
  stageKey: string;
  stageTitle: string;
  stepKey: string;
  stepTitle: string;
  screenKey: string | null;
  fieldKeys: string[];
};

function chunk<T>(items: T[], size: number): T[][] {
  if (items.length === 0) return [[]];
  const chunks: T[][] = [];
  for (let i = 0; i < items.length; i += size) chunks.push(items.slice(i, i + size));
  return chunks;
}

/** Flattens a Definition into an ordered list of every screen across every stage/step. */
export function buildScreenPlan(definition: ServiceDefinitionDoc): PlanScreen[] {
  const plan: PlanScreen[] = [];
  definition.stages.forEach((stage, stageIndex) => {
    stage.steps.forEach((step, stepIndex) => {
      const chunks = chunk(step.fields, SCREEN_SIZE);
      chunks.forEach((fields, screenIndex) => {
        plan.push({
          planIndex: plan.length,
          stageIndex,
          stepIndex,
          screenIndex,
          stageKey: stage.key,
          stageTitle: stage.title,
          stepKey: step.key,
          stepTitle: step.title,
          screenKey: fields[0]?.key ?? null,
          fieldKeys: fields.map((f) => f.key),
        });
      });
    });
  });
  return plan;
}

/** Locates a screen by its `screen_key` (checkpoint addressing — SPEC.md §2: "НЕ порядковым
 * индексом… ключ поля — нет"). Falls back to the first screen if the key is stale/unknown,
 * mirroring the server's `resolve_indices` fallback. */
export function findPlanIndexByScreenKey(plan: PlanScreen[], screenKey: string | null | undefined): number {
  if (screenKey) {
    const found = plan.findIndex((p) => p.screenKey === screenKey || p.fieldKeys.includes(screenKey));
    if (found >= 0) return found;
  }
  return 0;
}

export function fieldIndex(definition: ServiceDefinitionDoc): Map<string, DefinitionField> {
  const map = new Map<string, DefinitionField>();
  for (const stage of definition.stages) {
    for (const step of stage.steps) {
      for (const field of step.fields) map.set(field.key, field);
    }
  }
  return map;
}
