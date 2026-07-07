import { SiteHeader } from "@/components/site-header";
import { DefinitionEditorShell } from "@/components/definitions/definition-editor-shell";

// Визуальный конструктор услуги (SPEC.md §5.2). Тонкий серверный компонент: параметры
// маршрута → клиентский редактор (весь I/O клиентский из-за X-User-Id/localStorage).
export default async function DefinitionEditorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <>
      <SiteHeader />
      <DefinitionEditorShell definitionId={id} />
    </>
  );
}
