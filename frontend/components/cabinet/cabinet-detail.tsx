"use client";
// Детальная страница заявки в личном кабинете (SPEC.md §4.4): таймлайн статусов,
// уведомления, блок «Что дальше». Документы придут пустым списком, пока файловый
// контур не реализован — секцию честно подписываем, а не прячем.
import { useEffect, useState } from "react";
import Link from "next/link";
import { ApplicationApiError, applicationApi } from "@/lib/application-api";
import { stageJustOpened } from "@/lib/stage-progress";
import { nextSteps, statusLabel } from "@/lib/status-labels";
import type { CabinetApplicationDetail } from "@/lib/application-types";
import { formatCabinetDate } from "./cabinet-list";
import { StageOpenBanner } from "./stage-open-banner";

type Phase = "loading" | "unavailable" | "not_found" | "ready";

function formatMoment(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" })}, ${date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}`;
}

export function CabinetDetail({ applicationId }: { applicationId: string }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [detail, setDetail] = useState<CabinetApplicationDetail | null>(null);
  // Многоэтапность (SPEC.md §4.3, требование 3) — см. cabinet-list.tsx для того же приёма:
  // `CabinetApplicationDetail` не несёт completed_stages/stage_open, поэтому для одной
  // конкретной заявки (уже открытой) дёргаем resume() лишний раз, только когда она не черновик.
  const [stageOpenInfo, setStageOpenInfo] = useState<{ completedStages: string[]; stageOpen: boolean } | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await applicationApi.getApplication(applicationId);
        if (cancelled) return;
        setDetail(result);
        setPhase("ready");
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApplicationApiError && err.status === 404) {
          setPhase("not_found");
          return;
        }
        setPhase("unavailable");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applicationId]);

  useEffect(() => {
    if (phase !== "ready" || !detail || detail.status === "draft") return;
    let cancelled = false;
    (async () => {
      try {
        const resumed = await applicationApi.resume(applicationId);
        if (!cancelled) setStageOpenInfo({ completedStages: resumed.completed_stages, stageOpen: resumed.stage_open });
      } catch {
        // Не критично — просто не покажем баннер, ничего не ломаем.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [phase, detail, applicationId]);

  if (phase === "loading") {
    return <p className="muted">Загружаем заявку…</p>;
  }

  if (phase === "not_found") {
    return (
      <div className="form-card">
        <h2>Заявка не найдена</h2>
        <p className="muted">Возможно, ссылка устарела или заявка принадлежит другому пользователю.</p>
        <Link className="button secondary" href="/take/cabinet">
          К списку заявок
        </Link>
      </div>
    );
  }

  if (phase === "unavailable" || !detail) {
    return (
      <div className="form-card">
        <span className="pill">Технический сбой</span>
        <h2>Стенд временно недоступен</h2>
        <p className="muted">Не удалось получить заявку. Попробуйте обновить страницу через минуту.</p>
        <button type="button" className="button" onClick={() => window.location.reload()}>
          Обновить страницу
        </button>
      </div>
    );
  }

  // Таймлайн начинаем с создания черновика — сам `timeline` на сервере хранит только
  // переходы статусов (первый появляется при отправке).
  const timeline = [
    { key: "created", label: "Черновик создан", at: detail.created_at },
    ...detail.timeline.map((entry, i) => ({
      key: `${entry.status}-${i}`,
      label: statusLabel(entry.status, detail.labels_plain),
      at: entry.at,
    })),
  ];

  return (
    <>
      <span className="pill">{statusLabel(detail.status, detail.labels_plain)}</span>
      <h1>{detail.service.title}</h1>
      <p className="muted">
        {detail.number ? `Заявка № ${detail.number}` : `Черновик заполнен на ${detail.progress_percent}%`}
        {" · обновлена "}
        {formatCabinetDate(detail.updated_at)}
      </p>
      {detail.status === "draft" && (
        <p>
          <Link className="button" href={`/take/services/${detail.service.slug}/apply`}>
            Продолжить заполнение
          </Link>
        </p>
      )}

      {stageOpenInfo && stageJustOpened(stageOpenInfo.completedStages, stageOpenInfo.stageOpen) && (
        <StageOpenBanner slug={detail.service.slug} applicationId={detail.id} />
      )}

      <div className="form-card">
        <h2>История заявки</h2>
        <ol className="steps">
          {timeline.map((entry) => (
            <li key={entry.key}>
              <strong>{entry.label}</strong>
              <span className="muted"> — {formatMoment(entry.at)}</span>
            </li>
          ))}
        </ol>
      </div>

      <div className="form-card">
        <h2>Что дальше</h2>
        <ol className="steps">
          {nextSteps(detail.status).map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ol>
      </div>

      <div className="form-card">
        <h2>Уведомления</h2>
        {detail.notifications.length === 0 ? (
          <p className="muted">Уведомлений пока нет. Когда организация что-то запросит, это появится здесь.</p>
        ) : (
          <ul className="steps">
            {detail.notifications.map((notification) => (
              <li key={notification.id}>
                <strong>{notification.title}</strong>
                <span className="muted"> — {formatMoment(notification.created_at)}</span>
                <p>{notification.body}</p>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="form-card">
        <h2>Документы</h2>
        <p className="muted">
          {detail.documents.length === 0
            ? "Документов пока нет. Загрузка и дозагрузка файлов появятся на следующем этапе."
            : `Документов: ${detail.documents.length}`}
        </p>
      </div>

      <p>
        <Link className="muted" href="/take/cabinet">
          ← К списку заявок
        </Link>
      </p>
    </>
  );
}
