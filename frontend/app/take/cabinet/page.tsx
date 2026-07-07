import { SiteHeader } from "@/components/site-header";
import { CabinetList } from "@/components/cabinet/cabinet-list";

// Личный кабинет (SPEC.md §4.4). Как и мастер заявки, список ходит в API с браузерным
// X-User-Id (см. lib/mock-user.ts), поэтому вся загрузка живёт в клиентском <CabinetList>,
// а эта обёртка даёт только маршрут и общий каркас страницы.
export default function CabinetPage() {
  return (
    <>
      <SiteHeader />
      <main id="main">
        <section className="section container">
          <h1>Личный кабинет</h1>
          <p className="lead">Черновики, отправленные заявки и их статусы — всё в одном месте.</p>
          <CabinetList />
        </section>
      </main>
    </>
  );
}
