"use client";
// Реестр Definitions (SPEC.md §5.1, критерий 9.2): таблица со статусом/версией/slug/датой,
// действия «редактировать / дублировать / экспорт JSON», создание пустой услуги и переход
// в AI-генератор. Без mock-фолбэка: недоступный бэкенд честно показывает «стенд недоступен»
// (тот же паттерн, что application-wizard.tsx).
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApplicationApiError, BackendUnavailableError } from "@/lib/application-api";
import { definitionAdminApi, downloadJson } from "@/lib/definition-api";
import { createEmptyDefinition } from "@/lib/definition-editor";
import type { DefinitionListItem, DefinitionStatus } from "@/lib/definition-admin-types";

const STATUS_LABELS: Record<DefinitionStatus, string> = {
  draft: "Черновик",
  published: "Опубликована",
  archived: "В архиве",
};

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

type Phase = "loading" | "unavailable" | "ready";

/** Группирует строки реестра по service_id и оставляет в каждой группе только
 * запись с максимальным version (задача: по умолчанию не дублировать v1+v2
 * published одной и той же услуги — визуальный шум в таблице). */
function latestPerService(items: DefinitionListItem[]): DefinitionListItem[] {
  const latest = new Map<string, DefinitionListItem>();
  for (const item of items) {
    const current = latest.get(item.service_id);
    if (!current || item.version > current.version) {
      latest.set(item.service_id, item);
    }
  }
  return Array.from(latest.values());
}

export function DefinitionsRegistry() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("loading");
  const [items, setItems] = useState<DefinitionListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [showAllVersions, setShowAllVersions] = useState(false);

  const load = useCallback(async () => {
    try {
      const list = await definitionAdminApi.list();
      setItems(list);
      setPhase("ready");
    } catch {
      setPhase("unavailable");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function describeError(err: unknown): string {
    if (err instanceof BackendUnavailableError) return "Стенд временно недоступен — действие не выполнено.";
    if (err instanceof ApplicationApiError) return err.message;
    return "Не удалось выполнить действие.";
  }

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    setCreateError(null);
    const title = newTitle.trim();
    const slug = newSlug.trim();
    if (!title) {
      setCreateError("Укажите название услуги");
      return;
    }
    if (!/^[a-z0-9][a-z0-9-]*$/.test(slug)) {
      setCreateError("Slug — латиница в нижнем регистре, цифры и дефисы (например: sme-loan)");
      return;
    }
    setBusyId("create");
    try {
      const created = await definitionAdminApi.create(slug, createEmptyDefinition(title));
      router.push(`/create/definitions/${created.id}`);
    } catch (err) {
      setCreateError(describeError(err));
    } finally {
      setBusyId(null);
    }
  }

  async function handleDuplicate(item: DefinitionListItem) {
    setError(null);
    setBusyId(item.id);
    try {
      const copy = await definitionAdminApi.duplicate(item.id);
      router.push(`/create/definitions/${copy.id}`);
    } catch (err) {
      setError(describeError(err));
      setBusyId(null);
    }
  }

  async function handleExport(item: DefinitionListItem) {
    setError(null);
    setBusyId(item.id);
    try {
      const payload = await definitionAdminApi.exportJson(item.id);
      downloadJson(payload, `${item.slug}-v${item.version}.json`);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusyId(null);
    }
  }

  if (phase === "loading") {
    return (
      <div className="form-card">
        <p className="muted">Загружаем реестр услуг…</p>
      </div>
    );
  }

  if (phase === "unavailable") {
    return (
      <div className="form-card">
        <span className="pill">Технический сбой</span>
        <h2>Стенд временно недоступен</h2>
        <p className="muted">
          Не удалось связаться с сервером конструктора. Это не имитация — реестр услуг сейчас
          недоступен. Попробуйте обновить страницу через минуту.
        </p>
        <button type="button" className="button" onClick={() => window.location.reload()}>
          Обновить страницу
        </button>
      </div>
    );
  }

  const visibleItems = showAllVersions ? items : latestPerService(items);
  const hiddenCount = items.length - visibleItems.length;

  return (
    <div>
      <div className="actions" style={{ marginBottom: 16 }}>
        <button type="button" className="button" onClick={() => setCreating((v) => !v)}>
          Создать услугу
        </button>
        <Link className="button secondary" href="/create/generate">
          Создать из документа (AI)
        </Link>
      </div>

      {hiddenCount > 0 && (
        <p className="muted" style={{ marginBottom: 16 }}>
          Показана последняя версия каждой услуги ({hiddenCount}{" "}
          {hiddenCount === 1 ? "старая версия скрыта" : "старых версий скрыто"}).{" "}
          <button
            type="button"
            className="button secondary"
            style={{ marginLeft: 8 }}
            onClick={() => setShowAllVersions(true)}
          >
            Показать все версии
          </button>
        </p>
      )}
      {showAllVersions && (
        <p className="muted" style={{ marginBottom: 16 }}>
          Показаны все версии.{" "}
          <button
            type="button"
            className="button secondary"
            style={{ marginLeft: 8 }}
            onClick={() => setShowAllVersions(false)}
          >
            Только последние версии
          </button>
        </p>
      )}

      {creating && (
        <form className="form-card" onSubmit={handleCreate} noValidate style={{ marginBottom: 16 }}>
          <h2>Новая услуга</h2>
          <div className="field">
            <label htmlFor="new-title">Название услуги</label>
            <input id="new-title" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="Например: Льготное финансирование МСБ" />
          </div>
          <div className="field">
            <label htmlFor="new-slug">Slug (адрес в каталоге)</label>
            <input id="new-slug" value={newSlug} onChange={(e) => setNewSlug(e.target.value)} placeholder="sme-loan" />
          </div>
          {createError && <small role="alert">{createError}</small>}
          <div className="actions">
            <button className="button" disabled={busyId === "create"}>
              {busyId === "create" ? "Создаём…" : "Создать черновик"}
            </button>
          </div>
        </form>
      )}

      {error && (
        <div className="mock" role="alert">
          {error}
        </div>
      )}

      {items.length === 0 ? (
        <div className="form-card">
          <p className="muted">В реестре пока нет услуг. Создайте первую — вручную или из документа через AI.</p>
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Название</th>
              <th>Slug</th>
              <th>Статус</th>
              <th>Версия</th>
              <th>Обновлена</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {visibleItems.map((item) => (
              <tr key={item.id}>
                <td>{item.title}</td>
                <td>{item.slug}</td>
                <td>
                  <span className="pill" data-status={item.status}>
                    {STATUS_LABELS[item.status] ?? item.status}
                  </span>
                </td>
                <td>v{item.version}</td>
                <td>{formatDate(item.updated_at)}</td>
                <td>
                  <div className="actions">
                    <Link className="button secondary" href={`/create/definitions/${item.id}`}>
                      Редактировать
                    </Link>
                    <button
                      type="button"
                      className="button secondary"
                      disabled={busyId === item.id}
                      onClick={() => void handleDuplicate(item)}
                    >
                      Дублировать
                    </button>
                    <button
                      type="button"
                      className="button secondary"
                      disabled={busyId === item.id}
                      onClick={() => void handleExport(item)}
                    >
                      Экспорт JSON
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
