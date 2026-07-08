import { describe, expect, it } from "vitest";
import type { PlanScreen } from "./screen-plan";
import { RESTART_CONFIRM_MESSAGE, buildRestartDelta, firstScreenCheckpoint } from "./restart-wizard";

describe("RESTART_CONFIRM_MESSAGE", () => {
  it("is a non-empty confirmation prompt that warns the data will be cleared", () => {
    expect(RESTART_CONFIRM_MESSAGE).toContain("Начать заново");
    expect(RESTART_CONFIRM_MESSAGE.length).toBeGreaterThan(0);
  });
});

describe("buildRestartDelta", () => {
  it("blanks every filled scalar field to an empty string", () => {
    const delta = buildRestartDelta({ bin: "123", name: "ТОО Ромашка", amount: 500 });
    expect(delta).toEqual({ bin: "", name: "", amount: "" });
  });

  it("blanks a filled list field to an empty array (not a string)", () => {
    const delta = buildRestartDelta({ founders: ["A", "B"] });
    expect(delta).toEqual({ founders: [] });
  });

  it("skips fields that are already empty — nothing needless goes over the wire", () => {
    const delta = buildRestartDelta({ a: "", b: null, c: undefined, d: [], e: "x" });
    expect(delta).toEqual({ e: "" });
  });

  it("returns an empty delta for an already-clean draft", () => {
    expect(buildRestartDelta({})).toEqual({});
  });
});

describe("firstScreenCheckpoint", () => {
  const plan: PlanScreen[] = [
    {
      planIndex: 0,
      stageIndex: 0,
      stepIndex: 0,
      screenIndex: 0,
      stageKey: "stage_1",
      stageTitle: "Этап I",
      stepKey: "applicant",
      stepTitle: "Заявитель",
      screenKey: "bin",
      fieldKeys: ["bin", "name"],
    },
    {
      planIndex: 1,
      stageIndex: 0,
      stepIndex: 1,
      screenIndex: 0,
      stageKey: "stage_1",
      stageTitle: "Этап I",
      stepKey: "loan",
      stepTitle: "Кредит",
      screenKey: "amount",
      fieldKeys: ["amount"],
    },
  ];

  it("addresses the very first screen of the plan by its keys, not an index", () => {
    expect(firstScreenCheckpoint(plan)).toEqual({
      stage_key: "stage_1",
      step_key: "applicant",
      screen_key: "bin",
    });
  });

  it("returns null for an empty plan", () => {
    expect(firstScreenCheckpoint([])).toBeNull();
  });
});
