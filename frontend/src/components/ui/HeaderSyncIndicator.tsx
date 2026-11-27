import React, { useState } from "react";
import { useSyncState } from "../../hooks/useSyncState";
import { syncOfflineQueue } from "../../lib/offlineQueue";

interface HeaderSyncIndicatorProps {
  className?: string;
  compact?: boolean;
}

export function HeaderSyncIndicator({
  className = "",
  compact = false,
}: HeaderSyncIndicatorProps) {
  const { syncState, pendingCount, isOnline } = useSyncState();
  const [isRetrying, setIsRetrying] = useState(false);

  const handleClick = async () => {
    if (isOnline && !isRetrying) {
      setIsRetrying(true);
      try {
        await syncOfflineQueue();
      } finally {
        setIsRetrying(false);
      }
    }
  };

  const getStatusConfig = () => {
    switch (syncState) {
      case "syncing":
        return {
          icon: (
            <svg
              className="w-3.5 h-3.5 text-blue-500 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          ),
          label: compact ? "Syncing" : "Syncing...",
          title: "Synchronizing offline changes via CRDT three-way merge",
          badgeClass:
            "border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400 hover:bg-blue-500/20",
          dotColor: "bg-blue-500 animate-pulse",
        };
      case "offline-buffered":
        return {
          icon: (
            <svg
              className="w-3.5 h-3.5 text-amber-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 00-9.78 2.096A4.001 4.001 0 003 15z"
              />
            </svg>
          ),
          label: compact
            ? `Offline-Buffered${pendingCount > 0 ? ` (${pendingCount})` : ""}`
            : `Offline-Buffered (${pendingCount} pending)`,
          title: `Offline mode: ${pendingCount} delta operations buffered in IndexedDB`,
          badgeClass:
            "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400 hover:bg-amber-500/20",
          dotColor: "bg-amber-500",
        };
      case "synced":
      default:
        return {
          icon: (
            <svg
              className="w-3.5 h-3.5 text-emerald-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M5 13l4 4L19 7"
              />
            </svg>
          ),
          label: "Synced",
          title: "All data synced and verified",
          badgeClass:
            "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-500/20",
          dotColor: "bg-emerald-500",
        };
    }
  };

  const config = getStatusConfig();

  return (
    <button
      type="button"
      onClick={handleClick}
      role="status"
      aria-live="polite"
      aria-label={`Sync status: ${syncState}`}
      title={config.title}
      data-testid="header-sync-status"
      data-sync-state={syncState}
      disabled={!isOnline || syncState === "syncing" || isRetrying}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full border transition-all duration-200 select-none disabled:cursor-default ${config.badgeClass} ${className}`}
    >
      <span className="relative flex items-center justify-center">
        {config.icon}
      </span>
      <span className="font-mono text-[11px] leading-none tracking-tight">
        {config.label}
      </span>
    </button>
  );
}

export default HeaderSyncIndicator;
