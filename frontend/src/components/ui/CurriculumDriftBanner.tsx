import { AlertTriangle, X } from "lucide-react";
import { useState } from "react";
import type { CurriculumDriftReport } from "../../lib/curriculumSlugDrift";

type CurriculumDriftBannerProps = {
  slug: string;
  report: CurriculumDriftReport;
  className?: string;
};

/**
 * Soft warning when the open lesson exists in curriculum.json
 * but is missing from the seeded API lesson catalog.
 */
export function CurriculumDriftBanner({
  slug,
  report,
  className = "",
}: CurriculumDriftBannerProps) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed || !report.apiAvailable) return null;
  if (!report.missingInApi.includes(slug)) return null;

  return (
    <div
      role="status"
      data-testid="curriculum-drift-banner"
      className={`flex items-start gap-3 rounded-2xl border-2 border-amber-500 bg-amber-50 p-4 text-amber-950 dark:bg-amber-950/25 dark:text-amber-100 dark:border-amber-600 ${className}`}
    >
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1 text-sm">
        <p className="font-black">Curriculum / API slug drift</p>
        <p className="mt-1 font-bold leading-relaxed opacity-90">
          This lesson (<code className="rounded bg-black/10 px-1">{slug}</code>)
          is in{" "}
          <code className="rounded bg-black/10 px-1">curriculum.json</code> but
          not in the seeded API lessons. You can still read it; progress or
          roadmap sync may be incomplete until maintainers run{" "}
          <code className="rounded bg-black/10 px-1">
            python manage.py check_curriculum_slugs
          </code>{" "}
          and re-seed.
        </p>
        {report.missingInApi.length > 1 && (
          <p className="mt-2 text-xs font-bold opacity-80">
            {report.missingInApi.length} curriculum slug
            {report.missingInApi.length === 1 ? "" : "s"} missing from API
            total.
          </p>
        )}
      </div>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        className="rounded-lg border-2 border-amber-700/40 p-1 hover:bg-amber-100 dark:hover:bg-amber-900/40"
        aria-label="Dismiss drift warning"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

type CurriculumDriftSummaryProps = {
  report: CurriculumDriftReport;
  className?: string;
};

/** Soft summary for roadmap / learning-path surfaces when any slug drift exists. */
export function CurriculumDriftSummaryBanner({
  report,
  className = "",
}: CurriculumDriftSummaryProps) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed || !report.apiAvailable || !report.hasDrift) return null;

  return (
    <div
      role="status"
      data-testid="curriculum-drift-summary"
      className={`flex items-start gap-3 rounded-2xl border-2 border-amber-500 bg-amber-50 p-3 text-sm text-amber-950 dark:bg-amber-950/25 dark:text-amber-100 dark:border-amber-600 ${className}`}
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <p className="min-w-0 flex-1 font-bold leading-relaxed">
        Curriculum slug drift detected: {report.missingInApi.length} missing
        from API
        {report.missingInCurriculum.length > 0
          ? `, ${report.missingInCurriculum.length} missing from curriculum.json`
          : ""}
        . Roadmap progress may not match static lessons until maintainers sync
        seeds.
      </p>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        className="rounded-lg border-2 border-amber-700/40 p-1 hover:bg-amber-100 dark:hover:bg-amber-900/40"
        aria-label="Dismiss drift summary"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
