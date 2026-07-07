import { SiteHeader } from "@/components/site-header";
import { DynamicForm } from "@/components/form-engine/dynamic-form";
import { ServiceCatalog } from "@/components/catalog/service-catalog";
import { intakeFields } from "@/lib/mock-data";
import { portalApi } from "@/lib/api";

export default async function Take() {
  const catalog = await portalApi.listServiceDefinitions();
  return (
    <>
      <SiteHeader />
      <main id="main">
        <section className="hero">
          <div className="container">
            <span className="pill">Единая платформа поддержки</span>
            <h1>Возможности для роста вашего бизнеса</h1>
            <p className="lead">Подберите программу поддержки и подайте заявку в одном понятном процессе.</p>
            <div className="actions">
              <a className="button" href="#intake">Подобрать услугу</a>
              <a className="button secondary" href="#catalog">Смотреть каталог</a>
            </div>
          </div>
        </section>
        <section className="section container" id="catalog">
          <h2>Каталог услуг</h2>
          <p className="muted">Найдите услугу по названию, направлению, организации или тому, кому она подходит — ЮЛ или ИП.</p>
          <ServiceCatalog services={catalog} />
        </section>
        <section className="section" id="intake" style={{ background: "var(--wash)" }}>
          <div className="container form-shell">
            <DynamicForm fields={intakeFields} />
            <aside className="card">
              <h2>Как это работает</h2>
              <ol className="steps">
                <li>Ответьте на несколько вопросов</li>
                <li>Получите рекомендации</li>
                <li>Заполните заявку</li>
                <li>Отслеживайте статус</li>
              </ol>
            </aside>
          </div>
        </section>
      </main>
    </>
  );
}
