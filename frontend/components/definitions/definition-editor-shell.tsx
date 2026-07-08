"use client";
// Визуальный конструктор услуги (SPEC.md §5.2, критерии 9.2+9.4): три панели —
// слева дерево этапы→шаги→поля (добавить/удалить/переместить), в центре живой превью
// текущего шага тем же рендерером, что видит клиент (StepPreview, form-engine), справа
// свойства выбранного элемента + редакторы meta. Autosave — PUT c debounce 800 мс
// (createDebouncedSaver из lib/draft-autosave, тот же паттерн, что в мастере заявителя).
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApplicationApiError, BackendUnavailableError } from "@/lib/application-api";
import { definitionAdminApi } from "@/lib/definition-api";
import { createDebouncedSaver } from "@/lib/draft-autosave";
import {
  addField,
  addStage,
  addStep,
  changeFieldType,
  findField,
  findStage,
  findStep,
  issueMatches,
  moveField,
  moveStage,
  moveStep,
  removeField,
  removeStage,
  removeStep,
  updateField,
  updateMeta,
  updateStage,
  updateStep,
  validateDefinition,
  type EditorSelection,
} from "@/lib/definition-editor";
import { StepPreview } from "@/components/form-engine/step-preview";
import type {
  AdminDefinitionDoc,
  AdminField,
  DefinitionDetail,
  DefinitionStatus,
} from "@/lib/definition-admin-types";

const FIELD_TYPE_LABELS: [string, string][] = [
  ["text", "Текст"],
  ["number", "Число"],
  ["boolean", "Да/нет"],
  ["select", "Справочник (список)"],
  ["repeater", "Повторяемая группа"],
];

const STATUS_LABELS: Record<DefinitionStatus, string> = {
  draft: "Черновик",
  published: "Опубликована",
  archived: "В архиве",
};

export type AiNotice = { warnings: string[]; degraded?: boolean };

export function aiNoticeStorageKey(id: string): string {
  return `baiterek.ai_notice.${id}`;
}

type Phase = "loading" | "unavailable" | "not_found" | "ready";
type SaveStatus = "idle" | "saving" | "saved" | "error";

function describeError(err: unknown): string {
  if (err instanceof BackendUnavailableError) return "Нет связи со стендом — изменения не сохранены.";
  if (err instanceof ApplicationApiError) return `Сервер отклонил сохранение: ${err.message}`;
  return "Не удалось сохранить изменения.";
}

export function DefinitionEditorShell({ definitionId }: { definitionId: string }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [detail, setDetail] = useState<DefinitionDetail | null>(null);
  const [doc, setDoc] = useState<AdminDefinitionDoc | null>(null);
  const [selection, setSelection] = useState<EditorSelection>({ kind: "meta" });
  // Мобильная раскладка (≤768px, см. globals.css): вместо трёх колонок сразу — вкладки
  // «Структура / Превью / Свойства». Игнорируется CSS на десктопе (там все три панели
  // видны одновременно как раньше — `data-mobile-active` там ничего не скрывает).
  const [mobileTab, setMobileTab] = useState<"tree" | "preview" | "properties">("tree");
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [publishMessage, setPublishMessage] = useState<string | null>(null);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [aiNotice, setAiNotice] = useState<AiNotice | null>(null);

  const docRef = useRef<AdminDefinitionDoc | null>(null);
  const readOnlyRef = useRef(false);
  const readOnly = detail !== null && detail.status !== "draft";
  readOnlyRef.current = readOnly;

  const persist = useCallback(async () => {
    const current = docRef.current;
    if (!current || readOnlyRef.current) return;
    setSaveStatus("saving");
    setSaveError(null);
    try {
      await definitionAdminApi.update(definitionId, current);
      setSaveStatus("saved");
      setSavedAt(new Date());
    } catch (err) {
      setSaveStatus("error");
      setSaveError(describeError(err));
    }
  }, [definitionId]);

  // Debounce-семантика та же, что у черновика заявителя: правки коалесцируются,
  // на сервер уходит целиком актуальный документ из docRef (последняя правка побеждает).
  const persistRef = useRef(persist);
  persistRef.current = persist;
  const saverRef = useRef(createDebouncedSaver(() => void persistRef.current()));

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const loaded = await definitionAdminApi.get(definitionId);
        if (cancelled) return;
        setDetail(loaded);
        setDoc(loaded.definition);
        docRef.current = loaded.definition;
        setPhase("ready");
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApplicationApiError && err.status === 404) {
          setPhase("not_found");
          return;
        }
        setPhase("unavailable");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [definitionId]);

  // Предупреждения AI-генератора, переданные экраном /create/generate через sessionStorage.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = window.sessionStorage.getItem(aiNoticeStorageKey(definitionId));
      if (raw) setAiNotice(JSON.parse(raw) as AiNotice);
    } catch {
      // повреждённая запись — просто не показываем плашку
    }
  }, [definitionId]);

  // Гарантированное сохранение при скрытии вкладки и размонтировании (паттерн мастера).
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

  function mutate(next: AdminDefinitionDoc) {
    setDoc(next);
    docRef.current = next;
    if (!readOnlyRef.current) saverRef.current.schedule({ definition: true });
  }

  function dismissAiNotice() {
    setAiNotice(null);
    if (typeof window !== "undefined") {
      window.sessionStorage.removeItem(aiNoticeStorageKey(definitionId));
    }
  }

  async function handlePublish() {
    if (!doc || !detail) return;
    setPublishError(null);
    const confirmed = window.confirm(
      "Опубликовать услугу? Она сразу появится в каталоге и станет доступна заявителям.",
    );
    if (!confirmed) return;
    saverRef.current.flushNow();
    setPublishing(true);
    try {
      const published = await definitionAdminApi.publish(definitionId);
      setDetail(published);
      setPublishMessage("Услуга опубликована и доступна в каталоге.");
    } catch (err) {
      setPublishError(describeError(err));
    } finally {
      setPublishing(false);
    }
  }

  if (phase === "loading") {
    return (
      <div className="form-card">
        <p className="muted">Загружаем черновик услуги…</p>
      </div>
    );
  }

  if (phase === "not_found") {
    return (
      <div className="form-card">
        <span className="pill">Не найдено</span>
        <h2>Такой услуги нет в реестре</h2>
        <p className="muted">Возможно, черновик был удалён. Вернитесь в реестр и выберите услугу из списка.</p>
        <Link className="button secondary" href="/create">
          В реестр услуг
        </Link>
      </div>
    );
  }

  if (phase === "unavailable" || !doc || !detail) {
    return (
      <div className="form-card">
        <span className="pill">Технический сбой</span>
        <h2>Стенд временно недоступен</h2>
        <p className="muted">
          Не удалось связаться с сервером конструктора. Это не имитация — редактирование сейчас
          недоступно. Попробуйте обновить страницу через минуту; сохранённые ранее правки не потеряются.
        </p>
        <button type="button" className="button" onClick={() => window.location.reload()}>
          Обновить страницу
        </button>
      </div>
    );
  }

  const issues = validateDefinition(doc);
  const selectionIssues = issues.filter((issue) => issueMatches(issue, selection));

  // Шаг для центрального превью: выбранный, либо первый доступный.
  const previewStage =
    (selection.kind !== "meta" && findStage(doc, selection.stage)) || doc.stages[0];
  const previewStep =
    (selection.kind === "step" || selection.kind === "field"
      ? findStep(doc, selection.stage, selection.step)
      : undefined) ?? previewStage?.steps[0];

  const selectedField =
    selection.kind === "field"
      ? findField(doc, selection.stage, selection.step, selection.field)
      : undefined;

  function renderTree() {
    if (!doc) return null;
    return (
      <ul className="tree">
        <li>
          <button aria-pressed={selection.kind === "meta"} onClick={() => setSelection({ kind: "meta" })}>
            Карточка услуги
            <br />
            <small>{doc.meta.title || "Без названия"}</small>
          </button>
        </li>
        {doc.stages.map((stage, stageIndex) => (
          <li key={stage.key}>
            <button
              aria-pressed={selection.kind === "stage" && selection.stage === stage.key}
              onClick={() => setSelection({ kind: "stage", stage: stage.key })}
            >
              Этап {stageIndex + 1}: {stage.title || "Без названия"}
              <br />
              <small>
                {stage.steps.length} шаг(ов) · {stage.steps.reduce((n, st) => n + st.fields.length, 0)} полей
              </small>
            </button>
            {!readOnly && (
              <div className="actions">
                <button type="button" className="button secondary" title="Вверх" disabled={stageIndex === 0} onClick={() => mutate(moveStage(doc, stage.key, -1))}>
                  ↑
                </button>
                <button type="button" className="button secondary" title="Вниз" disabled={stageIndex === doc.stages.length - 1} onClick={() => mutate(moveStage(doc, stage.key, 1))}>
                  ↓
                </button>
                <button
                  type="button"
                  className="button secondary"
                  title="Удалить этап"
                  onClick={() => {
                    setSelection({ kind: "meta" });
                    mutate(removeStage(doc, stage.key));
                  }}
                >
                  ✕
                </button>
              </div>
            )}
            <ul className="tree">
              {stage.steps.map((step, stepIndex) => (
                <li key={step.key}>
                  <button
                    aria-pressed={selection.kind === "step" && selection.step === step.key}
                    onClick={() => setSelection({ kind: "step", stage: stage.key, step: step.key })}
                  >
                    Шаг: {step.title || "Без названия"}
                    <br />
                    <small>{step.fields.length} полей</small>
                  </button>
                  {!readOnly && (
                    <div className="actions">
                      <button type="button" className="button secondary" title="Вверх" disabled={stepIndex === 0} onClick={() => mutate(moveStep(doc, stage.key, step.key, -1))}>
                        ↑
                      </button>
                      <button type="button" className="button secondary" title="Вниз" disabled={stepIndex === stage.steps.length - 1} onClick={() => mutate(moveStep(doc, stage.key, step.key, 1))}>
                        ↓
                      </button>
                      <button
                        type="button"
                        className="button secondary"
                        title="Удалить шаг"
                        onClick={() => {
                          setSelection({ kind: "stage", stage: stage.key });
                          mutate(removeStep(doc, stage.key, step.key));
                        }}
                      >
                        ✕
                      </button>
                    </div>
                  )}
                  <ul className="tree">
                    {step.fields.map((field, fieldIndex) => (
                      <li key={field.key}>
                        <button
                          aria-pressed={selection.kind === "field" && selection.field === field.key}
                          onClick={() =>
                            setSelection({ kind: "field", stage: stage.key, step: step.key, field: field.key })
                          }
                        >
                          {field.label || "Без названия"}
                          <br />
                          <small>{FIELD_TYPE_LABELS.find(([t]) => t === field.type)?.[1] ?? field.type}</small>
                        </button>
                        {!readOnly && (
                          <div className="actions">
                            <button type="button" className="button secondary" title="Вверх" disabled={fieldIndex === 0} onClick={() => mutate(moveField(doc, stage.key, step.key, field.key, -1))}>
                              ↑
                            </button>
                            <button type="button" className="button secondary" title="Вниз" disabled={fieldIndex === step.fields.length - 1} onClick={() => mutate(moveField(doc, stage.key, step.key, field.key, 1))}>
                              ↓
                            </button>
                            <button
                              type="button"
                              className="button secondary"
                              title="Удалить поле"
                              onClick={() => {
                                setSelection({ kind: "step", stage: stage.key, step: step.key });
                                mutate(removeField(doc, stage.key, step.key, field.key));
                              }}
                            >
                              ✕
                            </button>
                          </div>
                        )}
                      </li>
                    ))}
                    {!readOnly && (
                      <li>
                        <button
                          type="button"
                          onClick={() => {
                            const result = addField(doc, stage.key, step.key, "text");
                            mutate(result.doc);
                            setSelection({ kind: "field", stage: stage.key, step: step.key, field: result.key });
                          }}
                        >
                          + Добавить поле
                        </button>
                      </li>
                    )}
                  </ul>
                </li>
              ))}
              {!readOnly && (
                <li>
                  <button
                    type="button"
                    onClick={() => {
                      const result = addStep(doc, stage.key);
                      mutate(result.doc);
                      setSelection({ kind: "step", stage: stage.key, step: result.key });
                    }}
                  >
                    + Добавить шаг
                  </button>
                </li>
              )}
            </ul>
          </li>
        ))}
      </ul>
    );
  }

  function renderFieldProperties(field: AdminField) {
    if (!doc || selection.kind !== "field") return null;
    const { stage, step } = selection;
    return (
      <>
        <div className="field">
          <label htmlFor="prop-type">Тип поля</label>
          <select
            id="prop-type"
            value={field.type}
            disabled={readOnly}
            onChange={(e) => mutate(changeFieldType(doc, stage, step, field.key, e.target.value))}
          >
            {FIELD_TYPE_LABELS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="prop-label">Label (вопрос заявителю)</label>
          <input
            id="prop-label"
            value={field.label}
            disabled={readOnly}
            onChange={(e) => mutate(updateField(doc, stage, step, field.key, { label: e.target.value }))}
          />
        </div>
        <div className="field">
          <label htmlFor="prop-key">Ключ (техническое имя)</label>
          <input
            id="prop-key"
            value={field.key}
            disabled={readOnly}
            onChange={(e) => {
              const nextKey = e.target.value;
              mutate(updateField(doc, stage, step, field.key, { key: nextKey }));
              setSelection({ kind: "field", stage, step, field: nextKey });
            }}
          />
        </div>
        <div className="field">
          <label htmlFor="prop-hint">Подсказка (hint)</label>
          <input
            id="prop-hint"
            value={field.hint ?? ""}
            disabled={readOnly}
            onChange={(e) => mutate(updateField(doc, stage, step, field.key, { hint: e.target.value }))}
          />
        </div>
        <div className="field">
          <label>
            <input
              type="checkbox"
              checked={field.required ?? false}
              disabled={readOnly}
              onChange={(e) => mutate(updateField(doc, stage, step, field.key, { required: e.target.checked }))}
            />{" "}
            Обязательное поле
          </label>
        </div>
        {field.type === "select" && (
          <div className="field">
            <label htmlFor="prop-options">Справочник — варианты (по одному в строке)</label>
            <textarea
              id="prop-options"
              rows={5}
              value={(field.options ?? []).join("\n")}
              disabled={readOnly}
              onChange={(e) =>
                mutate(updateField(doc, stage, step, field.key, { options: e.target.value.split("\n") }))
              }
            />
          </div>
        )}
        {field.type === "number" && (
          <>
            <div className="field">
              <label htmlFor="prop-min">Минимум</label>
              <input
                id="prop-min"
                type="number"
                value={field.minimum ?? ""}
                disabled={readOnly}
                onChange={(e) =>
                  mutate(
                    updateField(doc, stage, step, field.key, {
                      minimum: e.target.value === "" ? null : Number(e.target.value),
                    }),
                  )
                }
              />
            </div>
            <div className="field">
              <label htmlFor="prop-max">Максимум</label>
              <input
                id="prop-max"
                type="number"
                value={field.maximum ?? ""}
                disabled={readOnly}
                onChange={(e) =>
                  mutate(
                    updateField(doc, stage, step, field.key, {
                      maximum: e.target.value === "" ? null : Number(e.target.value),
                    }),
                  )
                }
              />
            </div>
          </>
        )}
      </>
    );
  }

  function renderProperties() {
    if (!doc) return null;
    if (selection.kind === "meta") {
      return (
        <>
          <h2>Карточка услуги</h2>
          <div className="field">
            <label htmlFor="meta-title">Название услуги</label>
            <input
              id="meta-title"
              value={doc.meta.title}
              disabled={readOnly}
              onChange={(e) => mutate(updateMeta(doc, { title: e.target.value }))}
            />
          </div>
          <div className="field">
            <label htmlFor="meta-summary">Краткое описание (summary)</label>
            <textarea
              id="meta-summary"
              rows={4}
              value={doc.meta.description}
              disabled={readOnly}
              onChange={(e) => mutate(updateMeta(doc, { description: e.target.value }))}
            />
          </div>
          <div className="field">
            <label htmlFor="meta-conditions">Условия участия (по одному в строке: «Условие | Значение»)</label>
            <textarea
              id="meta-conditions"
              rows={5}
              value={(doc.meta.conditions ?? []).map((c) => `${c.label} | ${c.value}`).join("\n")}
              disabled={readOnly}
              onChange={(e) =>
                mutate(
                  updateMeta(doc, {
                    conditions: e.target.value
                      .split("\n")
                      .filter((line) => line.trim())
                      .map((line) => {
                        const [label, ...rest] = line.split("|");
                        return { label: label.trim(), value: rest.join("|").trim() };
                      }),
                  }),
                )
              }
            />
          </div>
          <div className="field">
            <label htmlFor="meta-docs">Чек-лист документов (по одному в строке)</label>
            <textarea
              id="meta-docs"
              rows={5}
              value={(doc.meta.documents_checklist ?? []).join("\n")}
              disabled={readOnly}
              onChange={(e) =>
                mutate(updateMeta(doc, { documents_checklist: e.target.value.split("\n") }))
              }
            />
          </div>
        </>
      );
    }
    if (selection.kind === "stage") {
      const stage = findStage(doc, selection.stage);
      if (!stage) return null;
      return (
        <>
          <h2>Этап</h2>
          <div className="field">
            <label htmlFor="stage-title">Название этапа</label>
            <input
              id="stage-title"
              value={stage.title}
              disabled={readOnly}
              onChange={(e) => mutate(updateStage(doc, stage.key, { title: e.target.value }))}
            />
          </div>
        </>
      );
    }
    if (selection.kind === "step") {
      const step = findStep(doc, selection.stage, selection.step);
      if (!step) return null;
      return (
        <>
          <h2>Шаг</h2>
          <div className="field">
            <label htmlFor="step-title">Название шага</label>
            <input
              id="step-title"
              value={step.title}
              disabled={readOnly}
              onChange={(e) => mutate(updateStep(doc, selection.stage, step.key, { title: e.target.value }))}
            />
          </div>
        </>
      );
    }
    if (selectedField) {
      return (
        <>
          <h2>Поле</h2>
          {renderFieldProperties(selectedField)}
        </>
      );
    }
    return <p className="muted">Выберите элемент в дереве слева.</p>;
  }

  return (
    <div className="workspace">
      <div className="workspace-tabs" role="tablist" aria-label="Разделы конструктора">
        <button type="button" role="tab" aria-selected={mobileTab === "tree"} onClick={() => setMobileTab("tree")}>
          Структура
        </button>
        <button type="button" role="tab" aria-selected={mobileTab === "preview"} onClick={() => setMobileTab("preview")}>
          Превью
        </button>
        <button type="button" role="tab" aria-selected={mobileTab === "properties"} onClick={() => setMobileTab("properties")}>
          Свойства
        </button>
      </div>
      <aside className="panel" data-mobile-active={mobileTab === "tree"}>
        <h2>Структура</h2>
        <p className="muted">
          {detail.title || doc.meta.title} · v{detail.version} ·{" "}
          {STATUS_LABELS[detail.status] ?? detail.status}
        </p>
        {renderTree()}
        {!readOnly && (
          <button
            type="button"
            className="button secondary"
            onClick={() => {
              const result = addStage(doc);
              mutate(result.doc);
              setSelection({ kind: "stage", stage: result.key });
            }}
          >
            + Добавить этап
          </button>
        )}
      </aside>

      <main className="canvas" id="main" data-mobile-active={mobileTab === "preview"}>
        {aiNotice && (
          <div className="mock" role="status">
            {aiNotice.degraded && <p><strong>AI в демо-режиме</strong> — черновик собран запасным генератором, проверьте его особенно внимательно.</p>}
            {aiNotice.warnings.length > 0 && (
              <>
                <p>Замечания AI-генератора — проверьте перед публикацией:</p>
                <ul>
                  {aiNotice.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </>
            )}
            <button type="button" className="button secondary" onClick={dismissAiNotice}>
              Понятно, скрыть
            </button>
          </div>
        )}

        {readOnly && (
          <div className="mock" role="status">
            Эта версия имеет статус «{STATUS_LABELS[detail.status] ?? detail.status}» и защищена от правок.
            Чтобы внести изменения, создайте копию-черновик в реестре («Дублировать»).
          </div>
        )}

        {publishMessage && (
          <div className="mock" role="status">
            {publishMessage}{" "}
            <Link href="/take">Открыть каталог</Link>
          </div>
        )}
        {publishError && (
          <div className="mock" role="alert">
            {publishError}
          </div>
        )}

        <div className="actions" style={{ marginBottom: 16 }}>
          <Link className="button secondary" href="/create">
            ← В реестр
          </Link>
          {!readOnly && (
            <button
              type="button"
              className="button"
              disabled={publishing || issues.length > 0}
              onClick={() => void handlePublish()}
            >
              {publishing ? "Публикуем…" : "Опубликовать"}
            </button>
          )}
          <p className="save-indicator" data-status={saveStatus} role="status">
            {saveStatus === "saving" && "Сохраняем черновик…"}
            {saveStatus === "saved" &&
              savedAt &&
              `Черновик сохранён в ${savedAt.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`}
            {saveStatus === "error" && (saveError ?? "Не удалось сохранить изменения.")}
          </p>
        </div>

        {issues.length > 0 && (
          <div className="mock" role="alert">
            <p>Публикация недоступна, пока есть замечания ({issues.length}):</p>
            <ul>
              {issues.map((issue, index) => (
                <li key={index}>
                  <button type="button" onClick={() => setSelection(issue.selection)}>
                    {issue.message}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <h1 style={{ fontSize: "1.6rem", marginBottom: 12 }}>Превью «глазами клиента»</h1>
        {selection.kind === "meta" ? (
          <div className="card">
            <span className="pill">Карточка услуги в каталоге</span>
            <h2>{doc.meta.title || "Без названия"}</h2>
            <p className="muted">{doc.meta.description || "Краткое описание появится здесь."}</p>
            {(doc.meta.conditions ?? []).length > 0 && (
              <>
                <h3>Условия</h3>
                <ul>
                  {(doc.meta.conditions ?? []).map((c, i) => (
                    <li key={i}>
                      {c.label}
                      {c.value ? `: ${c.value}` : ""}
                    </li>
                  ))}
                </ul>
              </>
            )}
            {(doc.meta.documents_checklist ?? []).filter((d) => d.trim()).length > 0 && (
              <>
                <h3>Документы</h3>
                <ul>
                  {(doc.meta.documents_checklist ?? [])
                    .filter((d) => d.trim())
                    .map((d, i) => (
                      <li key={i}>{d}</li>
                    ))}
                </ul>
              </>
            )}
          </div>
        ) : previewStage && previewStep ? (
          <StepPreview stageTitle={previewStage.title} stepTitle={previewStep.title} fields={previewStep.fields} />
        ) : (
          <p className="muted">Добавьте этап и шаг, чтобы увидеть превью анкеты.</p>
        )}
      </main>

      <aside className="properties" data-mobile-active={mobileTab === "properties"}>
        {renderProperties()}
        {selectionIssues.length > 0 && (
          <div className="field">
            {selectionIssues.map((issue, index) => (
              <small role="alert" key={index}>
                {issue.message}
              </small>
            ))}
          </div>
        )}
      </aside>
    </div>
  );
}
