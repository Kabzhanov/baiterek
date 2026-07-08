// Демо-автозаполнение мастера («Далее-Далее» для быстрого прохода жюри — задача для питча,
// не часть SPEC.md): строит валидные значения для полей ТЕКУЩЕГО ЭТАПА мастера (все шаги/
// экраны этапа сразу, а не только текущий видимый экран), используя тот же контракт
// (`DefinitionField`), что и обычный ручной ввод. Чистая логика без React/DOM — вызывающий
// код (application-wizard.tsx) прогоняет результат через тот же updateField()/autosave, что
// и ручной ввод, поэтому демо-заполнение не в обход API.
import type { DefinitionField, ServiceDefinitionDoc } from "./application-types";

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

function isEmptyValue(value: unknown): boolean {
  return value === undefined || value === null || value === "" || (Array.isArray(value) && value.length === 0);
}

// Только эти типы имеют ручной ввод в мастере (см. renderField в application-wizard.tsx) —
// будущие/нераспознанные типы полей (напр. `info`/`file`, если появятся) пропускаем, а не
// пытаемся угадать для них значение.
const FILLABLE_TYPES = new Set(["text", "number", "boolean", "select", "repeater"]);

/** Строит дельту демо-значений для ВСЕХ полей заданного этапа (`stageKey`) — по всем его
 * шагам/экранам сразу, а не только по текущему видимому экрану, и НЕЗАВИСИМО от текущей
 * видимости полей: некоторые поля становятся видимыми только после выбора конкретной ветки
 * (напр. select/boolean), поэтому, чтобы демо-проход прошёл по любой ветке без ручного
 * ввода, заполняются все поля этапа сразу. Пропускает вычисляемые поля (`definition.computed`,
 * их нельзя проставить руками) и поля неизвестного/нередактируемого типа. `currentData`
 * бережёт уже заполненные значения (ручной ввод, prefill из ГБД ЮЛ, повторный клик по
 * кнопке) — демо-заполнение не перетирает то, что уже валидно заполнено. */
export function buildStageDemoFillDelta(
  definition: ServiceDefinitionDoc,
  stageKey: string,
  currentData: Record<string, unknown>,
): Record<string, unknown> {
  const stage = definition.stages.find((s) => s.key === stageKey);
  if (!stage) return {};
  const computedKeys = new Set(definition.computed.map((c) => c.key));
  const delta: Record<string, unknown> = {};
  for (const step of stage.steps) {
    for (const field of step.fields) {
      if (computedKeys.has(field.key)) continue;
      if (!FILLABLE_TYPES.has(field.type)) continue;
      if (!isEmptyValue(currentData[field.key])) continue;
      delta[field.key] = demoValueForField(field, field.key);
    }
  }
  return delta;
}
