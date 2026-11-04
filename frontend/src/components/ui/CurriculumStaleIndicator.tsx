import React from "react";
import type { CurriculumContentSource } from "../../lib/curriculumCache";

export interface CurriculumStaleIndicatorProps {
  isStale: boolean; isOffline: boolean; source: CurriculumContentSource;
  cachedAt: number | null; warning?: string; onRefresh?: () => void;
  isRefreshing?: boolean; className?: string;
}

export function CurriculumStaleIndicator({
  isStale, isOffline, source, cachedAt, warning, onRefresh, isRefreshing = false, className = "",
}: CurriculumStaleIndicatorProps) {
  if (!isStale && !isOffline && source === "network" && !warning) return null;
  if (source === "rollback" || warning) {
    return (
      <div role="status" aria-live="polite" data-testid="curriculum-rollback-banner" className={`flex items-center justify-between gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs text-amber-900 dark:text-amber-200 ${className}`}>
        <div>
          <p className="font-semibold">Curriculum Rollback Active</p>
          <p className="opacity-90">{warning || "Incomplete curriculum received; restored previous verified version."}</p>
        </div>
        {onRefresh && (
          <button type="button" onClick={onRefresh} disabled={isRefreshing} className="rounded-lg bg-amber-600/20 px-3 py-1 font-medium hover:bg-amber-600/30 disabled:opacity-50">
            {isRefreshing ? "Checking..." : "Retry Update"}
          </button>
        )}
      </div>
    );
  }
  if (isOffline) {
    return (
      <div role="status" aria-live="polite" data-testid="curriculum-offline-banner" className={`flex items-center gap-2 rounded-lg border border-sky-500/25 bg-sky-500/10 px-3.5 py-2 text-xs text-sky-900 dark:text-sky-200 ${className}`}>
        <span className="h-2 w-2 rounded-full bg-sky-500 animate-pulse" aria-hidden="true" />
        <span><strong>Offline Mode:</strong> Browsing locally saved curriculum.</span>
      </div>
    );
  }
  if (isStale && cachedAt) {
    return (
      <div role="status" aria-live="polite" data-testid="curriculum-stale-banner" className={`flex items-center justify-between gap-3 rounded-lg border border-zinc-500/20 bg-zinc-500/5 px-3.5 py-2 text-xs text-zinc-700 dark:text-zinc-300 ${className}`}>
        <span>🕒 Cached curriculum snapshot.</span>
        {onRefresh && (
          <button type="button" onClick={onRefresh} disabled={isRefreshing} className="text-sky-600 dark:text-sky-400 hover:underline font-semibold">
            {isRefreshing ? "Refreshing..." : "Check for updates"}
          </button>
        )}
      </div>
    );
  }
  return null;
}
