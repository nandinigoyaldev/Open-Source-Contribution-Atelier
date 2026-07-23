/**
 * AvailableOfflineBadge.tsx
 * Compact badge for lesson list rows when content is cached for offline reading.
 */
import { HardDrive } from "lucide-react";

interface AvailableOfflineBadgeProps {
  /** Compact icon-only mode for dense sidebars */
  compact?: boolean;
  className?: string;
}

export function AvailableOfflineBadge({
  compact = false,
  className = "",
}: AvailableOfflineBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border border-teal-600/40 bg-teal-50 px-1.5 py-0.5 text-[9px] font-black uppercase tracking-wide text-teal-800 dark:bg-teal-900/30 dark:text-teal-200 dark:border-teal-600/50 ${className}`}
      title="This lesson is cached and can be read offline"
      aria-label="Available offline"
    >
      <HardDrive className="h-2.5 w-2.5 shrink-0" aria-hidden />
      {!compact && <span>Available offline</span>}
      {compact && <span className="sr-only">Available offline</span>}
    </span>
  );
}
