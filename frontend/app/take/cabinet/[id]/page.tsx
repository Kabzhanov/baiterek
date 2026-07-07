import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { CabinetDetail } from "@/components/cabinet/cabinet-detail";

// Детальная страница заявки (SPEC.md §4.4): таймлайн, «что дальше», уведомления.
// Загрузка — в клиентском <CabinetDetail> (X-User-Id живёт в браузере).
export default async function CabinetApplicationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <>
      <SiteHeader />
      <main id="main">
        <section className="section container">
          <p>
            <Link className="muted" href="/take/cabinet">← Личный кабинет</Link>
          </p>
          <CabinetDetail applicationId={id} />
        </section>
      </main>
    </>
  );
}
