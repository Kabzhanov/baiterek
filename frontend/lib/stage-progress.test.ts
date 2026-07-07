import { describe, expect, it } from "vitest";
import { ApplicationApiError } from "./application-api";
import { buildStageProgress, classifyDraftError, isUnderReview, stageJustOpened } from "./stage-progress";

function apiError(status: number, code: string) {
  return new ApplicationApiError(status, { code, message: "x", details: {}, trace_id: "t" });
}

describe("classifyDraftError", () => {
  it("recognizes 409 stage_locked", () => {
    expect(classifyDraftError(apiError(409, "stage_locked"))).toBe("stage_locked");
  });

  it("recognizes 409 revision_conflict", () => {
    expect(classifyDraftError(apiError(409, "revision_conflict"))).toBe("revision_conflict");
  });

  it("treats an unrelated 409 code as other, not either known kind", () => {
    expect(classifyDraftError(apiError(409, "something_else"))).toBe("other");
  });

  it("treats a non-409 ApplicationApiError as other", () => {
    expect(classifyDraftError(apiError(422, "stage_locked"))).toBe("other");
  });

  it("treats a plain network failure as other", () => {
    expect(classifyDraftError(new Error("network down"))).toBe("other");
  });
});

describe("isUnderReview", () => {
  it("is true once submitted and the current stage is closed", () => {
    expect(isUnderReview("submitted", false)).toBe(true);
  });

  it("is false for a draft even if stage_open were somehow false", () => {
    expect(isUnderReview("draft", false)).toBe(false);
  });

  it("is false once the current stage has been reopened", () => {
    expect(isUnderReview("indicative_approved", true)).toBe(false);
  });
});

describe("stageJustOpened", () => {
  it("is true when a later stage opened after at least one earlier stage completed", () => {
    expect(stageJustOpened(["stage_1"], true)).toBe(true);
  });

  it("is false for a fresh single-stage draft (nothing completed yet)", () => {
    expect(stageJustOpened([], true)).toBe(false);
  });

  it("is false while the current stage is still closed (under review)", () => {
    expect(stageJustOpened(["stage_1"], false)).toBe(false);
  });
});

describe("buildStageProgress", () => {
  const stages = [
    { key: "stage_1", title: "Этап I" },
    { key: "stage_2", title: "Этап II" },
  ];

  it("marks a completed stage done and the checkpoint's stage current", () => {
    expect(buildStageProgress(stages, ["stage_1"], "stage_2")).toEqual([
      { key: "stage_1", title: "Этап I", state: "done" },
      { key: "stage_2", title: "Этап II", state: "current" },
    ]);
  });

  it("marks everything else upcoming", () => {
    expect(buildStageProgress(stages, [], "stage_1")).toEqual([
      { key: "stage_1", title: "Этап I", state: "current" },
      { key: "stage_2", title: "Этап II", state: "upcoming" },
    ]);
  });

  it("keeps Definition order even if completedStages lists keys out of order", () => {
    expect(buildStageProgress(stages, ["stage_2", "stage_1"], null).map((s) => s.state)).toEqual(["done", "done"]);
  });
});
