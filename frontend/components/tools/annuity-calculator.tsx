"use client";
// Калькулятор аннуитетного платежа (SPEC.md §4.7) — переиспользует lib/calculators.ts,
// формула которого идентична backend/app/engine/formulas.py's "annuity" op (см. docstring
// в lib/calculators.ts).
import { useMemo, useState } from "react";
import { CALCULATOR_DISCLAIMER, calculateAnnuity, formatKzt } from "@/lib/calculators";

export function AnnuityCalculator() {
  const [principal, setPrincipal] = useState(5_000_000);
  const [rate, setRate] = useState(15);
  const [months, setMonths] = useState(24);

  const output = useMemo(() => {
    try {
      return { ok: true as const, result: calculateAnnuity(principal, rate, months) };
    } catch (error) {
      return { ok: false as const, message: error instanceof Error ? error.message : "Ошибка расчёта" };
    }
  }, [principal, rate, months]);

  return (
    <div className="card" id="annuity">
      <h2>Калькулятор аннуитетного платежа</h2>
      <p className="muted">Равные ежемесячные платежи по кредиту или лизингу.</p>
      <div className="field">
        <label htmlFor="annuity-principal">Сумма, ₸</label>
        <input
          id="annuity-principal"
          type="number"
          min={1}
          value={principal}
          onChange={(e) => setPrincipal(Number(e.target.value))}
        />
      </div>
      <div className="field">
        <label htmlFor="annuity-rate">Ставка, % годовых</label>
        <input id="annuity-rate" type="number" min={0} step="0.1" value={rate} onChange={(e) => setRate(Number(e.target.value))} />
      </div>
      <div className="field">
        <label htmlFor="annuity-months">Срок, мес.</label>
        <input
          id="annuity-months"
          type="number"
          min={1}
          value={months}
          onChange={(e) => setMonths(Number(e.target.value))}
        />
      </div>

      {output.ok ? (
        <div className="computed-field" role="status">
          <strong>Ежемесячный платёж: {formatKzt(output.result.monthlyPayment)}</strong>
          <p>{output.result.explanation}</p>
        </div>
      ) : (
        <small role="alert">{output.message}</small>
      )}
      <p className="muted">{CALCULATOR_DISCLAIMER}</p>
    </div>
  );
}
