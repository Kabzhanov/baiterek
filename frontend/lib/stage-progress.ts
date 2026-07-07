// Многоэтапность (SPEC.md §4.3 "Многоэтапность", "Обязательное расширение" контракт A):
// чистая логика поверх `ResumeOut.completed_stages`/`stage_open` и 409-кодов ошибок
// PATCH /draft, без React/DOM — тестируется отдельно от компонента
// (see stage-progress.test.ts). application-wizard.tsx и components/cabinet/* используют
// эти функции, не дублируя условия у себя.
import { ApplicationApiError } from "./application-api";

export type DraftErrorKind = "stage_locked" | "revision_conflict" | "other";

/** Различает два разных 409 у PATCH /applications/{id}/draft (backend/app/api/applications.py):
 * - `revision_conflict` — чужая параллельная правка того же черновика; безопасно
 *   разрешается повторным resume()+merge()+retry (см. lib/draft-autosave.ts::mergeAfterConflict).
 * - `stage_locked` — текущий этап УЖЕ отправлен и закрыт для правки (заявка на
 *   рассмотрении); повторная попытка сохранить тем же способом снова получит 409 —
 *   это не гонка редактирования, а «сейчас сюда нельзя», обрабатывается отдельно
 *   (не ретраим, не мержим, не теряем то, что уже введено на экране).
 * Любая другая ошибка — `"other"`, обрабатывается как раньше (unavailable/error). */
export function classifyDraftError(err: unknown): DraftErrorKind {
  if (err instanceof ApplicationApiError && err.status === 409) {
    if (err.body.code === "stage_locked") return "stage_locked";
    if (err.body.code === "revision_conflict") return "revision_conflict";
  }
  return "other";
}

/** Заявка отправлена (не черновик), но текущий этап ещё не открыт — показываем «Заявка на
 * рассмотрении» вместо формы, а не пустой/запертый экран (SPEC.md §4.3, требование 1). */
export function isUnderReview(status: string, stageOpen: boolean): boolean {
  return status !== "draft" && !stageOpen;
}

/** Следующий этап только что открылся одобрением (админ продвинул checkpoint дальше
 * completed_stages) — заявитель мог этого ещё не увидеть: есть хотя бы один завершённый
 * этап, а текущий снова открыт для правки. Используется для баннера в личном кабинете
 * (требование 3) и для решения «показать форму, а не „на рассмотрении“» при входе в мастер
 * по прямой ссылке на заявку. */
export function stageJustOpened(completedStages: string[], stageOpen: boolean): boolean {
  return stageOpen && completedStages.length > 0;
}

export type StageProgressState = "done" | "current" | "upcoming";

export type StageProgressItem = { key: string; title: string; state: StageProgressState };

/** Прогресс ПО ЭТАПАМ для мастера (требование 1: «этап I ✓ завершён, этап II — текущий»),
 * отдельно от прогресса по шагам/экранам внутри этапа (lib/screen-plan.ts). Порядок этапов
 * берётся из Definition, а не из completedStages — так работает даже если бэк когда-нибудь
 * пришлёт их не по порядку. */
export function buildStageProgress(
  stages: { key: string; title: string }[],
  completedStages: string[],
  currentStageKey: string | null,
): StageProgressItem[] {
  return stages.map((stage) => {
    const state: StageProgressState = completedStages.includes(stage.key)
      ? "done"
      : stage.key === currentStageKey
        ? "current"
        : "upcoming";
    return { key: stage.key, title: stage.title, state };
  });
}
