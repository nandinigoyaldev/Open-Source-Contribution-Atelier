import { useMemo, useState } from "react";
import { Download, FileImage, Image as ImageIcon, Share2 } from "lucide-react";
import {
  LearningPathShareStats,
  buildLearningPathShareSvg,
  downloadPngFromSvg,
  downloadSvgFile,
  hasShareableProgress,
} from "../../lib/learningPathShareCard";

export type LearningPathShareCardProps = {
  stats: LearningPathShareStats;
  isLoading?: boolean;
  className?: string;
};

export function LearningPathShareCard({
  stats,
  isLoading = false,
  className = "",
}: LearningPathShareCardProps) {
  const [exporting, setExporting] = useState<"svg" | "png" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const svgMarkup = useMemo(() => buildLearningPathShareSvg(stats), [stats]);
  const canShare = hasShareableProgress(stats);

  const handleSvg = () => {
    setError(null);
    setExporting("svg");
    try {
      downloadSvgFile(stats, svgMarkup);
    } catch {
      setError("Could not download SVG. Try again.");
    } finally {
      setExporting(null);
    }
  };

  const handlePng = async () => {
    setError(null);
    setExporting("png");
    try {
      await downloadPngFromSvg(stats, svgMarkup);
    } catch {
      setError("Could not export PNG. Try SVG instead.");
    } finally {
      setExporting(null);
    }
  };

  if (isLoading) {
    return (
      <section
        className={`rounded-[2rem] border-4 border-black bg-white p-6 shadow-card animate-pulse dark:bg-[#1f1c18] dark:border-[#2e2924] ${className}`}
        aria-busy="true"
      >
        <div className="h-6 w-48 rounded bg-gray-200 dark:bg-gray-700 mb-4" />
        <div className="aspect-[1200/630] w-full rounded-xl bg-gray-200 dark:bg-gray-700" />
      </section>
    );
  }

  if (!canShare) {
    return (
      <section
        className={`rounded-[2rem] border-4 border-dashed border-black/40 bg-surface-low p-8 text-center dark:bg-[#151411] dark:border-[#2e2924] ${className}`}
        data-testid="learning-path-share-empty"
      >
        <Share2 className="mx-auto mb-3 h-10 w-10 text-muted" aria-hidden />
        <h2 className="text-xl font-black dark:text-[#f0ebe2]">
          Nothing to share yet
        </h2>
        <p className="mx-auto mt-2 max-w-md text-sm font-bold text-muted dark:text-[#c4bbae]">
          Complete a lesson or keep a streak going, then come back to export a
          learning-path progress card (separate from your graduation
          certificate).
        </p>
      </section>
    );
  }

  return (
    <section
      className={`rounded-[2rem] border-4 border-black bg-white p-5 sm:p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] ${className}`}
      data-testid="learning-path-share-card"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-black dark:text-[#f0ebe2]">
            <Share2 className="h-5 w-5 text-primary" aria-hidden />
            Share your learning path
          </h2>
          <p className="mt-1 text-xs font-bold text-muted dark:text-[#c4bbae]">
            Social progress card — modules, streak, and badges (not a
            certificate).
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleSvg}
            disabled={!!exporting}
            className="inline-flex items-center gap-2 rounded-xl border-2 border-black bg-primary px-4 py-2 text-xs font-black shadow-card-sm disabled:opacity-60"
          >
            <Download className="h-3.5 w-3.5" aria-hidden />
            {exporting === "svg" ? "Saving…" : "Download SVG"}
          </button>
          <button
            type="button"
            onClick={() => void handlePng()}
            disabled={!!exporting}
            className="inline-flex items-center gap-2 rounded-xl border-2 border-black bg-white px-4 py-2 text-xs font-black dark:bg-[#151411] dark:border-[#2e2924] disabled:opacity-60"
          >
            <FileImage className="h-3.5 w-3.5" aria-hidden />
            {exporting === "png" ? "Saving…" : "Download PNG"}
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border-4 border-black bg-[#FFF8EF]">
        <div
          className="w-full [&_svg]:h-auto [&_svg]:w-full"
          // Preview the same SVG that gets downloaded
          dangerouslySetInnerHTML={{
            __html: svgMarkup.replace(/^<\?xml[^>]*>\s*/i, ""),
          }}
        />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatChip
          label="Modules"
          value={`${stats.modulesCompleted}/${stats.modulesTotal}`}
        />
        <StatChip label="Streak" value={`${stats.streakDays}d`} />
        <StatChip label="Badges" value={`${stats.badgeCount}`} />
        <StatChip label="Complete" value={`${stats.completionPercent}%`} />
      </div>

      {error && (
        <p role="alert" className="mt-3 text-xs font-bold text-red-600">
          {error}
        </p>
      )}

      <p className="mt-3 flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-muted dark:text-[#c4bbae]">
        <ImageIcon className="h-3 w-3" aria-hidden />
        1200×630 SVG · PNG export via canvas
      </p>
    </section>
  );
}

function StatChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border-2 border-black bg-surface-low px-3 py-2 dark:bg-[#151411] dark:border-[#2e2924]">
      <p className="text-[10px] font-black uppercase text-muted dark:text-[#c4bbae]">
        {label}
      </p>
      <p className="text-lg font-black dark:text-[#f0ebe2]">{value}</p>
    </div>
  );
}

export default LearningPathShareCard;
