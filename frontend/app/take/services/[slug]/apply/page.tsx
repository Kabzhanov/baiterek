import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { ApplicationWizard } from "@/components/form-engine/application-wizard";

// The draft/checkpoint API is keyed by the mock `X-User-Id` (see lib/mock-user.ts), which
// only exists in the browser (localStorage) — so unlike the read-only catalog pages, the
// entire create/resume/render flow here runs client-side inside <ApplicationWizard>. This
// wrapper just supplies the slug from the route and the shared page chrome.
export default async function ApplyPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;

  return (
    <>
      <SiteHeader />
      <main id="main">
        <section className="section container">
          <p>
            <Link className="muted" href={`/take/services/${slug}`}>← К услуге</Link>
          </p>
          <ApplicationWizard slug={slug} />
        </section>
      </main>
    </>
  );
}
