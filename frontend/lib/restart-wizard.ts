// «Начать заново» в мастере анкеты (SPEC.md §6, п.7). Бэкенд не умеет restart/reset
// (POST /applications идемпотентен и всегда возвращает существующий черновик, а
// PATCH .../draft только сливает data_delta и не удаляет ключи — см.
// backend/app/api/applications.py). Поэтому «чистим» черновик клиентски: одним PATCH
// перезаписываем каждое заполненное поле его «пустым» значением и возвращаем checkpoint
// на самый первый экран. Это не ломает autosave/многоэтапность — идёт тем же PATCH-
// контрактом, что и обычная правка. Логика вынесена сюда, чтобы её можно было проверить
// юнит-тестом без DOM (см. restart-wizard.test.ts).
import type { Checkpoint } from "./application-types";
import type { PlanScreen } from "./screen-plan";

export const RESTART_CONFIRM_MESSAGE =
  "Начать заново? Всё, что уже введено в этой заявке, будет очищено. Отменить это действие нельзя.";

/** «Пустое» значение того же вида, что и текущее: [] для списков, "" для остального.
 * Пустая строка через merge-PATCH затирает прежнее значение поля (бэкенд не удаляет
 * ключи), а на resume читается как незаполненное поле. */
function emptyLike(value: unknown): unknown {
  return Array.isArray(value) ? [] : "";
}

/** Delta, обнуляющая КАЖДОЕ непустое поле текущего черновика. Пустые/уже-очищенные поля
 * не включаем — незачем гонять их по сети. */
export function buildRestartDelta(data: Record<string, unknown>): Record<string, unknown> {
  const delta: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(data)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value) && value.length === 0) continue;
    delta[key] = emptyLike(value);
  }
  return delta;
}

/** Checkpoint самого первого экрана плана — точка, куда возвращаем мастер после сброса. */
export function firstScreenCheckpoint(plan: PlanScreen[]): Checkpoint | null {
  const first = plan[0];
  if (!first) return null;
  return { stage_key: first.stageKey, step_key: first.stepKey, screen_key: first.screenKey };
}
