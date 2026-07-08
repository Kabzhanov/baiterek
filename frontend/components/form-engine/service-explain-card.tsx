"use client";
// «Объяснить простыми словами» (SPEC.md §7.1, AI-критерий 9.4) — карточка услуги.
// Отдельный client-компонент: сама страница услуги — server component (см.
// app/take/services/[slug]/page.tsx), а этому блоку нужна интерактивность кнопки.
import { useState } from "react";
import { applicationApi } from "@/lib/application-api";
import { degradedNote } from "@/lib/copilot";

type State =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; text: string; degraded: boolean }
  | { status: "error" };

export function ServiceExplainCard({ slug }: { slug: string }) {
  const [state, setState] = useState<State>({ status: "idle" });

  async function handleExplain() {
    setState({ status: "loading" });
    try {
      const result = await applicationApi.explainService(slug);
      setState({ status: "success", text: result.text, degraded: result.degraded });
    } catch {
      // Мягкая деградация (SPEC item 7): это второстепенная AI-подсказка, а не сама
      // подача заявки — недоступность бэка здесь не пугает пользователя техническим
      // сбоем, а честно сообщает и предлагает попробовать снова.
      setState({ status: "error" });
    }
  }

  return (
    <aside className="card">
      <span className="pill">AI</span>
      <h2>Объяснить простыми словами</h2>
      <p className="muted">Пересказ условий без канцелярита и подсказка, что понадобится для заявки.</p>

      {state.status === "success" ? (
        <>
          <p>{state.text}</p>
          {state.degraded && (
            <p className="muted">
              <small>{degradedNote("explain")}</small>
            </p>
          )}
          <div className="mock" role="note">
            Ответ сформирован ИИ автоматически и может быть неточным — уточняйте условия в разделе «Условия» выше
            или у организации.
          </div>
        </>
      ) : state.status === "error" ? (
        <>
          <p className="muted">Не удалось получить объяснение — попробуйте ещё раз позже.</p>
          <button className="button secondary" type="button" onClick={handleExplain}>
            Повторить
          </button>
        </>
      ) : (
        <button
          className="button secondary"
          type="button"
          onClick={handleExplain}
          disabled={state.status === "loading"}
        >
          {state.status === "loading" ? "Готовим объяснение…" : "Объяснить простыми словами"}
        </button>
      )}
    </aside>
  );
}
