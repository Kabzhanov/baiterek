import { SiteHeader } from "@/components/site-header";
import { AnalyticsCatalog } from "@/components/analytics/analytics-catalog";

// Модуль аналитической отчётности (SPEC.md §4.5).
export default function AnalyticsPage() {
  return (
    <>
      <SiteHeader />
      <main id="main">
        <section className="section container">
          <h1>Аналитика и отчётность</h1>
          <p className="lead">
            Годовые отчёты Холдинга и материалы дочерних организаций: описание, источник, период актуальности.
          </p>
          <AnalyticsCatalog />
        </section>
      </main>
    </>
  );
}
