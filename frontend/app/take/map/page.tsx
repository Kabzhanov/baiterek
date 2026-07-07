import { SiteHeader } from "@/components/site-header";
import { MapExplorer } from "@/components/map/map-explorer";

// Интерактивная карта проектов (SPEC.md §4.6). Как и карта сама по себе, вся загрузка
// данных живёт в клиентском <MapExplorer> — эта обёртка даёт только маршрут и каркас.
export default function MapPage() {
  return (
    <>
      <SiteHeader />
      <main id="main">
        <section className="section container">
          <h1>Карта проектов</h1>
          <p className="lead">Проекты, реализуемые при поддержке организаций Холдинга «Байтерек», на карте Казахстана.</p>
          <MapExplorer />
        </section>
      </main>
    </>
  );
}
