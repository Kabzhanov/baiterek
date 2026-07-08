import { describe, expect, it } from "vitest";
import { completenessEmptyMessage, degradedNote, formatSuggestionCount } from "./copilot";

describe("completenessEmptyMessage", () => {
  it("честно сообщает, что рекомендаций нет, а не молчит пустым списком", () => {
    expect(completenessEmptyMessage()).toContain("заполнены");
  });
});

describe("degradedNote", () => {
  it("различает текст для explain и completeness", () => {
    expect(degradedNote("explain")).toContain("Ответ");
    expect(degradedNote("completeness")).toContain("Подсказки");
  });
});

describe("formatSuggestionCount", () => {
  it("склоняет 1/2/5 по стандартным правилам", () => {
    expect(formatSuggestionCount(1)).toBe("1 рекомендация");
    expect(formatSuggestionCount(2)).toBe("2 рекомендации");
    expect(formatSuggestionCount(5)).toBe("5 рекомендаций");
  });

  it("11-14 — исключение из общего правила (рекомендаций, не рекомендация)", () => {
    expect(formatSuggestionCount(11)).toBe("11 рекомендаций");
    expect(formatSuggestionCount(12)).toBe("12 рекомендаций");
  });

  it("21/22 возвращаются к обычному склонению", () => {
    expect(formatSuggestionCount(21)).toBe("21 рекомендация");
    expect(formatSuggestionCount(22)).toBe("22 рекомендации");
  });

  it("0 склоняется как множественное число", () => {
    expect(formatSuggestionCount(0)).toBe("0 рекомендаций");
  });
});
