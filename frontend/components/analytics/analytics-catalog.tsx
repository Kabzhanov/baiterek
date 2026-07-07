"use client";
// Модуль аналитической отчётности (SPEC.md §4.5): каталог с фильтром по организации и
// типу; карточка — описание/источник/период; открытие по ссылке или embedding (iframe
// для материалов с `embed_allowed=true`).
import { useEffect, useMemo, useState } from "react";
import { contentApi } from "@/lib/content-api";
import type { AnalyticsMaterial } from "@/lib/types";

const ALL = "Все";

const TYPE_LABELS: Record<string, string> = {
  dashboard: "Дашборд",
  report: "Отчёт",
  financial: "Финансовая отчётность",
  research: "Исследование",
};

export function AnalyticsCatalog() {
  const [materials, setMaterials] = useState<AnalyticsMaterial[] | null>(null);
  const [organization, setOrganization] = useState(ALL);
  const [type, setType] = useState(ALL);
  const [embeddedId, setEmbeddedId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const items = await contentApi.listAnalyticsMaterials();
      if (!cancelled) setMaterials(items);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const organizations = useMemo(
    () => [ALL, ...Array.from(new Set((materials ?? []).map((m) => m.organization))).sort()],
    [materials],
  );
  const types = useMemo(() => [ALL, ...Array.from(new Set((materials ?? []).map((m) => m.type)))], [materials]);

  const filtered = (materials ?? []).filter(
    (m) => (organization === ALL || m.organization === organization) && (type === ALL || m.type === type),
  );

  if (materials === null) return <p className="muted">Загрузка материалов…</p>;

  return (
    <div>
      <div className="filters" role="group" aria-label="Организация">
        {organizations.map((o) => (
          <button key={o} type="button" aria-pressed={organization === o} onClick={() => setOrganization(o)}>
            {o}
          </button>
        ))}
      </div>
      <div className="filters" role="group" aria-label="Тип материала">
        {types.map((t) => (
          <button key={t} type="button" aria-pressed={type === t} onClick={() => setType(t)}>
            {t === ALL ? ALL : (TYPE_LABELS[t] ?? t)}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <p className="muted">Ничего не найдено — попробуйте изменить фильтры.</p>
      ) : (
        <div className="grid">
          {filtered.map((material) => (
            <article key={material.id} className="card">
              <span className="pill">{TYPE_LABELS[material.type] ?? material.type}</span>
              <h3>{material.title}</h3>
              <p className="muted">{material.description}</p>
              <p className="muted">
                {material.source ?? "—"}
                {material.period ? ` · ${material.period}` : ""} · {material.organization}
              </p>
              <div className="actions">
                {material.url && (
                  <a className="button secondary" href={material.url} target="_blank" rel="noopener noreferrer">
                    Открыть по ссылке
                  </a>
                )}
                {material.embed_allowed && material.url && (
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() => setEmbeddedId(embeddedId === material.id ? null : material.id)}
                  >
                    {embeddedId === material.id ? "Скрыть" : "Показать здесь"}
                  </button>
                )}
              </div>
              {embeddedId === material.id && material.url && (
                <iframe
                  src={material.url}
                  title={material.title}
                  className="embed-frame"
                  loading="lazy"
                />
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
