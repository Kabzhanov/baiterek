import { describe, expect, it } from "vitest";
import { annuityPayment, calculateAnnuity, calculateSubsidy } from "./calculators";

describe("annuityPayment", () => {
  // Fixtures cross-checked against backend/app/engine/formulas.py's "annuity" op
  // (Decimal arithmetic) — see task notes: same formula, same numbers.
  //   annuity(1_200_000, 0.12, 12) == 106618.5464140100488079853975
  //   annuity(5_000_000, 0,    24) == 208333.3333333333333333333333
  //   annuity(3_000_000, 0.18, 36) == 108457.1866077505102262236869
  it("matches the backend formula for a 12%/12mo loan", () => {
    expect(annuityPayment(1_200_000, 12, 12)).toBeCloseTo(106618.546414, 4);
  });

  it("falls back to principal/months at a zero rate (backend's rate==0 branch)", () => {
    expect(annuityPayment(5_000_000, 0, 24)).toBeCloseTo(208333.333333, 4);
  });

  it("matches the backend formula for an 18%/36mo loan", () => {
    expect(annuityPayment(3_000_000, 18, 36)).toBeCloseTo(108457.186608, 3);
  });

  it("rejects non-positive principal, term or negative rate", () => {
    expect(() => annuityPayment(0, 10, 12)).toThrow();
    expect(() => annuityPayment(100, 10, 0)).toThrow();
    expect(() => annuityPayment(100, -1, 12)).toThrow();
  });
});

describe("calculateAnnuity", () => {
  it("returns monthly payment, total payment, total interest and an explanation", () => {
    const result = calculateAnnuity(1_200_000, 12, 12);
    expect(result.monthlyPayment).toBeCloseTo(106618.546414, 4);
    expect(result.totalPayment).toBeCloseTo(result.monthlyPayment * 12, 6);
    expect(result.totalInterest).toBeCloseTo(result.totalPayment - 1_200_000, 6);
    expect(result.explanation).toContain("₸");
  });
});

describe("calculateSubsidy", () => {
  it("computes full-rate vs subsidized payment and the saving", () => {
    const result = calculateSubsidy(3_000_000, 18, 6, 36);
    const full = annuityPayment(3_000_000, 18, 36);
    const subsidized = annuityPayment(3_000_000, 6, 36);
    expect(result.fullRatePayment).toBeCloseTo(full, 6);
    expect(result.subsidizedPayment).toBeCloseTo(subsidized, 6);
    expect(result.monthlySaving).toBeCloseTo(full - subsidized, 6);
    expect(result.totalSaving).toBeCloseTo((full - subsidized) * 36, 6);
    expect(result.monthlySaving).toBeGreaterThan(0);
  });

  it("rejects a subsidized rate higher than the full rate", () => {
    expect(() => calculateSubsidy(1_000_000, 5, 10, 12)).toThrow();
  });
});
