"use client";
// Инструменты и материалы (SPEC.md §4.7): категории — база знаний · шаблоны документов ·
// чек-листы · калькуляторы · обзоры.
import { useEffect, useMemo, useState } from "react";
import { contentApi } from "@/lib/content-api";
import type { KnowledgeItem } from "@/lib/types";

const ALL = "Все";

const CATEGORY_LABELS: Record<string, string> = {
  guide: "База знаний",
  template: "Шаблоны документов",
  checklist: "Чек-листы",
  calculator: "Калькуляторы",
  review: "Обзоры",
};

export function KnowledgeCatalog() {
  const [items, setItems] = useState<KnowledgeItem[] | null>(null);
  const [category, setCategory] = useState(ALL);
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await contentApi.listKnowledgeItems();
      if (!cancelled) setItems(result);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const categories = useMemo(() => [ALL, ...Array.from(new Set((items ?? []).map((i) => i.category)))], [items]);
  const filtered = (items ?? []).filter((i) => category === ALL || i.category === category);

  if (items === null) return <p className="muted">Загрузка материалов…</p>;

  return (
    <div>
      <div className="filters" role="group" aria-label="Категория">
        {categories.map((c) => (
          <button key={c} type="button" aria-pressed={category === c} onClick={() => setCategory(c)}>
            {c === ALL ? ALL : (CATEGORY_LABELS[c] ?? c)}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <p className="muted">Ничего не найдено — попробуйте изменить фильтр.</p>
      ) : (
        <div className="grid">
          {filtered.map((item) => (
            <article key={item.id} className="card">
              <span className="pill">{CATEGORY_LABELS[item.category] ?? item.category}</span>
              <h3>{item.title}</h3>
              <p className="muted">{item.description}</p>
              {openId === item.id && item.content && <p>{item.content}</p>}
              <div className="actions">
                {item.content && (
                  <button type="button" className="button secondary" onClick={() => setOpenId(openId === item.id ? null : item.id)}>
                    {openId === item.id ? "Свернуть" : "Читать"}
                  </button>
                )}
                {item.url && (
                  <a className="button secondary" href={item.url}>
                    Открыть
                  </a>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
