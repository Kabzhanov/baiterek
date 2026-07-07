// Инструменты и материалы (SPEC.md §4.7): "Минимум два работающих калькулятора
// (аннуитетный платеж по лизингу; субсидируемая ставка) — переиспользуем движок формул
// из конструктора". `annuityPayment` below is the SAME formula as the `"annuity"`
// operation in `backend/app/engine/formulas.py`:
//
//   rate = annual / 12
//   payment = principal / months                                    if rate == 0
//   payment = principal*rate*(1+rate)^n / ((1+rate)^n - 1)           otherwise
//
// The backend takes `annual` as a decimal fraction (0.12 for 12%); this module takes
// a whole percent (12) and divides by 100 first — same rate once computed. Verified
// against the backend (Decimal arithmetic) for the fixtures in calculators.test.ts.

export const CALCULATOR_DISCLAIMER =
  "Предварительный расчёт носит справочный характер и не является финансовым предложением. " +
  "Точные условия определяются организацией-партнёром при рассмотрении заявки.";

export function annuityPayment(principal: number, annualRatePercent: number, months: number): number {
  if (principal <= 0) throw new Error("Сумма должна быть больше нуля");
  if (months <= 0 || !Number.isFinite(months)) throw new Error("Срок должен быть больше нуля месяцев");
  if (annualRatePercent < 0) throw new Error("Ставка не может быть отрицательной");

  const rate = annualRatePercent / 100 / 12;
  if (rate === 0) return principal / months;
  const factor = Math.pow(1 + rate, months);
  return (principal * rate * factor) / (factor - 1);
}

export type AnnuityResult = {
  monthlyPayment: number;
  totalPayment: number;
  totalInterest: number;
  explanation: string;
};

export function calculateAnnuity(principal: number, annualRatePercent: number, months: number): AnnuityResult {
  const monthlyPayment = annuityPayment(principal, annualRatePercent, months);
  const totalPayment = monthlyPayment * months;
  const totalInterest = totalPayment - principal;
  return {
    monthlyPayment,
    totalPayment,
    totalInterest,
    explanation:
      `Ежемесячный аннуитетный платёж — ${formatKzt(monthlyPayment)} при сумме ${formatKzt(principal)}, ` +
      `ставке ${annualRatePercent}% годовых и сроке ${months} мес. Переплата за весь срок — ${formatKzt(totalInterest)}.`,
  };
}

export type SubsidyResult = {
  fullRatePayment: number;
  subsidizedPayment: number;
  monthlySaving: number;
  totalSaving: number;
  explanation: string;
};

export function calculateSubsidy(
  principal: number,
  fullRatePercent: number,
  subsidizedRatePercent: number,
  months: number,
): SubsidyResult {
  if (subsidizedRatePercent > fullRatePercent) {
    throw new Error("Субсидируемая ставка не может быть выше полной ставки");
  }
  const fullRatePayment = annuityPayment(principal, fullRatePercent, months);
  const subsidizedPayment = annuityPayment(principal, subsidizedRatePercent, months);
  const monthlySaving = fullRatePayment - subsidizedPayment;
  const totalSaving = monthlySaving * months;
  return {
    fullRatePayment,
    subsidizedPayment,
    monthlySaving,
    totalSaving,
    explanation:
      `По полной ставке ${fullRatePercent}% платёж — ${formatKzt(fullRatePayment)}, по субсидируемой ` +
      `${subsidizedRatePercent}% — ${formatKzt(subsidizedPayment)}. Экономия — ${formatKzt(monthlySaving)} в месяц, ` +
      `${formatKzt(totalSaving)} за весь срок ${months} мес.`,
  };
}

export function formatKzt(value: number): string {
  return `${Math.round(value).toLocaleString("ru-RU")} ₸`;
}
