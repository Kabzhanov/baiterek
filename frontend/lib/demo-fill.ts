// Демо-автозаполнение мастера («Далее-Далее» для быстрого прохода жюри — задача для питча,
// не часть SPEC.md): строит валидные значения для полей ТЕКУЩЕГО экрана мастера, используя
// тот же контракт (`ScreenContract`/`DefinitionField`), что и обычный ручной ввод. Чистая
// логика без React/DOM — вызывающий код (application-wizard.tsx) прогоняет результат через
// тот же updateField()/autosave, что и ручной ввод, поэтому демо-заполнение не в обход API.
import type { DefinitionField, ScreenContract } from "./application-types";

// Валидный БИН из mock-ГБД ЮЛ (см. backend mock data) — подставляется в поле-триггер
// `prefill: "gbd_ul.lookup"`, чтобы демо-проход тоже показал prefill-сводку компании.
export const DEMO_BIN = "990101400000";

function demoTextValue(def: DefinitionField | undefined, key: string): string {
  const label = (def?.label ?? "").toLowerCase();
  const k = key.toLowerCase();
  if (k.includes("bin") || label.includes("бин")) return DEMO_BIN;
  if (k.includes("phone") || label.includes("телефон")) return "+7 700 000 00 00";
  if (k.includes("email") || label.includes("почта") || label.includes("email")) return "demo@example.kz";
  if (label.includes("адрес") || k.includes("address")) return "г. Астана, ул. Демонстрационная, 1";
  if (label.includes("фио") || label.includes("руководител") || label.includes("директор")) return "Демонов Демо Демонович";
  if (label.includes("название") || label.includes("наименование") || label.includes("компан") || label.includes("организац")) {
    return "Демо-организация";
  }
  const trimmedLabel = def?.label ?? key;
  return `Демо-значение: ${trimmedLabel}`;
}

function clampToRange(def: DefinitionField | undefined, value: number): number {
  let v = value;
  if (def?.minimum != null && v < def.minimum) v = def.minimum;
  if (def?.maximum != null && v > def.maximum) v = def.maximum;
  return v;
}

function demoNumberValue(def: DefinitionField | undefined, key: string): number {
  const label = (def?.label ?? "").toLowerCase();
  const k = key.toLowerCase();
  if (label.includes("процент") || label.includes("ставк") || k.includes("percent") || k.includes("rate")) {
    return clampToRange(def, 12);
  }
  if (label.includes("год") || k.includes("year")) return clampToRange(def, 2024);
  // «мес» (не только полное «месяц») — реальные лейблы часто сокращают: «Срок, мес.».
  if (label.includes("мес") || k.includes("month")) return clampToRange(def, 24);
  if (
    label.includes("сумм") ||
    label.includes("стоимост") ||
    k.includes("amount") ||
    k.includes("sum") ||
    k.includes("price") ||
    k.includes("cost")
  ) {
    return clampToRange(def, 1_000_000);
  }
  return clampToRange(def, def?.minimum ?? 1);
}

/** Одно валидное демо-значение поля по его типу/правилам — детерминированно, без побочных
 * эффектов (SPEC-независимая утилита). */
export function demoValueForField(def: DefinitionField | undefined, key: string): unknown {
  const type = def?.type;
  if (type === "select") {
    const options = def?.options ?? [];
    return options.length > 0 ? options[0] : demoTextValue(def, key);
  }
  if (type === "boolean") return true;
  if (type === "number") return demoNumberValue(def, key);
  if (type === "repeater") return [demoTextValue(def, key)];
  return demoTextValue(def, key);
}

/** Строит дельту демо-значений для всех видимых и включённых полей текущего экрана —
 * пропускает вычисляемые поля (`screen.computed`), которые нельзя проставить руками, и
 * скрытые/выключенные правилами поля (иначе демо-заполнение обошло бы ту же видимость,
 * что видит заявитель). */
export function buildDemoFillDelta(
  screen: ScreenContract,
  fieldIndexMap: Map<string, DefinitionField>,
): Record<string, unknown> {
  const delta: Record<string, unknown> = {};
  for (const field of screen.fields) {
    if (!field.visible || !field.enabled) continue;
    if (field.key in screen.computed) continue;
    const def = fieldIndexMap.get(field.key);
    delta[field.key] = demoValueForField(def, field.key);
  }
  return delta;
}
