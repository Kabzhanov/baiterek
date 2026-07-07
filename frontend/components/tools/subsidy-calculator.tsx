"use client";
// Калькулятор субсидируемой ставки (SPEC.md §4.7): платёж по полной ставке, платёж по
// субсидированной ставке, разница — на том же lib/calculators.ts движке.
import { useMemo, useState } from "react";
import { CALCULATOR_DISCLAIMER, calculateSubsidy, formatKzt } from "@/lib/calculators";

export function SubsidyCalculator() {
  const [principal, setPrincipal] = useState(10_000_000);
  const [fullRate, setFullRate] = useState(18);
  const [subsidizedRate, setSubsidizedRate] = useState(6);
  const [months, setMonths] = useState(36);

  const output = useMemo(() => {
    try {
      return { ok: true as const, result: calculateSubsidy(principal, fullRate, subsidizedRate, months) };
    } catch (error) {
      return { ok: false as const, message: error instanceof Error ? error.message : "Ошибка расчёта" };
    }
  }, [principal, fullRate, subsidizedRate, months]);

  return (
    <div className="card" id="subsidy">
      <h2>Калькулятор субсидируемой ставки</h2>
      <p className="muted">Сравнение платежа по полной рыночной ставке и по ставке с учётом субсидирования.</p>
      <div className="field">
        <label htmlFor="subsidy-principal">Сумма, ₸</label>
        <input
          id="subsidy-principal"
          type="number"
          min={1}
          value={principal}
          onChange={(e) => setPrincipal(Number(e.target.value))}
        />
      </div>
      <div className="field">
        <label htmlFor="subsidy-full-rate">Полная ставка, % годовых</label>
        <input
          id="subsidy-full-rate"
          type="number"
          min={0}
          step="0.1"
          value={fullRate}
          onChange={(e) => setFullRate(Number(e.target.value))}
        />
      </div>
      <div className="field">
        <label htmlFor="subsidy-rate">Субсидируемая ставка, % годовых</label>
        <input
          id="subsidy-rate"
          type="number"
          min={0}
          step="0.1"
          value={subsidizedRate}
          onChange={(e) => setSubsidizedRate(Number(e.target.value))}
        />
      </div>
      <div className="field">
        <label htmlFor="subsidy-months">Срок, мес.</label>
        <input
          id="subsidy-months"
          type="number"
          min={1}
          value={months}
          onChange={(e) => setMonths(Number(e.target.value))}
        />
      </div>

      {output.ok ? (
        <div className="computed-field" role="status">
          <strong>
            Платёж по полной ставке: {formatKzt(output.result.fullRatePayment)} · по субсидируемой:{" "}
            {formatKzt(output.result.subsidizedPayment)}
          </strong>
          <p>{output.result.explanation}</p>
        </div>
      ) : (
        <small role="alert">{output.message}</small>
      )}
      <p className="muted">{CALCULATOR_DISCLAIMER}</p>
    </div>
  );
}
