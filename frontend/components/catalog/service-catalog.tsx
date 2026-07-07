"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import type { ServiceDefinition } from "@/lib/types";

const ALL = "Все";

export function ServiceCatalog({ services }: { services: ServiceDefinition[] }) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string>(ALL);
  const [org, setOrg] = useState<string>(ALL);
  const [audience, setAudience] = useState<string>(ALL);

  const categories = useMemo(() => [ALL, ...Array.from(new Set(services.map((s) => s.meta.category)))], [services]);
  const orgs = useMemo(() => [ALL, ...Array.from(new Set(services.map((s) => s.meta.org)))], [services]);

  const filtered = services.filter((s) => {
    const q = query.trim().toLowerCase();
    const matchesQuery = !q || s.meta.title.toLowerCase().includes(q) || s.meta.summary_plain.toLowerCase().includes(q);
    const matchesCategory = category === ALL || s.meta.category === category;
    const matchesOrg = org === ALL || s.meta.org === org;
    const matchesAudience = audience === ALL || s.meta.audience.includes(audience);
    return matchesQuery && matchesCategory && matchesOrg && matchesAudience;
  });

  return (
    <div>
      <input
        className="search"
        type="search"
        placeholder="Найти услугу по названию или описанию"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="Поиск услуг"
      />
      <div className="filters" role="group" aria-label="Направление">
        {categories.map((c) => (
          <button key={c} type="button" aria-pressed={category === c} onClick={() => setCategory(c)}>
            {c}
          </button>
        ))}
      </div>
      <div className="filters" role="group" aria-label="Организация">
        {orgs.map((o) => (
          <button key={o} type="button" aria-pressed={org === o} onClick={() => setOrg(o)}>
            {o}
          </button>
        ))}
      </div>
      <div className="filters" role="group" aria-label="Аудитория">
        {[ALL, "ЮЛ", "ИП"].map((a) => (
          <button key={a} type="button" aria-pressed={audience === a} onClick={() => setAudience(a)}>
            {a}
          </button>
        ))}
      </div>
      {filtered.length === 0 ? (
        <p className="muted">Ничего не найдено — попробуйте изменить запрос или фильтры.</p>
      ) : (
        <div className="grid">
          {filtered.map((s) => (
            <article className="card" key={s.id}>
              <span className="pill">{s.meta.org}</span>
              <h3>{s.meta.title}</h3>
              <p className="muted">{s.meta.summary_plain}</p>
              <p>
                <small>{s.meta.audience} · срок рассмотрения {s.meta.sla_days} дн.</small>
              </p>
              <Link className="button secondary" href={`/take/services/${s.slug}`}>
                Подробнее
              </Link>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
