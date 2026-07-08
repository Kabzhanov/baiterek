import { describe, expect, it } from "vitest";
import type { DefinitionField, ScreenContract } from "./application-types";
import { DEMO_BIN, buildDemoFillDelta, demoValueForField } from "./demo-fill";

function field(overrides: Partial<DefinitionField> & { key: string; type: string }): DefinitionField {
  return { label: overrides.key, ...overrides } as DefinitionField;
}

describe("demoValueForField", () => {
  it("picks the first option for a select field", () => {
    const def = field({ key: "org_form", type: "select", options: ["ТОО", "ИП", "АО"] });
    expect(demoValueForField(def, "org_form")).toBe("ТОО");
  });

  it("falls back to text for a select field without options", () => {
    const def = field({ key: "org_form", type: "select", options: [] });
    expect(demoValueForField(def, "org_form")).toBe("Демо-значение: org_form");
  });

  it("returns true for a boolean field", () => {
    const def = field({ key: "has_export", type: "boolean" });
    expect(demoValueForField(def, "has_export")).toBe(true);
  });

  it("returns a percent-shaped number clamped to <=100", () => {
    const def = field({ key: "subsidy_rate", label: "Ставка субсидирования, %", type: "number", maximum: 100 });
    const value = demoValueForField(def, "subsidy_rate") as number;
    expect(value).toBeLessThanOrEqual(100);
    expect(value).toBe(12);
  });

  it("returns a year-shaped number for a year field", () => {
    const def = field({ key: "founding_year", label: "Год основания", type: "number" });
    expect(demoValueForField(def, "founding_year")).toBe(2024);
  });

  it("returns a month-shaped number for a term-in-months field", () => {
    const def = field({ key: "term", label: "Срок, мес.", type: "number" });
    expect(demoValueForField(def, "term")).toBe(24);
  });

  it("returns a large sum for an amount field", () => {
    const def = field({ key: "loan_amount", label: "Сумма займа", type: "number" });
    expect(demoValueForField(def, "loan_amount")).toBe(1_000_000);
  });

  it("clamps a number value into the field's min/max range", () => {
    const def = field({ key: "loan_amount", label: "Сумма займа", type: "number", minimum: 0, maximum: 500 });
    expect(demoValueForField(def, "loan_amount")).toBe(500);
  });

  it("returns one row for a repeater field", () => {
    const def = field({ key: "founders", label: "Учредители", type: "repeater" });
    expect(demoValueForField(def, "founders")).toEqual(["Демо-значение: Учредители"]);
  });

  it("returns the mock BIN for a BIN-shaped text field", () => {
    const def = field({ key: "applicant_bin", label: "БИН заявителя", type: "text", prefill: "gbd_ul.lookup" });
    expect(demoValueForField(def, "applicant_bin")).toBe(DEMO_BIN);
  });

  it("returns a plausible phone for a phone field", () => {
    const def = field({ key: "contact_phone", label: "Контактный телефон", type: "text" });
    expect(demoValueForField(def, "contact_phone")).toBe("+7 700 000 00 00");
  });

  it("returns a generic placeholder for a plain text field", () => {
    const def = field({ key: "notes", label: "Комментарий", type: "text" });
    expect(demoValueForField(def, "notes")).toBe("Демо-значение: Комментарий");
  });
});

describe("buildDemoFillDelta", () => {
  const fieldIndexMap = new Map<string, DefinitionField>([
    ["applicant_bin", field({ key: "applicant_bin", label: "БИН", type: "text", prefill: "gbd_ul.lookup" })],
    ["amount", field({ key: "amount", label: "Сумма", type: "number" })],
    ["agree", field({ key: "agree", label: "Согласие", type: "boolean" })],
  ]);

  function screenWith(fields: ScreenContract["fields"], computed: Record<string, unknown> = {}): ScreenContract {
    return {
      stage: "s",
      step: "st",
      screen: 0,
      fields,
      computed,
      validation: [],
      progress: { current: 1, total: 1 },
      explanations: { rules: [], computed: {} },
    };
  }

  it("fills every visible, enabled, non-computed field on the current screen", () => {
    const screen = screenWith([
      { key: "applicant_bin", type: "text", label: "БИН", visible: true, required: true, enabled: true, prefill: "gbd_ul.lookup", hint: null },
      { key: "amount", type: "number", label: "Сумма", visible: true, required: true, enabled: true, prefill: null, hint: null },
      { key: "agree", type: "boolean", label: "Согласие", visible: true, required: false, enabled: true, prefill: null, hint: null },
    ]);
    const delta = buildDemoFillDelta(screen, fieldIndexMap);
    expect(delta).toEqual({ applicant_bin: DEMO_BIN, amount: 1_000_000, agree: true });
  });

  it("skips fields that are not visible", () => {
    const screen = screenWith([
      { key: "amount", type: "number", label: "Сумма", visible: false, required: true, enabled: true, prefill: null, hint: null },
    ]);
    expect(buildDemoFillDelta(screen, fieldIndexMap)).toEqual({});
  });

  it("skips fields that are disabled", () => {
    const screen = screenWith([
      { key: "amount", type: "number", label: "Сумма", visible: true, required: true, enabled: false, prefill: null, hint: null },
    ]);
    expect(buildDemoFillDelta(screen, fieldIndexMap)).toEqual({});
  });

  it("skips computed fields — they cannot be set manually", () => {
    const screen = screenWith(
      [{ key: "amount", type: "number", label: "Сумма", visible: true, required: true, enabled: true, prefill: null, hint: null }],
      { amount: 42 },
    );
    expect(buildDemoFillDelta(screen, fieldIndexMap)).toEqual({});
  });
});
