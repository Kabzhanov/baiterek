import Link from "next/link";
import { notFound } from "next/navigation";
import { ServiceExplainCard } from "@/components/form-engine/service-explain-card";
import { SiteHeader } from "@/components/site-header";
import { portalApi } from "@/lib/api";

export default async function ServiceDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const services = await portalApi.listServiceDefinitions();
  const service = services.find((item) => item.slug === slug);
  if (!service) notFound();
  const { meta } = service;

  return (
    <>
      <SiteHeader />
      <main id="main">
        <section className="section container">
          <p>
            <Link className="muted" href="/take">← Все услуги</Link>
          </p>
          <span className="pill">{meta.org}</span>
          <h1>{meta.title}</h1>
          <p className="lead">{meta.summary_plain}</p>
          <div className="form-shell">
            <div>
              <h2>Условия</h2>
              <table className="table">
                <tbody>
                  {meta.conditions.map((c) => (
                    <tr key={c.label}>
                      <th>{c.label}</th>
                      <td>{c.value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h2>Что понадобится</h2>
              <ul className="steps">
                {meta.documents_checklist.map((doc) => (
                  <li key={doc}>{doc}</li>
                ))}
              </ul>

              <h2>Результат</h2>
              <p className="muted">{meta.result}</p>
              <p>
                <small>Срок рассмотрения — {meta.sla_days} дней.</small>
              </p>

              <div className="actions">
                <Link className="button" href={`/take/services/${slug}/apply`}>Подать заявку</Link>
              </div>
            </div>

            <ServiceExplainCard slug={slug} />
          </div>
        </section>
      </main>
    </>
  );
}
