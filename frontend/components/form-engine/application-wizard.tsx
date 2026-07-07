"use client";
// Runtime for filling out an application (SPEC.md §4.3, "Обязательное расширение" §§1-2, 4):
// creates/resumes a checkpointed draft, renders the current 3-6-field screen from the
// renderer contract, autosaves continuously, and walks the applicant through review →
// mock-ЭЦП-free submit → success. See lib/application-api.ts for the HTTP contract and
// lib/draft-autosave.ts for the debounce/409-recovery logic this component wires together.
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ApplicationApiError, applicationApi } from "@/lib/application-api";
import { createDebouncedSaver, mergeAfterConflict, type FieldDelta } from "@/lib/draft-autosave";
import { buildScreenPlan, fieldIndex, findPlanIndexByScreenKey, type PlanScreen } from "@/lib/screen-plan";
import type {
  Checkpoint,
  DefinitionField,
  ScreenContract,
  ScreenValidationItem,
  ServiceDefinitionDoc,
  SubmitOut,
} from "@/lib/application-types";

type Phase = "loading" | "unavailable" | "service_not_found" | "active" | "review" | "submitting" | "success";
type SaveStatus = "idle" | "saving" | "saved" | "error";

export function ApplicationWizard({ slug }: { slug: string }) {
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

  const applicationIdRef = useRef<string | null>(null);
  const revisionRef = useRef(1);
  const planRef = useRef<PlanScreen[]>([]);

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

  // 409 revision_conflict: a stale `expected_revision` never overwrites a newer save
  // server-side, so instead of losing the applicant's edits we re-fetch the authoritative
  // state and replay exactly the edits from the failed attempt on top of it, then retry
  // once with the fresh revision (SPEC.md §2: "сервер… возвращает актуальную ревизию").
  async function recoverFromSaveError(err: unknown, delta: FieldDelta, navigationCheckpoint: Checkpoint | null) {
    const id = applicationIdRef.current;
    if (id && err instanceof ApplicationApiError && err.status === 409) {
      try {
        const fresh = await applicationApi.resume(id);
        setData(() => mergeAfterConflict(fresh.data, delta));
        revisionRef.current = fresh.revision;
        setScreen(fresh.screen);
        setCurrentPlanIndex(findPlanIndexByScreenKey(planRef.current, fresh.checkpoint.screen_key));
        setSaveStatus("saving");
        const retry = await applicationApi.patchDraft(id, {
          data_delta: delta,
          checkpoint: navigationCheckpoint,
          expected_revision: fresh.revision,
        });
        applyPatchResult(retry.revision, retry.checkpoint, retry.screen);
        return;
      } catch {
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
        const service = await applicationApi.getService(slug);
        const created = await applicationApi.createApplication(service.id);
        const resumed = await applicationApi.resume(created.id);
        if (cancelled) return;
        const builtPlan = buildScreenPlan(resumed.definition);
        applicationIdRef.current = resumed.id;
        revisionRef.current = resumed.revision;
        planRef.current = builtPlan;
        setDefinition(resumed.definition);
        setPlan(builtPlan);
        setData(resumed.data);
        setScreen(resumed.screen);
        setCurrentPlanIndex(findPlanIndexByScreenKey(builtPlan, resumed.checkpoint.screen_key));
        setPhase("active");
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
  }, [slug]);

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
  }

  function isEmpty(value: unknown): boolean {
    return value === undefined || value === null || value === "" || (Array.isArray(value) && value.length === 0);
  }

  function handleFieldBlur(key: string) {
    const def = fieldIndexMap.get(key);
    const field = screen?.fields.find((f) => f.key === key);
    if (!def || !field || !field.visible) return;
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
    setPhase("review");
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
        </label>
        {control}
        {error && <small role="alert">{error}</small>}
      </div>
    );
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
        <h2>Услуга не найдена</h2>
        <p className="muted">Возможно, ссылка устарела или услуга была снята с публикации.</p>
        <Link className="button secondary" href="/take">
          К каталогу услуг
        </Link>
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
          <li>Отслеживание статусов по заявкам появится в личном кабинете (в разработке).</li>
        </ol>
        <div className="actions">
          <Link className="button" href="/take">
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
            {screen.fields.map((field) => renderField(field))}
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
            ))}
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
      <aside className="card">{renderLevels()}</aside>
    </div>
  );
}
