// Предзаполнение по БИН из mock ГБД ЮЛ (SPEC.md §3.2/§8, "Обязательное расширение" §1:
// «ничего не спрашиваем, если можем узнать сами»). Чистая логика поверх `field.prefill`
// (см. backend/app/schemas/definition.py::FieldBase docstring for the convention this
// mirrors) и `GbdUlOut`, без React/DOM — тестируется отдельно (gbd-ul-prefill.test.ts).
import type { GbdUlOut } from "./application-types";

const BIN_RE = /^\d{12}$/;

/** БИН РК — ровно 12 цифр. Пробелы по краям (частая опечатка при вводе/вставке) не мешают. */
export function looksLikeBin(value: unknown): boolean {
  return typeof value === "string" && BIN_RE.test(value.trim());
}

/** Поле-триггер: при вводе похожего на БИН значения фронт вызывает GET /integrations/gbd-ul/{value}. */
export function isGbdLookupTrigger(prefill: string | null | undefined): boolean {
  return prefill === "gbd_ul.lookup";
}

const TARGET_ATTR: Record<string, keyof GbdUlOut> = {
  "gbd_ul.name": "name",
  "gbd_ul.address": "address",
  "gbd_ul.oked": "oked",
  "gbd_ul.oked_name": "oked_name",
  "gbd_ul.director": "director",
};

/** Целевое поле: заполняется из ответа lookup'а, а не вводится руками (пока не нажали «Изменить»). */
export function isGbdPrefillTarget(prefill: string | null | undefined): boolean {
  return !!prefill && prefill in TARGET_ATTR;
}

export function gbdTargetAttr(prefill: string | null | undefined): keyof GbdUlOut | null {
  return prefill && prefill in TARGET_ATTR ? TARGET_ATTR[prefill] : null;
}

/** Распределяет ответ ГБД ЮЛ по целевым полям (SPEC.md §1: для каждого поля с
 * `prefill: "gbd_ul.<attr>"` берёт `response[<attr>]`). Поля без такого `prefill` не
 * затрагиваются — вызывающий код мержит результат в data_delta так же, как обычную правку. */
export function distributeGbdUlResponse(
  fields: { key: string; prefill?: string | null }[],
  response: GbdUlOut,
): Record<string, string> {
  const result: Record<string, string> = {};
  for (const field of fields) {
    const attr = gbdTargetAttr(field.prefill);
    if (attr) result[field.key] = String(response[attr]);
  }
  return result;
}
