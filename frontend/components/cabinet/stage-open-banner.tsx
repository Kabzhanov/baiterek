import Link from "next/link";

// Многоэтапность (SPEC.md §4.3, "Обязательное расширение" §4.3, требование 3): заметный
// баннер в личном кабинете, когда этап I одобрен и этап II открылся в той же заявке.
// Ведёт в мастер с `?applicationId=` — тот резюмирует ровно эту заявку (не создаёт новую
// через create-or-find-draft, который ищет только status="draft", см.
// app/take/services/[slug]/apply/page.tsx docstring), поэтому попадает ровно на этап II
// — checkpoint там уже стоит на нём (см. backend/app/api/admin.py::change_application_status).
export function StageOpenBanner({ slug, applicationId }: { slug: string; applicationId: string }) {
  return (
    <div className="stage-banner" role="note">
      <strong>Этап I одобрен — можно продолжить этап II</strong>
      <Link className="button" href={`/take/services/${slug}/apply?applicationId=${applicationId}`}>
        Продолжить этап II
      </Link>
    </div>
  );
}
