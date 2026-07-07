import { describe, expect, it } from "vitest";
import {
  addField,
  addStage,
  addStep,
  changeFieldType,
  createEmptyDefinition,
  findField,
  findStep,
  issueMatches,
  moveField,
  moveStage,
  moveStep,
  removeField,
  removeStage,
  removeStep,
  uniqueKey,
  updateField,
  updateMeta,
  updateStage,
  updateStep,
  validateDefinition,
} from "./definition-editor";

function baseDoc() {
  return createEmptyDefinition("Тестовая услуга");
}

describe("uniqueKey", () => {
  it("возвращает base, если ключ свободен", () => {
    expect(uniqueKey("stage", ["step-1"])).toBe("stage");
  });

  it("подбирает первый свободный суффикс", () => {
    expect(uniqueKey("stage", ["stage", "stage-2"])).toBe("stage-3");
  });
});

describe("createEmptyDefinition", () => {
  it("создаёт валидный документ с этапом, шагом и полем", () => {
    const doc = baseDoc();
    expect(doc.meta.title).toBe("Тестовая услуга");
    expect(doc.stages).toHaveLength(1);
    expect(doc.stages[0].steps[0].fields).toHaveLength(1);
    expect(doc.statuses.length).toBeGreaterThan(0);
    expect(validateDefinition(doc)).toEqual([]);
  });
});

describe("операции с этапами", () => {
  it("addStage добавляет этап с шагом и уникальным ключом", () => {
    const { doc, key } = addStage(baseDoc());
    expect(doc.stages).toHaveLength(2);
    expect(key).not.toBe(doc.stages[0].key);
    expect(doc.stages[1].steps).toHaveLength(1);
  });

  it("removeStage удаляет этап и не мутирует исходный документ", () => {
    const original = addStage(baseDoc()).doc;
    const next = removeStage(original, original.stages[0].key);
    expect(next.stages).toHaveLength(1);
    expect(original.stages).toHaveLength(2);
  });

  it("moveStage меняет местами соседние этапы и игнорирует выход за границы", () => {
    const doc = addStage(baseDoc()).doc;
    const [a, b] = doc.stages.map((s) => s.key);
    const swapped = moveStage(doc, b, -1);
    expect(swapped.stages.map((s) => s.key)).toEqual([b, a]);
    expect(moveStage(doc, a, -1).stages.map((s) => s.key)).toEqual([a, b]);
    expect(moveStage(doc, b, 1).stages.map((s) => s.key)).toEqual([a, b]);
  });

  it("updateStage меняет название", () => {
    const doc = baseDoc();
    const next = updateStage(doc, doc.stages[0].key, { title: "Финансирование" });
    expect(next.stages[0].title).toBe("Финансирование");
  });
});

describe("операции с шагами", () => {
  it("addStep добавляет шаг в нужный этап", () => {
    const doc = baseDoc();
    const { doc: next, key } = addStep(doc, doc.stages[0].key);
    expect(next.stages[0].steps).toHaveLength(2);
    expect(findStep(next, doc.stages[0].key, key)).toBeDefined();
  });

  it("ключи шагов уникальны между этапами", () => {
    const withStage = addStage(baseDoc()).doc;
    const { doc: next } = addStep(withStage, withStage.stages[0].key);
    const keys = next.stages.flatMap((s) => s.steps.map((st) => st.key));
    expect(new Set(keys).size).toBe(keys.length);
  });

  it("removeStep и moveStep работают внутри этапа", () => {
    const doc = baseDoc();
    const stageKey = doc.stages[0].key;
    const { doc: withStep, key } = addStep(doc, stageKey);
    const firstKey = withStep.stages[0].steps[0].key;
    const moved = moveStep(withStep, stageKey, key, -1);
    expect(moved.stages[0].steps[0].key).toBe(key);
    const removed = removeStep(moved, stageKey, firstKey);
    expect(removed.stages[0].steps.map((s) => s.key)).toEqual([key]);
  });

  it("updateStep меняет название шага", () => {
    const doc = baseDoc();
    const next = updateStep(doc, doc.stages[0].key, doc.stages[0].steps[0].key, { title: "Документы" });
    expect(next.stages[0].steps[0].title).toBe("Документы");
  });
});

describe("операции с полями", () => {
  it("addField(select) сразу получает options", () => {
    const doc = baseDoc();
    const stageKey = doc.stages[0].key;
    const stepKey = doc.stages[0].steps[0].key;
    const { doc: next, key } = addField(doc, stageKey, stepKey, "select");
    const field = findField(next, stageKey, stepKey, key);
    expect(field?.type).toBe("select");
    expect(field?.options?.length).toBeGreaterThan(0);
  });

  it("moveField/removeField переупорядочивают и удаляют", () => {
    const doc = baseDoc();
    const stageKey = doc.stages[0].key;
    const stepKey = doc.stages[0].steps[0].key;
    const first = doc.stages[0].steps[0].fields[0].key;
    const { doc: withField, key } = addField(doc, stageKey, stepKey, "number");
    const moved = moveField(withField, stageKey, stepKey, key, -1);
    expect(moved.stages[0].steps[0].fields[0].key).toBe(key);
    const removed = removeField(moved, stageKey, stepKey, first);
    expect(removed.stages[0].steps[0].fields.map((f) => f.key)).toEqual([key]);
  });

  it("updateField меняет label/required точечно", () => {
    const doc = baseDoc();
    const stageKey = doc.stages[0].key;
    const stepKey = doc.stages[0].steps[0].key;
    const fieldKey = doc.stages[0].steps[0].fields[0].key;
    const next = updateField(doc, stageKey, stepKey, fieldKey, { label: "БИН", required: false });
    const field = findField(next, stageKey, stepKey, fieldKey);
    expect(field?.label).toBe("БИН");
    expect(field?.required).toBe(false);
  });

  it("changeFieldType text→select добавляет options, select→text убирает их", () => {
    const doc = baseDoc();
    const stageKey = doc.stages[0].key;
    const stepKey = doc.stages[0].steps[0].key;
    const fieldKey = doc.stages[0].steps[0].fields[0].key;
    const asSelect = changeFieldType(doc, stageKey, stepKey, fieldKey, "select");
    expect(findField(asSelect, stageKey, stepKey, fieldKey)?.options).toEqual(["Вариант 1"]);
    const backToText = changeFieldType(asSelect, stageKey, stepKey, fieldKey, "text");
    const field = findField(backToText, stageKey, stepKey, fieldKey);
    expect(field?.type).toBe("text");
    expect(field?.options).toBeUndefined();
    expect(field?.label).toBe("Наименование заявителя");
  });
});

describe("updateMeta", () => {
  it("обновляет только переданные поля", () => {
    const doc = baseDoc();
    const next = updateMeta(doc, { description: "Краткое описание" });
    expect(next.meta.description).toBe("Краткое описание");
    expect(next.meta.title).toBe("Тестовая услуга");
  });
});

describe("validateDefinition", () => {
  it("ловит пустой label поля", () => {
    const doc = baseDoc();
    const stageKey = doc.stages[0].key;
    const stepKey = doc.stages[0].steps[0].key;
    const fieldKey = doc.stages[0].steps[0].fields[0].key;
    const broken = updateField(doc, stageKey, stepKey, fieldKey, { label: "  " });
    const issues = validateDefinition(broken);
    expect(issues.some((i) => i.message === "Пустой label поля")).toBe(true);
    expect(
      issues.some((i) => issueMatches(i, { kind: "field", stage: stageKey, step: stepKey, field: fieldKey })),
    ).toBe(true);
  });

  it("ловит пустое название услуги и дубликаты ключей полей", () => {
    const doc = baseDoc();
    const stageKey = doc.stages[0].key;
    const stepKey = doc.stages[0].steps[0].key;
    const existingKey = doc.stages[0].steps[0].fields[0].key;
    const { doc: withField, key } = addField(doc, stageKey, stepKey, "text");
    const withDuplicate = updateField(withField, stageKey, stepKey, key, { key: existingKey });
    const noTitle = updateMeta(withDuplicate, { title: "" });
    const messages = validateDefinition(noTitle).map((i) => i.message);
    expect(messages).toContain("Укажите название услуги");
    expect(messages.some((m) => m.includes("Дублируется ключ поля"))).toBe(true);
  });

  it("ловит справочник без вариантов и min>max", () => {
    const doc = baseDoc();
    const stageKey = doc.stages[0].key;
    const stepKey = doc.stages[0].steps[0].key;
    const { doc: withSelect, key: selectKey } = addField(doc, stageKey, stepKey, "select");
    const { doc: withNumber, key: numberKey } = addField(withSelect, stageKey, stepKey, "number");
    let broken = updateField(withNumber, stageKey, stepKey, selectKey, { options: ["  "] });
    broken = updateField(broken, stageKey, stepKey, numberKey, { minimum: 10, maximum: 5 });
    const messages = validateDefinition(broken).map((i) => i.message);
    expect(messages).toContain("У справочника нет ни одного варианта");
    expect(messages).toContain("Минимум больше максимума");
  });

  it("ловит этап без шагов и пустые статусы", () => {
    const doc = baseDoc();
    const { doc: withStage, key } = addStage(doc);
    const noSteps = {
      ...withStage,
      stages: withStage.stages.map((s) => (s.key === key ? { ...s, steps: [] } : s)),
      statuses: [] as string[],
    };
    const messages = validateDefinition(noSteps).map((i) => i.message);
    expect(messages).toContain("В этапе нет ни одного шага");
    expect(messages).toContain("Не задан ни один статус заявки");
  });
});
