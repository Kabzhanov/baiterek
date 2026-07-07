import { SiteHeader } from "@/components/site-header";
import { GenerateForm } from "@/components/definitions/generate-form";

// AI-генератор услуги из документа (SPEC.md §5.3).
export default function GeneratePage() {
  return (
    <>
      <SiteHeader />
      <main id="main">
        <section className="section container">
          <h1>AI-генератор услуги</h1>
          <GenerateForm />
        </section>
      </main>
    </>
  );
}
