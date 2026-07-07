import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { ApplicationWizard } from "@/components/form-engine/application-wizard";

// The draft/checkpoint API is keyed by the mock `X-User-Id` (see lib/mock-user.ts), which
// only exists in the browser (localStorage) — so unlike the read-only catalog pages, the
// entire create/resume/render flow here runs client-side inside <ApplicationWizard>. This
// wrapper just supplies the slug from the route and the shared page chrome.
//
// Optional `?applicationId=` (SPEC.md §4.3 "Многоэтапность"): the cabinet's "Этап I
// одобрен — продолжить этап II" banner links here with the specific application id.
// `POST /applications` only finds-or-creates a *draft*-status application by service,
// so it can't be used to reopen a later-stage application whose status has moved past
// "draft" — the wizard must resume that exact id instead (see ApplicationWizard's init
// effect in components/form-engine/application-wizard.tsx).
export default async function ApplyPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ applicationId?: string }>;
}) {
  const { slug } = await params;
  const { applicationId } = await searchParams;

  return (
    <>
      <SiteHeader />
      <main id="main">
        <section className="section container">
          <p>
            <Link className="muted" href={`/take/services/${slug}`}>← К услуге</Link>
          </p>
          <ApplicationWizard slug={slug} applicationId={applicationId} />
        </section>
      </main>
    </>
  );
}
