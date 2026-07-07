"use client";
// Живой превью шага «глазами клиента» для конструктора (SPEC.md §5.2 «холст-превью:
// живой рендер того же form-engine, что видит клиент»). Использует те же CSS-классы и
// разметку полей, что application-wizard.tsx (form-card / field / repeater-row, select с
// пустым «Выберите», чекбокс для boolean) — так превью в конструкторе пиксельно совпадает
// с анкетой заявителя. Инпуты неуправляемые: превью интерактивно, но ничего не сохраняет.
import type { AdminField } from "@/lib/definition-admin-types";

function PreviewField({ field }: { field: AdminField }) {
  if (field.type === "boolean") {
    return (
      <div className="field">
        <label>
          <input type="checkbox" /> {field.label}
          {field.required && " *"}
        </label>
        {field.hint && <small>{field.hint}</small>}
      </div>
    );
  }
  if (field.type === "repeater") {
    return (
      <div className="field">
        <label>
          {field.label}
          {field.required && " *"}
        </label>
        <div className="repeater-row">
          <p className="muted">Повторяемая группа — заявитель добавляет строки по кнопке «+ Добавить»</p>
        </div>
        {field.hint && <small>{field.hint}</small>}
      </div>
    );
  }
  return (
    <div className="field">
      <label htmlFor={`preview-${field.key}`}>
        {field.label}
        {field.required && " *"}
      </label>
      {field.type === "select" ? (
        <select id={`preview-${field.key}`} defaultValue="">
          <option value="">Выберите</option>
          {(field.options ?? []).map((option) => (
            <option key={option}>{option}</option>
          ))}
        </select>
      ) : field.type === "number" ? (
        <input
          id={`preview-${field.key}`}
          type="number"
          min={field.minimum ?? undefined}
          max={field.maximum ?? undefined}
        />
      ) : (
        <input id={`preview-${field.key}`} type="text" />
      )}
      {field.hint && <small>{field.hint}</small>}
    </div>
  );
}

export function StepPreview({
  stageTitle,
  stepTitle,
  fields,
}: {
  stageTitle: string;
  stepTitle: string;
  fields: AdminField[];
}) {
  return (
    <div className="form-card">
      <span className="pill">{stageTitle}</span>
      <h2>{stepTitle}</h2>
      {fields.length === 0 ? (
        <p className="muted">На этом шаге пока нет полей — добавьте их в дереве слева.</p>
      ) : (
        fields.map((field) => <PreviewField key={field.key} field={field} />)
      )}
      <button type="button" className="button" disabled>
        Сохранить и продолжить
      </button>
    </div>
  );
}
