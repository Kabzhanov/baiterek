// Shared formatting helpers for the map + summary panel (SPEC.md §4.6).
export function formatAmount(value: string | null): string {
  if (!value) return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return `${Math.round(number).toLocaleString("ru-RU")} ₸`;
}

export function formatPeriod(start: string | null, end: string | null): string {
  if (!start && !end) return "—";
  const fmt = (iso: string) => new Date(iso).toLocaleDateString("ru-RU", { month: "long", year: "numeric" });
  if (start && end) return `${fmt(start)} — ${fmt(end)}`;
  return fmt((start ?? end) as string);
}
