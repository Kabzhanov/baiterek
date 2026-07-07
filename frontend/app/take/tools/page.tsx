import { SiteHeader } from "@/components/site-header";
import { KnowledgeCatalog } from "@/components/tools/knowledge-catalog";
import { AnnuityCalculator } from "@/components/tools/annuity-calculator";
import { SubsidyCalculator } from "@/components/tools/subsidy-calculator";

// Инструменты и материалы (SPEC.md §4.7): база знаний · шаблоны · чек-листы ·
// калькуляторы · обзоры + два работающих калькулятора.
export default function ToolsPage() {
  return (
    <>
      <SiteHeader />
      <main id="main">
        <section className="section container">
          <h1>Инструменты и материалы</h1>
          <p className="lead">База знаний, шаблоны документов, чек-листы, калькуляторы и обзоры для предпринимателя.</p>
          <KnowledgeCatalog />
        </section>
        <section className="section container" style={{ background: "var(--wash)" }}>
          <h2>Калькуляторы</h2>
          <div className="tools-grid">
            <AnnuityCalculator />
            <SubsidyCalculator />
          </div>
        </section>
      </main>
    </>
  );
}
