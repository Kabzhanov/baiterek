"use client";
// Интерактивная карта проектов (SPEC.md §4.6): маркеры + фильтры (организация, регион,
// отрасль, статус) + панель-сводка (всего/сумма/по регионам, мини-бар-чарт) + карточка
// проекта по клику + бейдж «демонстрационные данные».
import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { contentApi } from "@/lib/content-api";
import { formatAmount, formatPeriod } from "@/lib/map-format";
import type { MapProject, MapSummary } from "@/lib/types";

// Leaflet touches `window`/`document` at import time — dynamic import with `ssr: false`
// is the only way this doesn't crash `next build`'s server-side prerender pass.
const ProjectMap = dynamic(() => import("./project-map").then((m) => m.ProjectMap), {
  ssr: false,
  loading: () => (
    <div className="map-canvas map-canvas-loading" aria-hidden>
      Загрузка карты…
    </div>
  ),
});

const ALL = "Все";

export function MapExplorer() {
  const [projects, setProjects] = useState<MapProject[] | null>(null);
  const [summary, setSummary] = useState<MapSummary | null>(null);
  const [selected, setSelected] = useState<MapProject | null>(null);

  const [organization, setOrganization] = useState(ALL);
  const [region, setRegion] = useState(ALL);
  const [industry, setIndustry] = useState(ALL);
  const [status, setStatus] = useState(ALL);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [items, totals] = await Promise.all([contentApi.listMapProjects(), contentApi.getMapSummary()]);
      if (cancelled) return;
      setProjects(items);
      setSummary(totals);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const organizations = useMemo(
    () => [ALL, ...Array.from(new Set((projects ?? []).map((p) => p.organization))).sort()],
    [projects],
  );
  const regions = useMemo(
    () => [ALL, ...Array.from(new Set((projects ?? []).map((p) => p.region_code))).sort()],
    [projects],
  );
  const industries = useMemo(
    () => [ALL, ...Array.from(new Set((projects ?? []).map((p) => p.industry).filter(Boolean) as string[]))].sort(),
    [projects],
  );
  const statuses = useMemo(
    () => [ALL, ...Array.from(new Set((projects ?? []).map((p) => p.status)))].sort(),
    [projects],
  );

  const filtered = (projects ?? []).filter((p) => {
    return (
      (organization === ALL || p.organization === organization) &&
      (region === ALL || p.region_code === region) &&
      (industry === ALL || p.industry === industry) &&
      (status === ALL || p.status === status)
    );
  });

  const maxRegionCount = Math.max(1, ...(summary?.by_region.map((r) => r.count) ?? [1]));

  return (
    <div>
      <span className="pill" role="note">
        Демонстрационные данные — синтетические проекты для стенда
      </span>

      <div className="filters" role="group" aria-label="Организация">
        {organizations.map((o) => (
          <button key={o} type="button" aria-pressed={organization === o} onClick={() => setOrganization(o)}>
            {o}
          </button>
        ))}
      </div>
      <div className="filters" role="group" aria-label="Регион">
        {regions.map((r) => (
          <button key={r} type="button" aria-pressed={region === r} onClick={() => setRegion(r)}>
            {r}
          </button>
        ))}
      </div>
      <div className="filters" role="group" aria-label="Отрасль">
        {industries.map((i) => (
          <button key={i} type="button" aria-pressed={industry === i} onClick={() => setIndustry(i)}>
            {i}
          </button>
        ))}
      </div>
      <div className="filters" role="group" aria-label="Статус">
        {statuses.map((s) => (
          <button key={s} type="button" aria-pressed={status === s} onClick={() => setStatus(s)}>
            {s}
          </button>
        ))}
      </div>

      <div className="map-shell">
        <div>
          {projects === null ? (
            <p className="muted">Загрузка проектов…</p>
          ) : (
            <ProjectMap projects={filtered} onSelect={setSelected} />
          )}
          <p className="muted">Показано проектов: {filtered.length} из {projects?.length ?? 0}</p>
        </div>

        <aside className="card">
          <h2>Сводка</h2>
          {summary ? (
            <>
              <p>
                Всего проектов: <strong>{summary.total_count}</strong>
                <br />
                Общая сумма: <strong>{formatAmount(summary.total_amount)}</strong>
              </p>
              <ul className="region-bars">
                {summary.by_region.slice(0, 10).map((r) => (
                  <li key={r.region_code}>
                    <span>{r.region_code}</span>
                    <span className="region-bar-track">
                      <span
                        className="region-bar-fill"
                        style={{ width: `${(r.count / maxRegionCount) * 100}%` }}
                      />
                    </span>
                    <span>{r.count}</span>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="muted">Загрузка сводки…</p>
          )}

          <h2>Карточка проекта</h2>
          {selected ? (
            <dl className="project-card">
              <dt>Наименование</dt>
              <dd>{selected.name}</dd>
              <dt>Организация</dt>
              <dd>{selected.organization}</dd>
              <dt>Регион</dt>
              <dd>
                {selected.region_code}
                {selected.locality ? `, ${selected.locality}` : ""}
              </dd>
              <dt>Отрасль</dt>
              <dd>{selected.industry ?? "—"}</dd>
              <dt>Сумма</dt>
              <dd>{formatAmount(selected.amount)}</dd>
              <dt>Период</dt>
              <dd>{formatPeriod(selected.period_start, selected.period_end)}</dd>
              <dt>Статус</dt>
              <dd>{selected.status}</dd>
              <dt>Описание</dt>
              <dd>{selected.description ?? "—"}</dd>
            </dl>
          ) : (
            <p className="muted">Нажмите на маркер, чтобы увидеть карточку проекта.</p>
          )}
        </aside>
      </div>
    </div>
  );
}
