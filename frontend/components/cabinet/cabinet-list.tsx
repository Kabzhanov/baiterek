"use client";
// Личный кабинет, список заявок (SPEC.md §4.4, "Обязательное расширение" §2):
// черновики — первым блоком с «заполнена на N% — Продолжить» (кнопка ведёт в мастер,
// который через идемпотентный create-or-resume вернёт ровно сохранённый экран),
// ниже — отправленные заявки со статус-бейджем понятным языком. Данные ходят через
// applicationApi (X-User-Id живёт в браузере — поэтому компонент клиентский, как и мастер).
import { useEffect, useState } from "react";
import Link from "next/link";
import { applicationApi } from "@/lib/application-api";
import { stageJustOpened } from "@/lib/stage-progress";
import { statusLabel } from "@/lib/status-labels";
import type { CabinetApplicationItem } from "@/lib/application-types";
import { StageOpenBanner } from "./stage-open-banner";

type Phase = "loading" | "unavailable" | "ready";
type StageInfo = { completedStages: string[]; stageOpen: boolean };

export function formatCabinetDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
}

export function CabinetList() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [items, setItems] = useState<CabinetApplicationItem[]>([]);
  // Многоэтапность (SPEC.md §4.3, требование 3): `CabinetApplicationItem` из
  // GET /applications не несёт `completed_stages`/`stage_open` (тот контракт — только у
  // GET /applications/{id}/resume). Единственный честный способ узнать, открылся ли
  // следующий этап, не трогая бэк, — дёрнуть resume() по каждой неотправленной... то есть
  // не-черновой заявке (resume() работает для любого статуса, только владелец). На
  // MVP-стенде заявок немного, так что N доп. запросов не проблема.
  const [stageInfo, setStageInfo] = useState<Record<string, StageInfo>>({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await applicationApi.listApplications();
        if (cancelled) return;
        setItems(result.items);
        setPhase("ready");
      } catch {
        if (!cancelled) setPhase("unavailable");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (phase !== "ready") return;
    const targets = items.filter((item) => item.status !== "draft");
    if (targets.length === 0) return;
    let cancelled = false;
    (async () => {
      const entries = await Promise.all(
        targets.map(async (item): Promise<[string, StageInfo] | null> => {
          try {
            const resumed = await applicationApi.resume(item.id);
            return [item.id, { completedStages: resumed.completed_stages, stageOpen: resumed.stage_open }];
          } catch {
            return null;
          }
        }),
      );
      if (cancelled) return;
      setStageInfo((prev) => {
        const next = { ...prev };
        for (const entry of entries) if (entry) next[entry[0]] = entry[1];
        return next;
      });
    })();
    return () => {
      cancelled = true;
    };
    // `items` меняется только один раз за загрузку (см. эффект выше), поэтому лишних
    // повторных resume() при каждом рендере не будет.
  }, [phase, items]);

  if (phase === "loading") {
    return <p className="muted">Загружаем ваши заявки…</p>;
  }

  if (phase === "unavailable") {
    return (
      <div className="form-card">
        <span className="pill">Технический сбой</span>
        <h2>Стенд временно недоступен</h2>
        <p className="muted">
          Не удалось получить список заявок. Ваши данные не потерялись — попробуйте обновить страницу через минуту.
        </p>
        <button type="button" className="button" onClick={() => window.location.reload()}>
          Обновить страницу
        </button>
      </div>
    );
  }

  const drafts = items.filter((item) => item.status === "draft");
  const submitted = items.filter((item) => item.status !== "draft");

  if (items.length === 0) {
    return (
      <div className="form-card">
        <h2>Заявок пока нет</h2>
        <p className="muted">Выберите услугу в каталоге — черновик сохраняется сам, начать можно в любой момент.</p>
        <Link className="button" href="/take">
          К каталогу услуг
        </Link>
      </div>
    );
  }

  return (
    <>
      {drafts.length > 0 && (
        <>
          <h2>Черновики</h2>
          <p className="muted">Всё введённое уже сохранено — продолжите с того экрана, где остановились.</p>
          <div className="grid">
            {drafts.map((item) => (
              <article className="card" key={item.id}>
                <span className="pill">{statusLabel(item.status, item.labels_plain)}</span>
                <h3>
                  Заявка «{item.service.title}» заполнена на {item.progress_percent}%
                </h3>
                <p className="muted">Изменена {formatCabinetDate(item.updated_at)}</p>
                <div className="actions">
                  <Link className="button" href={`/take/services/${item.service.slug}/apply`}>
                    Продолжить
                  </Link>
                  <Link className="button secondary" href={`/take/cabinet/${item.id}`}>
                    Подробнее
                  </Link>
                </div>
              </article>
            ))}
          </div>
        </>
      )}

      {submitted.length > 0 && (
        <>
          <h2>Отправленные заявки</h2>
          <div className="grid">
            {submitted.map((item) => {
              const info = stageInfo[item.id];
              const showStageBanner = !!info && stageJustOpened(info.completedStages, info.stageOpen);
              return (
                <article className="card" key={item.id}>
                  <span className="pill">{statusLabel(item.status, item.labels_plain)}</span>
                  <h3>{item.service.title}</h3>
                  <p className="muted">
                    {item.number ? `№ ${item.number} · ` : ""}
                    {formatCabinetDate(item.updated_at)}
                  </p>
                  {showStageBanner && <StageOpenBanner slug={item.service.slug} applicationId={item.id} />}
                  <Link className="button secondary" href={`/take/cabinet/${item.id}`}>
                    Открыть заявку
                  </Link>
                </article>
              );
            })}
          </div>
        </>
      )}
    </>
  );
}
