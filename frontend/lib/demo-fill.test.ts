import { describe, expect, it } from "vitest";
import type { DefinitionField, ServiceDefinitionDoc } from "./application-types";
import { DEMO_BIN, buildStageDemoFillDelta, demoValueForField } from "./demo-fill";

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

describe("buildStageDemoFillDelta", () => {
  function definitionWith(overrides: Partial<ServiceDefinitionDoc>): ServiceDefinitionDoc {
    return {
      schema_version: "1.0",
      service_id: "svc-1",
      version: 1,
      meta: { title: "Тест", description: "" },
      stages: [],
      rules: [],
      computed: [],
      statuses: [],
      transitions: [],
      integrations: [],
      ...overrides,
    };
  }

  // Two steps in the same stage, plus a branch-select field whose two possible targets
  // (`branch_a_only`/`branch_b_only`) live on a *later* screen and would normally only be
  // visible after the applicant picks a branch — the whole point of this function is to
  // fill both regardless, so the applicant never hits an unfilled required field mid-branch.
  const definition = definitionWith({
    stages: [
      {
        key: "stage1",
        title: "Этап I",
        steps: [
          {
            key: "step1",
            title: "Шаг 1",
            fields: [
              field({ key: "applicant_bin", label: "БИН", type: "text", prefill: "gbd_ul.lookup" }),
              field({ key: "branch", label: "Форма организации", type: "select", options: ["ИП", "ТОО"] }),
            ],
          },
          {
            key: "step2",
            title: "Шаг 2",
            fields: [
              field({ key: "branch_a_only", label: "Поле для ИП", type: "text" }),
              field({ key: "branch_b_only", label: "Поле для ТОО", type: "text" }),
              field({ key: "amount", label: "Сумма", type: "number" }),
              field({ key: "total", label: "Итого", type: "number" }),
            ],
          },
        ],
      },
      {
        key: "stage2",
        title: "Этап II",
        steps: [{ key: "step3", title: "Шаг 3", fields: [field({ key: "stage2_field", label: "Поле этапа II", type: "text" })] }],
      },
    ],
    computed: [{ key: "total", expression: {} }],
  });

  it("fills every fillable, non-computed field across every step of the stage, regardless of branch visibility", () => {
    const delta = buildStageDemoFillDelta(definition, "stage1", {});
    expect(delta).toEqual({
      applicant_bin: DEMO_BIN,
      branch: "ИП",
      branch_a_only: "Демо-значение: Поле для ИП",
      branch_b_only: "Демо-значение: Поле для ТОО",
      amount: 1_000_000,
    });
  });

  it("does not touch fields belonging to a different stage", () => {
    const delta = buildStageDemoFillDelta(definition, "stage1", {});
    expect(delta).not.toHaveProperty("stage2_field");
  });

  it("skips computed fields — they cannot be set manually", () => {
    const delta = buildStageDemoFillDelta(definition, "stage1", {});
    expect(delta).not.toHaveProperty("total");
  });

  it("does not overwrite fields that already have a value (manual input or GBD prefill)", () => {
    const delta = buildStageDemoFillDelta(definition, "stage1", { applicant_bin: "111111111111", amount: 250 });
    expect(delta).toEqual({
      branch: "ИП",
      branch_a_only: "Демо-значение: Поле для ИП",
      branch_b_only: "Демо-значение: Поле для ТОО",
    });
  });

  it("returns an empty delta for an unknown stage key", () => {
    expect(buildStageDemoFillDelta(definition, "no-such-stage", {})).toEqual({});
  });
});
