"use client";
// AI-генератор услуги (SPEC.md §5.3, критерий 9.4): текст программы → POST generate →
// прогресс → редирект в конструктор с готовым draft. Warnings и degraded передаются
// редактору через sessionStorage (см. aiNoticeStorageKey), чтобы плашка «проверьте черновик»
// пережила переход между страницами. AI никогда не публикует сам — только draft.
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ApplicationApiError, BackendUnavailableError } from "@/lib/application-api";
import { definitionAdminApi } from "@/lib/definition-api";
import { aiNoticeStorageKey } from "./definition-editor-shell";
import type { GenerateOut } from "@/lib/definition-admin-types";

type Phase = "idle" | "generating" | "done" | "unavailable";

export function GenerateForm() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("idle");
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GenerateOut | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (text.trim().length < 50) {
      setError("Вставьте текст программы — минимум 50 символов, чтобы AI было с чем работать.");
      return;
    }
    setPhase("generating");
    try {
      const generated = await definitionAdminApi.generate(text);
      window.sessionStorage.setItem(
        aiNoticeStorageKey(generated.id),
        JSON.stringify({ warnings: generated.warnings, degraded: generated.degraded }),
      );
      if (generated.warnings.length === 0 && !generated.degraded) {
        // Чистый результат — сразу в конструктор дорабатывать draft.
        router.push(`/create/definitions/${generated.id}`);
        return;
      }
      setResult(generated);
      setPhase("done");
    } catch (err) {
      if (err instanceof BackendUnavailableError) {
        setPhase("unavailable");
        return;
      }
      setPhase("idle");
      setError(
        err instanceof ApplicationApiError
          ? `Генерация не удалась: ${err.message}`
          : "Генерация не удалась. Попробуйте ещё раз.",
      );
    }
  }

  if (phase === "unavailable") {
    return (
      <div className="form-card">
        <span className="pill">Технический сбой</span>
        <h2>Стенд временно недоступен</h2>
        <p className="muted">
          Не удалось связаться с сервером генерации. Это не имитация — создать услугу из документа
          сейчас нельзя. Попробуйте обновить страницу через минуту.
        </p>
        <button type="button" className="button" onClick={() => window.location.reload()}>
          Обновить страницу
        </button>
      </div>
    );
  }

  if (phase === "done" && result) {
    return (
      <div className="form-card">
        <span className="pill">Черновик готов</span>
        <h2>AI собрал черновик услуги</h2>
        {result.degraded && (
          <div className="mock" role="status">
            <strong>AI в демо-режиме</strong> — основной генератор временно недоступен, черновик
            собран запасным. Проверьте его особенно внимательно.
          </div>
        )}
        {result.warnings.length > 0 ? (
          <>
            <p className="muted">Замечания генератора — проверьте эти места в конструкторе:</p>
            <ul>
              {result.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </>
        ) : (
          <p className="muted">Замечаний нет — но публикация всё равно остаётся за вами.</p>
        )}
        <div className="actions">
          <Link className="button" href={`/create/definitions/${result.id}`}>
            Открыть в конструкторе
          </Link>
        </div>
      </div>
    );
  }

  return (
    <form className="form-card" onSubmit={handleSubmit} noValidate>
      <h2>Создать услугу из документа</h2>
      <p className="muted">
        Вставьте текст программы (описание условий, требований, документов) — AI разберёт его в
        черновик услуги. Черновик открывается в конструкторе: AI ничего не публикует сам.
      </p>
      <div className="field">
        <label htmlFor="generate-text">Текст программы</label>
        <textarea
          id="generate-text"
          rows={14}
          value={text}
          placeholder="Вставьте сюда текст документа с описанием программы поддержки…"
          disabled={phase === "generating"}
          onChange={(e) => setText(e.target.value)}
        />
        {error && <small role="alert">{error}</small>}
      </div>
      {phase === "generating" && (
        <p className="save-indicator" data-status="saving" role="status">
          Генерируем черновик услуги — обычно это занимает до минуты…
        </p>
      )}
      <div className="actions">
        <button className="button" disabled={phase === "generating"}>
          {phase === "generating" ? "Генерируем…" : "Сгенерировать черновик"}
        </button>
        <Link className="button secondary" href="/create">
          Отмена
        </Link>
      </div>
    </form>
  );
}
