import { SiteHeader } from "@/components/site-header";
import { DefinitionsRegistry } from "@/components/definitions/definitions-registry";

// Реестр услуг — вход в административный контур (SPEC.md §5.1).
export default function Create() {
  return (
    <>
      <SiteHeader />
      <main id="main">
        <section className="section container">
          <h1>Реестр услуг</h1>
          <p className="lead">
            Создавайте и публикуйте услуги без кода: вручную в конструкторе или из документа через AI.
          </p>
          <DefinitionsRegistry />
        </section>
      </main>
    </>
  );
}
