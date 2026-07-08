// Pure, framework-free helpers for the two AI copilots (SPEC.md §7.1) — kept separate
// from the components (ServiceExplainCard, ApplicationWizard's completeness block) so
// the text-formatting logic is unit-testable without rendering React. See
// lib/copilot.test.ts.

/** Message shown on the review screen when a completeness check finds nothing to flag —
 * an explicit, honest "checked, all good" rather than a silently empty list. */
export function completenessEmptyMessage(): string {
  return "Похоже, все обязательные поля этого этапа заполнены.";
}

/** Note shown alongside an AI answer once `degraded: true` came back — SPEC.md §7.3
 * "функциональность портала не деградирует", so this is informational, never blocking. */
export function degradedNote(kind: "explain" | "completeness"): string {
  return kind === "explain"
    ? "Ответ сформирован в упрощённом режиме — ИИ временно недоступен."
    : "Подсказки сформированы в упрощённом режиме — ИИ временно недоступен.";
}

/** Correct Russian pluralisation of "рекомендация" for a suggestion-count label
 * (1 рекомендация / 2 рекомендации / 5 рекомендаций / 11 рекомендаций / 21 рекомендация). */
export function formatSuggestionCount(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  let word: string;
  if (mod10 === 1 && mod100 !== 11) word = "рекомендация";
  else if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) word = "рекомендации";
  else word = "рекомендаций";
  return `${count} ${word}`;
}
