"use client";
// Runtime for filling out an application (SPEC.md §4.3, "Обязательное расширение" §§1-2, 4):
// creates/resumes a checkpointed draft, renders the current 3-6-field screen from the
// renderer contract, autosaves continuously, and walks the applicant through review →
// mock-ЭЦП-free submit → success. See lib/application-api.ts for the HTTP contract and
// lib/draft-autosave.ts for the debounce/409-recovery logic this component wires together.
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ApplicationApiError, applicationApi } from "@/lib/application-api";
import { completenessEmptyMessage, degradedNote, formatSuggestionCount } from "@/lib/copilot";
import { createDebouncedSaver, mergeAfterConflict, type FieldDelta } from "@/lib/draft-autosave";
import { buildStageDemoFillDelta } from "@/lib/demo-fill";
import { distributeGbdUlResponse, isGbdLookupTrigger, isGbdPrefillTarget, looksLikeBin } from "@/lib/gbd-ul-prefill";
import { buildScreenPlan, fieldIndex, findPlanIndexByScreenKey, type PlanScreen } from "@/lib/screen-plan";
import { buildStageProgress, classifyDraftError, isUnderReview } from "@/lib/stage-progress";
import { RESTART_CONFIRM_MESSAGE, buildRestartDelta, firstScreenCheckpoint } from "@/lib/restart-wizard";
import { nextSteps, statusLabel } from "@/lib/status-labels";
import type {
  CabinetApplicationDetail,
  Checkpoint,
  DefinitionField,
  GbdUlOut,
  ScreenContract,
  ScreenValidationItem,
  ServiceDefinitionDoc,
  SubmitOut,
} from "@/lib/application-types";

type Phase =
  | "loading"
  | "unavailable"
  | "service_not_found"
  | "active"
  | "review"
  | "submitting"
  | "success"
  // Многоэтапность (SPEC.md §4.3, требование 1/2): текущий этап отправлен и закрыт для
  // правки — сюда попадаем и при первой загрузке (resume вернул stage_open=false для
  // не-черновика), и посреди сессии (409 stage_locked на PATCH — см. lib/stage-progress.ts).
  | "under_review";
type SaveStatus = "idle" | "saving" | "saved" | "error";
type GbdLookupState = { status: "idle" | "loading" | "success" | "error"; result: GbdUlOut | null; triggerKey: string | null };
// «Проверить полноту (AI)» на review-экране (SPEC.md §7.1, AI-критерий 9.4) — советует,
// НЕ блокирует «Отправить заявку».
type CompletenessState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; suggestions: string[]; degraded: boolean }
  | { status: "error" };

function formatReviewMoment(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" })}, ${date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}`;
}

// `applicationId` (SPEC.md §4.3 "Многоэтапность"): при переходе из личного кабинета по
// баннеру «Этап I одобрен — продолжить этап II» мастер должен резюмировать РОВНО эту
// заявку, а не идемпотентный create-or-find-draft по slug — тот ищет только заявки со
// статусом "draft" (см. app/take/services/[slug]/apply/page.tsx docstring) и не найдёт
// заявку, чей статус уже продвинулся дальше черновика.
export function ApplicationWizard({ slug, applicationId }: { slug: string; applicationId?: string }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [definition, setDefinition] = useState<ServiceDefinitionDoc | null>(null);
  const [plan, setPlan] = useState<PlanScreen[]>([]);
  const [currentPlanIndex, setCurrentPlanIndex] = useState(0);
  const [screen, setScreen] = useState<ScreenContract | null>(null);
  const [data, setData] = useState<Record<string, unknown>>({});
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitErrors, setSubmitErrors] = useState<ScreenValidationItem[] | null>(null);
  const [submitResult, setSubmitResult] = useState<SubmitOut | null>(null);
  const [completeness, setCompleteness] = useState<CompletenessState>({ status: "idle" });

  // Многоэтапность (см. `Phase` docstring выше).
  const [status, setStatus] = useState<string>("draft");
  const [completedStages, setCompletedStages] = useState<string[]>([]);
  const [reviewDetail, setReviewDetail] = useState<CabinetApplicationDetail | null>(null);

  // Предзаполнение по БИН (SPEC.md §3.2/§8, "Обязательное расширение" §1).
  const [gbdLookup, setGbdLookup] = useState<GbdLookupState>({ status: "idle", result: null, triggerKey: null });
  // Целевые поля, заполненные из ГБД ЮЛ и пока не тронутые вручную — рендерятся свёрнутой
  // сводкой вместо самих себя (требование 4), пока не нажали «Изменить».
  const [profileSourcedKeys, setProfileSourcedKeys] = useState<Set<string>>(new Set());

  const applicationIdRef = useRef<string | null>(null);
  const revisionRef = useRef(1);
  const planRef = useRef<PlanScreen[]>([]);
  // Последнее значение, для которого уже пытались (успешно или нет) сделать lookup —
  // не долбим ГБД ЮЛ на каждый keystroke/повторный blur одного и того же БИН.
  const gbdLookupSeenRef = useRef<string | null>(null);

  const fieldIndexMap = useMemo<Map<string, DefinitionField>>(
    () => (definition ? fieldIndex(definition) : new Map()),
    [definition],
  );

  // Coalesces field edits into one PATCH every 800ms; `take()` also lets the "Далее"/
  // "Назад" handlers grab whatever is still queued and send it together with the
  // navigation checkpoint, so a screen change is never a data loss point (SPEC.md §2/§4).
  const saverRef = useRef(createDebouncedSaver((delta) => void handleAutosave(delta)));

  async function handleAutosave(delta: FieldDelta) {
    const id = applicationIdRef.current;
    if (!id || Object.keys(delta).length === 0) return;
    setSaveStatus("saving");
    try {
      const result = await applicationApi.patchDraft(id, {
        data_delta: delta,
        checkpoint: null,
        expected_revision: revisionRef.current,
      });
      applyPatchResult(result.revision, result.checkpoint, result.screen);
    } catch (err) {
      await recoverFromSaveError(err, delta, null);
    }
  }

  function applyPatchResult(revision: number, checkpoint: Checkpoint, nextScreen: ScreenContract) {
    revisionRef.current = revision;
    setScreen(nextScreen);
    setCurrentPlanIndex(findPlanIndexByScreenKey(planRef.current, checkpoint.screen_key));
    setSaveStatus("saved");
    setSavedAt(new Date());
  }

  // Отдельная заявка на рассмотрении (SPEC.md §4.3, требование 2): 409 `stage_locked`
  // означает «сюда сейчас нельзя», а не гонку редактирования — resume() освежает
  // status/completedStages для честного экрана, а таймлайн подтягивает loadReviewDetail().
  // Ничего из `data` не трогаем и не теряем: правка просто больше не уходит на сервер.
  async function enterUnderReview(id: string) {
    saverRef.current.cancel();
    try {
      const fresh = await applicationApi.resume(id);
      setStatus(fresh.status);
      setCompletedStages(fresh.completed_stages);
    } catch {
      // Бэк недоступен прямо сейчас — всё равно показываем «на рассмотрении» на основе
      // того, что уже знаем (эта заявка точно не в статусе "draft", раз стадия закрыта).
    }
    setPhase("under_review");
    setSaveStatus("idle");
    void loadReviewDetail(id);
  }

  async function loadReviewDetail(id: string) {
    try {
      const detail = await applicationApi.getApplication(id);
      setReviewDetail(detail);
    } catch {
      setReviewDetail(null);
    }
  }

  // 409 revision_conflict: a stale `expected_revision` never overwrites a newer save
  // server-side, so instead of losing the applicant's edits we re-fetch the authoritative
  // state and replay exactly the edits from the failed attempt on top of it, then retry
  // once with the fresh revision (SPEC.md §2: "сервер… возвращает актуальную ревизию").
  //
  // 409 stage_locked is a *different* failure (SPEC.md §4.3, требование 2): the current
  // stage was already submitted while we were editing (e.g. a second tab). Retrying the
  // same merge-and-resend recipe would just 409 again — instead we stop trying to save
  // this stage and show the "на рассмотрении" screen (`enterUnderReview`), which is also
  // how the retry below reacts if the race lands exactly on the resend.
  async function recoverFromSaveError(err: unknown, delta: FieldDelta, navigationCheckpoint: Checkpoint | null) {
    const id = applicationIdRef.current;
    const kind = classifyDraftError(err);
    if (id && kind === "stage_locked") {
      await enterUnderReview(id);
      return;
    }
    if (id && kind === "revision_conflict") {
      try {
        const fresh = await applicationApi.resume(id);
        setData(() => mergeAfterConflict(fresh.data, delta));
        revisionRef.current = fresh.revision;
        setScreen(fresh.screen);
        setCompletedStages(fresh.completed_stages);
        setStatus(fresh.status);
        setCurrentPlanIndex(findPlanIndexByScreenKey(planRef.current, fresh.checkpoint.screen_key));
        setSaveStatus("saving");
        const retry = await applicationApi.patchDraft(id, {
          data_delta: delta,
          checkpoint: navigationCheckpoint,
          expected_revision: fresh.revision,
        });
        applyPatchResult(retry.revision, retry.checkpoint, retry.screen);
        return;
      } catch (retryErr) {
        if (classifyDraftError(retryErr) === "stage_locked") {
          await enterUnderReview(id);
          return;
        }
        setSaveStatus("error");
        return;
      }
    }
    setSaveStatus("error");
  }

  // Initial load: idempotent create-or-resume, then resume() for the full Definition +
  // current screen. No silent mock fallback here — an unreachable backend must show an
  // honest "стенд недоступен" screen (SPEC item 7), never a faked submission flow.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // См. `applicationId` docstring на компоненте: обходим create-or-find-draft, если
        // кабинет уже прислал точный id заявки (переход по баннеру «этап II открылся»).
        const resumed = applicationId
          ? await applicationApi.resume(applicationId)
          : await (async () => {
              const service = await applicationApi.getService(slug);
              const created = await applicationApi.createApplication(service.id);
              return applicationApi.resume(created.id);
            })();
        if (cancelled) return;
        const builtPlan = buildScreenPlan(resumed.definition);
        applicationIdRef.current = resumed.id;
        revisionRef.current = resumed.revision;
        planRef.current = builtPlan;
        setDefinition(resumed.definition);
        setPlan(builtPlan);
        setData(resumed.data);
        setScreen(resumed.screen);
        setStatus(resumed.status);
        setCompletedStages(resumed.completed_stages);
        setCurrentPlanIndex(findPlanIndexByScreenKey(builtPlan, resumed.checkpoint.screen_key));
        if (isUnderReview(resumed.status, resumed.stage_open)) {
          setPhase("under_review");
          void loadReviewDetail(resumed.id);
        } else {
          setPhase("active");
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApplicationApiError && err.status === 404) {
          setPhase("service_not_found");
          return;
        }
        setPhase("unavailable");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [slug, applicationId]);

  // Flush pending edits when the tab loses focus/visibility and on unmount — "гарантированное
  // сохранение… при потере фокуса вкладки" (SPEC.md §2).
  useEffect(() => {
    const saver = saverRef.current;
    function handleVisibility() {
      if (document.visibilityState === "hidden") saver.flushNow();
    }
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
      saver.flushNow();
    };
  }, []);

  function updateField(key: string, value: unknown) {
    setData((prev) => ({ ...prev, [key]: value }));
    setFieldErrors((prev) => {
      if (!(key in prev)) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
    saverRef.current.schedule({ [key]: value });
    setSaveStatus("saving");
    maybeRunGbdLookup(key, value);
  }

  // Демо-заполнение («Далее-Далее» для питча — не часть SPEC.md): проставляет валидные
  // значения во ВСЕ поля ТЕКУЩЕГО ЭТАПА (все шаги/экраны этапа, не только текущий видимый
  // экран, и независимо от текущей видимости — см. buildStageDemoFillDelta docstring) через
  // тот же updateField()/autosave, что и ручной ввод — ничего не идёт в обход PATCH-контракта,
  // поэтому prefill/валидация/многоэтапность продолжают работать как обычно (см.
  // lib/demo-fill.ts для чистой логики генерации значений). После клика жюри достаточно
  // жать «Далее» до конца этапа — каждый экран, включая любую ветку, уже заполнен.
  function handleDemoFill() {
    if (!screen || !definition) return;
    const delta = buildStageDemoFillDelta(definition, screen.stage, data);
    for (const [key, value] of Object.entries(delta)) updateField(key, value);
  }

  // «Начать заново» (SPEC.md §6, п.7): после подтверждения очищаем черновик и возвращаемся
  // на первый экран. Бэкенд не умеет restart, поэтому одним PATCH обнуляем все заполненные
  // поля и переставляем checkpoint в начало — тем же autosave-контрактом, что и обычная
  // правка (см. lib/restart-wizard.ts). 409-восстановление переиспользуем как есть.
  async function handleRestart() {
    const id = applicationIdRef.current;
    if (!id) return;
    if (!window.confirm(RESTART_CONFIRM_MESSAGE)) return;
    saverRef.current.cancel();
    const delta = buildRestartDelta(data);
    const target = firstScreenCheckpoint(planRef.current);
    // Локальный сброс сразу — форма визуально чистая, даже пока PATCH в полёте.
    setData({});
    setFieldErrors({});
    setSubmitErrors(null);
    setProfileSourcedKeys(new Set());
    setGbdLookup({ status: "idle", result: null, triggerKey: null });
    gbdLookupSeenRef.current = null;
    setCurrentPlanIndex(0);
    setPhase("active");
    if (Object.keys(delta).length === 0 && !target) return;
    setSaveStatus("saving");
    try {
      const result = await applicationApi.patchDraft(id, {
        data_delta: delta,
        checkpoint: target,
        expected_revision: revisionRef.current,
      });
      applyPatchResult(result.revision, result.checkpoint, result.screen);
      setData({});
    } catch (err) {
      await recoverFromSaveError(err, delta, target);
    }
  }

  // Предзаполнение по БИН (SPEC.md §3.2/§8, требования 4/7): срабатывает только на поле-
  // триггер (`prefill: "gbd_ul.lookup"`) и только когда значение уже похоже на полный БИН —
  // не блокирует остальные поля и не дёргает справочник на каждую промежуточную цифру.
  function maybeRunGbdLookup(key: string, value: unknown) {
    const def = fieldIndexMap.get(key);
    if (!def || !isGbdLookupTrigger(def.prefill) || !looksLikeBin(value)) return;
    const binValue = String(value).trim();
    if (gbdLookupSeenRef.current === binValue) return;
    gbdLookupSeenRef.current = binValue;
    void runGbdLookup(key, binValue);
  }

  async function runGbdLookup(triggerKey: string, binValue: string) {
    setGbdLookup({ status: "loading", result: null, triggerKey });
    try {
      const result = await applicationApi.lookupGbdUl(binValue);
      setGbdLookup({ status: "success", result, triggerKey });
      const targets = distributeGbdUlResponse([...fieldIndexMap.values()], result);
      const keys = Object.keys(targets);
      if (keys.length > 0) {
        for (const key of keys) updateField(key, targets[key]);
        setProfileSourcedKeys((prev) => new Set([...prev, ...keys]));
      }
    } catch {
      // Требование 7: справочник недоступен/БИН не найден — не блокируем ручное заполнение,
      // только показываем мягкую подсказку рядом с полем-триггером (см. renderGbdStatusHint).
      setGbdLookup({ status: "error", result: null, triggerKey });
    }
  }

  // Требование 4: «Изменить» разворачивает свёрнутую сводку обратно в редактируемые поля.
  function expandGbdFields() {
    setProfileSourcedKeys(new Set());
  }

  function isEmpty(value: unknown): boolean {
    return value === undefined || value === null || value === "" || (Array.isArray(value) && value.length === 0);
  }

  function handleFieldBlur(key: string) {
    const def = fieldIndexMap.get(key);
    const field = screen?.fields.find((f) => f.key === key);
    if (!def || !field || !field.visible) return;
    maybeRunGbdLookup(key, data[key]);
    const value = data[key];
    let message: string | null = null;
    if (field.required && isEmpty(value)) {
      message = `«${def.label}» — обязательное поле`;
    } else if (def.type === "number" && !isEmpty(value)) {
      const numeric = Number(value);
      if (def.minimum != null && numeric < def.minimum) message = `Значение должно быть не меньше ${def.minimum}`;
      else if (def.maximum != null && numeric > def.maximum) message = `Значение должно быть не больше ${def.maximum}`;
    }
    setFieldErrors((prev) => {
      const next = { ...prev };
      if (message) next[key] = message;
      else delete next[key];
      return next;
    });
  }

  function requiredEmptyKeysOnCurrentScreen(): string[] {
    if (!screen) return [];
    return screen.fields
      .filter((f) => f.visible && f.required && !(f.key in screen.computed))
      .filter((f) => isEmpty(data[f.key]))
      .map((f) => f.key);
  }

  function markFieldErrors(keys: string[]) {
    setFieldErrors((prev) => {
      const next = { ...prev };
      for (const key of keys) {
        const label = fieldIndexMap.get(key)?.label ?? key;
        next[key] = `«${label}» — обязательное поле`;
      }
      return next;
    });
  }

  async function goToScreen(targetIndex: number) {
    const target = planRef.current[targetIndex];
    const id = applicationIdRef.current;
    if (!target || !id) return;
    if (targetIndex > currentPlanIndex) {
      const blockers = requiredEmptyKeysOnCurrentScreen();
      if (blockers.length > 0) {
        markFieldErrors(blockers);
        return;
      }
    }
    setPhase("active");
    const delta = saverRef.current.take();
    const nextCheckpoint: Checkpoint = {
      stage_key: target.stageKey,
      step_key: target.stepKey,
      screen_key: target.screenKey,
    };
    setSaveStatus("saving");
    try {
      const result = await applicationApi.patchDraft(id, {
        data_delta: delta,
        checkpoint: nextCheckpoint,
        expected_revision: revisionRef.current,
      });
      applyPatchResult(result.revision, result.checkpoint, result.screen);
    } catch (err) {
      await recoverFromSaveError(err, delta, nextCheckpoint);
    }
  }

  async function goToReview() {
    const blockers = requiredEmptyKeysOnCurrentScreen();
    if (blockers.length > 0) {
      markFieldErrors(blockers);
      return;
    }
    const id = applicationIdRef.current;
    const delta = saverRef.current.take();
    if (id) {
      setSaveStatus("saving");
      try {
        const result = await applicationApi.patchDraft(id, {
          data_delta: delta,
          checkpoint: null,
          expected_revision: revisionRef.current,
        });
        applyPatchResult(result.revision, result.checkpoint, result.screen);
      } catch (err) {
        await recoverFromSaveError(err, delta, null);
      }
    }
    setCompleteness({ status: "idle" });
    setPhase("review");
  }

  // «Проверить полноту (AI)» (SPEC.md §7.1): советует, не блокирует — ошибка здесь
  // просто оставляет кнопку доступной для повтора, «Отправить заявку» работает как раньше.
  async function handleCheckCompleteness() {
    const id = applicationIdRef.current;
    if (!id) return;
    setCompleteness({ status: "loading" });
    try {
      const result = await applicationApi.checkCompleteness(id);
      setCompleteness({ status: "success", suggestions: result.suggestions, degraded: result.degraded });
    } catch {
      setCompleteness({ status: "error" });
    }
  }

  async function jumpToField(key: string | null | undefined) {
    const target = key ? plan.findIndex((p) => p.fieldKeys.includes(key)) : -1;
    await goToScreen(target >= 0 ? target : 0);
  }

  async function handleSubmit() {
    const id = applicationIdRef.current;
    if (!id) return;
    setPhase("submitting");
    setSubmitErrors(null);
    try {
      const result = await applicationApi.submit(id);
      setSubmitResult(result);
      setPhase("success");
    } catch (err) {
      if (err instanceof ApplicationApiError) {
        const errors = (err.body.details.errors as ScreenValidationItem[] | undefined) ?? [
          { field: null, code: err.body.code, message: err.message },
        ];
        setSubmitErrors(errors);
        setPhase("review");
        return;
      }
      setPhase("unavailable");
    }
  }

  function humanValidationMessage(item: ScreenValidationItem): string {
    const label = item.field ? fieldIndexMap.get(item.field)?.label ?? item.field : null;
    if (item.code === "required") return label ? `«${label}» — обязательное поле` : "Заполните обязательное поле";
    if (item.code === "minimum") return label ? `«${label}» — значение слишком маленькое` : "Проверьте значение поля";
    if (item.code === "maximum") return label ? `«${label}» — значение слишком большое` : "Проверьте значение поля";
    if (item.message) return item.message;
    return label ? `Проверьте поле «${label}»` : "Проверьте данные заявки";
  }

  const reviewGroups = useMemo(() => {
    if (!definition || !screen) return [];
    const groups: { key: string; title: string; fields: { key: string; label: string }[] }[] = [];
    for (const stage of definition.stages) {
      for (const step of stage.steps) {
        const fields = step.fields
          .filter((f) => !isEmpty(data[f.key]) || f.required || f.key in screen.computed)
          .map((f) => ({ key: f.key, label: f.label }));
        if (fields.length > 0) groups.push({ key: `${stage.key}:${step.key}`, title: step.title, fields });
      }
    }
    return groups;
  }, [definition, screen, data]);

  function formatValueForReview(key: string): string {
    if (screen && key in screen.computed) {
      const value = screen.computed[key];
      return isEmpty(value) ? "рассчитывается после заполнения нужных полей" : String(value);
    }
    const value = data[key];
    if (isEmpty(value)) return "— не заполнено —";
    if (Array.isArray(value)) return value.join(", ");
    if (typeof value === "boolean") return value ? "Да" : "Нет";
    return String(value);
  }

  function renderField(field: ScreenContract["fields"][number]) {
    if (!field.visible) return null;
    const def = fieldIndexMap.get(field.key);
    const label = def?.label ?? field.label;
    const isComputed = screen ? field.key in screen.computed : false;

    if (isComputed) {
      const value = screen?.computed[field.key];
      const trace = screen?.explanations.computed[field.key];
      return (
        <div className="field" key={field.key}>
          <label>{label}</label>
          <div className="computed-field">
            <strong>{isEmpty(value) ? "рассчитывается после заполнения нужных полей" : String(value)}</strong>
            {trace && trace.length > 0 && <small className="muted">Как посчитано: {trace.join(" → ")}</small>}
          </div>
        </div>
      );
    }

    const error = fieldErrors[field.key];
    const common = { id: field.key, disabled: !field.enabled, onBlur: () => handleFieldBlur(field.key) };
    let control: React.ReactNode;

    if (def?.type === "select") {
      control = (
        <select {...common} value={String(data[field.key] ?? "")} onChange={(e) => updateField(field.key, e.target.value)}>
          <option value="">Выберите</option>
          {(def.options ?? []).map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      );
    } else if (def?.type === "boolean") {
      control = (
        <input
          type="checkbox"
          {...common}
          checked={Boolean(data[field.key])}
          onChange={(e) => updateField(field.key, e.target.checked)}
        />
      );
    } else if (def?.type === "number") {
      control = (
        <input
          type="number"
          {...common}
          value={isEmpty(data[field.key]) ? "" : String(data[field.key])}
          min={def.minimum ?? undefined}
          max={def.maximum ?? undefined}
          onChange={(e) => updateField(field.key, e.target.value === "" ? "" : Number(e.target.value))}
        />
      );
    } else if (def?.type === "repeater") {
      // The backend's `RepeaterField` schema (app/schemas/definition.py) does not yet
      // define an item sub-shape, so each row is a single free-text value — the smallest
      // faithful implementation of "add rows one by one, copy the previous row as a
      // template" (SPEC.md §4) that this contract supports today.
      const rows = Array.isArray(data[field.key]) ? (data[field.key] as string[]) : [];
      control = (
        <div>
          {rows.map((row, i) => (
            <div className="repeater-row" key={i}>
              <input
                disabled={!field.enabled}
                value={row}
                onChange={(e) => {
                  const next = [...rows];
                  next[i] = e.target.value;
                  updateField(field.key, next);
                }}
                onBlur={() => handleFieldBlur(field.key)}
              />
              <button type="button" className="button secondary" onClick={() => updateField(field.key, rows.filter((_, idx) => idx !== i))}>
                Удалить
              </button>
            </div>
          ))}
          <button type="button" className="button secondary" disabled={!field.enabled} onClick={() => updateField(field.key, [...rows, rows[rows.length - 1] ?? ""])}>
            + Добавить строку
          </button>
        </div>
      );
    } else {
      control = <input {...common} value={String(data[field.key] ?? "")} onChange={(e) => updateField(field.key, e.target.value)} />;
    }

    return (
      <div className="field" key={field.key}>
        <label htmlFor={field.key}>
          {label}
          {field.required && " *"}
          {/* Требование 6: подсказка раскрывается рядом с полем по «?», не отдельной страницей. */}
          {def?.hint && (
            <details className="field-hint">
              <summary aria-label={`Подсказка к полю «${label}»`}>?</summary>
              <p>{def.hint}</p>
            </details>
          )}
        </label>
        {control}
        {isGbdLookupTrigger(def?.prefill) && renderGbdStatusHint()}
        {error && <small role="alert">{error}</small>}
      </div>
    );
  }

  // Требования 4/5/7: пока поле-триггер грузит ответ ГБД ЮЛ — тихий индикатор рядом с
  // полем; если lookup не удался (справочник недоступен или БИН не найден) — мягкая
  // подсказка, что можно заполнить дальше вручную (никакой блокировки формы).
  function renderGbdStatusHint() {
    if (gbdLookup.status === "loading") return <small className="muted">Ищем данные компании в ГБД ЮЛ…</small>;
    if (gbdLookup.status === "error")
      return <small className="muted">Не удалось подтянуть данные автоматически — заполните поля ниже вручную.</small>;
    return null;
  }

  // Требование 4 ("Обязательное расширение" §1): вместо «голых» целевых полей ГБД ЮЛ —
  // одна свёрнутая сводка на всю группу, с кнопкой «Изменить» для возврата к правке.
  // Требование 5: бейдж-дисклеймер mock-источника — тем же классом `.mock`, что и у
  // остальных имитаций (см. SPEC.md §8 / renderField submitErrors block above).
  function renderGbdSummary(key: string) {
    const result = gbdLookup.result;
    if (!result) return null;
    return (
      <div className="field" key={`gbd-summary-${key}`}>
        <label>Данные компании</label>
        <div className="computed-field">
          <strong>
            {result.name}, БИН {result.bin}, {result.address}
          </strong>
          {result.mock && (
            <div className="mock" role="note">
              {result.disclaimer}
            </div>
          )}
          <div className="actions">
            <button type="button" className="button secondary" onClick={expandGbdFields}>
              Изменить
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Требование 4: рендерит экран, сворачивая целевые поля ГБД ЮЛ (`profileSourcedKeys`) в
  // одну сводку вместо того, чтобы показывать каждое из них как обычное поле формы.
  function renderScreenFields(fields: ScreenContract["fields"]) {
    const nodes: React.ReactNode[] = [];
    let summaryShown = false;
    for (const field of fields) {
      const def = fieldIndexMap.get(field.key);
      if (field.visible && isGbdPrefillTarget(def?.prefill) && profileSourcedKeys.has(field.key)) {
        if (!summaryShown) {
          nodes.push(renderGbdSummary(field.key));
          summaryShown = true;
        }
        continue;
      }
      nodes.push(renderField(field));
    }
    return nodes;
  }

  function renderSaveIndicator() {
    if (saveStatus === "saving") return <p className="save-indicator" data-status="saving">Сохраняем…</p>;
    if (saveStatus === "error")
      return (
        <p className="save-indicator" data-status="error">
          Не удалось сохранить черновик — проверьте связь. Введённое остаётся в форме и досохранится автоматически.
        </p>
      );
    if (saveStatus === "saved" && savedAt)
      return (
        <p className="save-indicator" data-status="saved">
          Черновик сохранён · {savedAt.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}
        </p>
      );
    return null;
  }

  function renderLevels() {
    const levels: { key: string; title: string; first: number; last: number }[] = [];
    plan.forEach((p, i) => {
      const key = `${p.stageKey}:${p.stepKey}`;
      const last = levels[levels.length - 1];
      if (last && last.key === key) {
        last.last = i;
        return;
      }
      levels.push({ key, title: p.stepTitle, first: i, last: i });
    });
    return (
      <ol className="levels" aria-label="Ход заполнения заявки">
        {levels.map((level) => {
          const done = phase === "review" || phase === "success" || currentPlanIndex > level.last;
          const current = phase === "active" && currentPlanIndex >= level.first && currentPlanIndex <= level.last;
          const state = done ? "done" : current ? "current" : "upcoming";
          return (
            <li key={level.key} data-state={state}>
              <button type="button" disabled={state === "upcoming"} onClick={() => goToScreen(level.first)}>
                <span aria-hidden>{state === "done" ? "✓" : state === "current" ? "●" : "○"}</span> {level.title}
              </button>
            </li>
          );
        })}
        <li data-state={phase === "review" ? "current" : phase === "success" ? "done" : "upcoming"}>
          <span>
            <span aria-hidden>{phase === "success" ? "✓" : phase === "review" ? "●" : "○"}</span> Проверка и отправка
          </span>
        </li>
      </ol>
    );
  }

  // Требование 1: прогресс ПО ЭТАПАМ (этап I ✓ завершён, этап II — текущий), отдельно от
  // renderLevels() (шаги/экраны внутри текущего этапа). Однoэтапные услуги — как раньше:
  // при одном этапе список из одного пункта не добавляет пользы, скрываем его.
  function renderStageProgress() {
    if (!definition || definition.stages.length <= 1) return null;
    const currentStageKey = plan[currentPlanIndex]?.stageKey ?? null;
    const items = buildStageProgress(
      definition.stages.map((s) => ({ key: s.key, title: s.title })),
      completedStages,
      currentStageKey,
    );
    return (
      <>
        <h3>Этапы заявки</h3>
        <ol className="levels" aria-label="Этапы заявки">
          {items.map((item) => (
            <li key={item.key} data-state={item.state}>
              <span>
                <span aria-hidden>{item.state === "done" ? "✓" : item.state === "current" ? "●" : "○"}</span> {item.title}
              </span>
            </li>
          ))}
        </ol>
      </>
    );
  }

  if (phase === "loading") {
    return (
      <div className="form-card">
        <p className="muted">Загружаем анкету…</p>
      </div>
    );
  }

  if (phase === "unavailable") {
    return (
      <div className="form-card">
        <span className="pill">Технический сбой</span>
        <h2>Стенд временно недоступен</h2>
        <p className="muted">
          Не удалось связаться с сервером заявок. Это не имитация — подать заявку сейчас нельзя. Попробуйте обновить
          страницу через минуту; если введённые данные уже сохранялись раньше, они не потеряются.
        </p>
        <button type="button" className="button" onClick={() => window.location.reload()}>
          Обновить страницу
        </button>
      </div>
    );
  }

  if (phase === "service_not_found") {
    return (
      <div className="form-card">
        <h2>{applicationId ? "Заявка не найдена" : "Услуга не найдена"}</h2>
        <p className="muted">
          {applicationId
            ? "Возможно, ссылка устарела или заявка принадлежит другому пользователю."
            : "Возможно, ссылка устарела или услуга была снята с публикации."}
        </p>
        <Link className="button secondary" href={applicationId ? "/take/cabinet" : "/take"}>
          {applicationId ? "К списку заявок" : "К каталогу услуг"}
        </Link>
      </div>
    );
  }

  if (phase === "under_review") {
    return (
      <div className="form-shell">
        <div>
          <span className="pill">{statusLabel(status, reviewDetail?.labels_plain)}</span>
          <h1>{definition?.meta.title ?? reviewDetail?.service.title}</h1>
          {reviewDetail?.number && <p className="muted">Заявка № {reviewDetail.number}</p>}
          <p className="lead">
            Этот этап заявки уже отправлен и рассматривается организацией — форма недоступна для правки, пока не будет
            решения. Ничего из введённого раньше не потеряно.
          </p>
          <div className="form-card">
            <h2>История заявки</h2>
            {reviewDetail ? (
              <ol className="steps">
                <li>
                  <strong>Черновик создан</strong>
                  <span className="muted"> — {formatReviewMoment(reviewDetail.created_at)}</span>
                </li>
                {reviewDetail.timeline.map((entry, i) => (
                  <li key={`${entry.status}-${i}`}>
                    <strong>{statusLabel(entry.status, reviewDetail.labels_plain)}</strong>
                    <span className="muted"> — {formatReviewMoment(entry.at)}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="muted">История временно недоступна — попробуйте обновить страницу через минуту.</p>
            )}
          </div>
          <div className="form-card">
            <h2>Что дальше</h2>
            <ol className="steps">
              {nextSteps(status).map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          </div>
          <div className="actions">
            <Link className="button" href="/take/cabinet">
              В личный кабинет
            </Link>
          </div>
        </div>
        {definition && definition.stages.length > 1 && <aside className="card wizard-progress">{renderStageProgress()}</aside>}
      </div>
    );
  }

  if (phase === "success" && submitResult) {
    return (
      <div className="form-card">
        <span className="pill">Заявка отправлена</span>
        <h2>Номер заявки {submitResult.number}</h2>
        <p className="lead">Заявка принята и зарегистрирована. Каждое изменение статуса будет видно по этому номеру.</p>
        <h3>Что дальше</h3>
        <ol className="steps">
          <li>Организация рассматривает заявку в срок, указанный на карточке услуги.</li>
          <li>При необходимости запросит дополнительные документы.</li>
          <li>Каждое изменение статуса видно в личном кабинете.</li>
          {definition && definition.stages.length > 1 && (
            <li>
              Если по услуге несколько этапов, следующий этап откроется в этой же заявке — сразу после того, как
              организация одобрит текущий.
            </li>
          )}
        </ol>
        <div className="actions">
          <Link className="button" href="/take/cabinet">
            В личный кабинет
          </Link>
          <Link className="button secondary" href="/take">
            К каталогу услуг
          </Link>
        </div>
      </div>
    );
  }

  const currentPlan = plan[currentPlanIndex];
  const isLastScreen = currentPlanIndex === plan.length - 1;

  return (
    <div className="form-shell">
      <div>
        <h1>{definition?.meta.title}</h1>
        {renderSaveIndicator()}

        {phase === "active" && screen && currentPlan && (
          <div className="form-card">
            <h2>{currentPlan.stepTitle}</h2>
            <p className="muted">
              Шаг {currentPlan.stepIndex + 1} · этап «{currentPlan.stageTitle}»
            </p>
            <div className="actions">
              <button type="button" className="button secondary" onClick={handleDemoFill}>
                <span className="pill" aria-hidden>Демо</span> Заполнить демо-данными
              </button>
            </div>
            {renderScreenFields(screen.fields)}
            <div className="actions">
              {currentPlanIndex > 0 && (
                <button type="button" className="button secondary" onClick={() => goToScreen(currentPlanIndex - 1)}>
                  ← Назад
                </button>
              )}
              {isLastScreen ? (
                <button type="button" className="button" onClick={goToReview}>
                  Проверить и отправить
                </button>
              ) : (
                <button type="button" className="button" onClick={() => goToScreen(currentPlanIndex + 1)}>
                  Далее →
                </button>
              )}
            </div>
            {/* «Начать заново» (SPEC.md §6, п.7) — неброско, отдельно от навигации и «Отправить»,
                только для обычного черновика (не для уже открытого следующего этапа). */}
            {status === "draft" && (
              <p className="restart-hint muted">
                <button type="button" className="link-button" onClick={handleRestart}>
                  Начать заново
                </button>
              </p>
            )}
          </div>
        )}

        {(phase === "review" || phase === "submitting") && (
          <div className="form-card">
            <h2>Проверьте заявку перед отправкой</h2>
            <p className="muted">Можно вернуться к любому шагу — ничего из введённого не потеряется.</p>
            {submitErrors && submitErrors.length > 0 && (
              <div className="mock" role="alert">
                <strong>Перед отправкой поправьте:</strong>
                <ul>
                  {submitErrors.map((item, i) => (
                    <li key={i}>
                      <button type="button" className="button secondary" onClick={() => jumpToField(item.field)}>
                        {humanValidationMessage(item)}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {reviewGroups.map((group) => (
              <div className="review-block" key={group.key}>
                <h3>{group.title}</h3>
                <div className="table-scroll">
                  <table className="table">
                    <tbody>
                      {group.fields.map((f) => (
                        <tr key={f.key}>
                          <th>{f.label}</th>
                          <td>{formatValueForReview(f.key)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
            <div className="form-card">
              <span className="pill">AI</span>
              <h3>Проверка полноты заявки</h3>
              <p className="muted">Необязательная подсказка перед отправкой — ничего не блокирует.</p>
              {completeness.status !== "success" && (
                <button
                  type="button"
                  className="button secondary"
                  onClick={handleCheckCompleteness}
                  disabled={completeness.status === "loading"}
                >
                  {completeness.status === "loading" ? "Проверяем…" : "Проверить полноту (AI)"}
                </button>
              )}
              {completeness.status === "error" && (
                <p className="muted">Не удалось проверить полноту — попробуйте ещё раз позже.</p>
              )}
              {completeness.status === "success" && (
                <>
                  {completeness.suggestions.length > 0 ? (
                    <>
                      <p className="muted">{formatSuggestionCount(completeness.suggestions.length)}:</p>
                      <ul className="steps">
                        {completeness.suggestions.map((s, i) => (
                          <li key={i}>{s}</li>
                        ))}
                      </ul>
                    </>
                  ) : (
                    <p className="muted">{completenessEmptyMessage()}</p>
                  )}
                  {completeness.degraded && (
                    <p className="muted">
                      <small>{degradedNote("completeness")}</small>
                    </p>
                  )}
                  <button type="button" className="button secondary" onClick={handleCheckCompleteness}>
                    Проверить ещё раз
                  </button>
                </>
              )}
            </div>
            <div className="actions">
              <button type="button" className="button secondary" onClick={() => goToScreen(plan.length - 1)}>
                Назад к заполнению
              </button>
              <button type="button" className="button" onClick={handleSubmit} disabled={phase === "submitting"}>
                {phase === "submitting" ? "Отправляем…" : "Отправить заявку"}
              </button>
            </div>
          </div>
        )}
      </div>
      <aside className="card wizard-progress">
        {renderStageProgress()}
        {renderLevels()}
      </aside>
    </div>
  );
}
