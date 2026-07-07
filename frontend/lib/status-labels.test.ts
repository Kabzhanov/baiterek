import { describe, expect, it } from "vitest";
import { nextSteps, statusLabel } from "./status-labels";

describe("statusLabel", () => {
  it("предпочитает labels_plain из Definition услуги", () => {
    expect(statusLabel("in_review_bpm", { in_review_bpm: "Заявку рассматривает Даму" })).toBe(
      "Заявку рассматривает Даму",
    );
  });

  it("падает на общий словарь, если организация не дала подпись", () => {
    expect(statusLabel("draft", {})).toBe("Черновик");
    expect(statusLabel("submitted")).toBe("Заявка отправлена");
  });

  it("показывает сырой статус, если подписи нет нигде (честнее, чем прятать)", () => {
    expect(statusLabel("custom_status", {})).toBe("custom_status");
  });
});

describe("nextSteps", () => {
  it("для черновика зовёт дозаполнить и отправить", () => {
    expect(nextSteps("draft").join(" ")).toContain("Дозаполните");
  });

  it("для рассмотрения и незнакомых статусов — общий сценарий рассмотрения", () => {
    for (const status of ["submitted", "in_review_bpm", "something_new"]) {
      expect(nextSteps(status).join(" ")).toContain("рассматривает");
    }
  });

  it("для финальных статусов — свои развязки", () => {
    expect(nextSteps("approved").join(" ")).toContain("в вашу пользу");
    expect(nextSteps("rejected").join(" ")).toContain("отрицательное");
  });
});
