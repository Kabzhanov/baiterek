"use client";
// Шапка сайта: на десктопе — обычное горизонтальное меню (как раньше); на ширине ≤768px
// (см. `@media(max-width:768px)` в globals.css) — гамбургер-кнопка, по тапу выезжает панель
// со всеми разделами. `.nav` рендерится один раз и переиспользуется для обоих режимов: на
// десктопе media-запрос его не трогает (всегда `display:flex`), на мобиле по умолчанию
// `display:none` и появляется только при `data-open="true"` — то же самое, что и убирает
// панель из tab-порядка при закрытии, без ручного управления `inert`/`tabIndex`.
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

const NAV_LINKS = [
  { href: "/take", label: "Получить услугу" },
  { href: "/take/map", label: "Карта проектов" },
  { href: "/take/analytics", label: "Аналитика" },
  { href: "/take/tools", label: "Инструменты" },
  { href: "/take/cabinet", label: "Личный кабинет" },
  { href: "/create", label: "Конструктор" },
];

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function handleKeydown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        toggleRef.current?.focus();
      }
    }
    document.addEventListener("keydown", handleKeydown);
    return () => document.removeEventListener("keydown", handleKeydown);
  }, [open]);

  function close() {
    setOpen(false);
  }

  return (
    <header className="header">
      <div className="container header-inner">
        <Link className="brand" href="/take">
          Байтерек
        </Link>
        <button
          type="button"
          className="nav-toggle"
          aria-expanded={open}
          aria-controls="site-nav"
          aria-label={open ? "Закрыть меню" : "Открыть меню"}
          onClick={() => setOpen((v) => !v)}
          ref={toggleRef}
        >
          <span aria-hidden>{open ? "✕" : "☰"}</span>
        </button>
        <nav id="site-nav" className="nav" data-open={open} aria-label="Основная навигация">
          {NAV_LINKS.map((link) => (
            <Link key={link.href} href={link.href} onClick={close}>
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="nav-overlay" data-open={open} aria-hidden onClick={close} />
      </div>
    </header>
  );
}
