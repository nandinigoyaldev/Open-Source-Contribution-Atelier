import React, { useState, useEffect, useCallback } from "react";
import {
  WifiOff,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  X,
} from "lucide-react";

import { useNetworkStatus } from "../../context/useNetworkStatus";
import { eventBus } from "../../core/events";
import {
  clearSyncResults,
  getSyncResults,
  syncOfflineQueue,
  type SyncItemResult,
} from "../../lib/offlineQueue";

interface PendingItem {
  id?: string;
  lesson_slug: string;
  score?: number;
  completed?: boolean;
  state?: "failed" | "conflict";
  serverData?: unknown;
}

function readPending(): PendingItem[] {
  try {
    const parsed = JSON.parse(
      localStorage.getItem("atelier_pending_sync") || "[]",
    );
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

const plural = (n: number, one: string, many: string) =>
  `${n} ${n === 1 ? one : many}`;

export function SyncStatusIndicator() {
  const { isOnline } = useNetworkStatus();
  const [pending, setPending] = useState<PendingItem[]>([]);
  const [results, setResults] = useState<SyncItemResult[]>([]);
  const [isRetrying, setIsRetrying] = useState(false);

  const refresh = useCallback(() => {
    setPending(readPending());
    setResults(getSyncResults());
  }, []);

  useEffect(() => {
    refresh();
    // Poll local storage for pending syncs, and refresh right after a replay
    const interval = setInterval(refresh, 2000);
    eventBus.on("sync:results", refresh);

    return () => {
      clearInterval(interval);
      eventBus.off("sync:results", refresh);
    };
  }, [refresh]);

  const failed = pending.filter((p) => p.state === "failed");
  const conflicts = pending.filter((p) => p.state === "conflict");
  const waiting = pending.length - failed.length - conflicts.length;
  const saved = results.filter((r) => r.status === "synced");
  const duplicates = results.filter((r) => r.status === "duplicate");
  const rejected = results.filter((r) => r.status === "failed");

  if (isOnline && pending.length === 0 && results.length === 0) {
    return null;
  }

  const handleRetry = async () => {
    setIsRetrying(true);
    try {
      await syncOfflineQueue();
    } finally {
      setIsRetrying(false);
      refresh();
    }
  };

  const handleReview = () => {
    const item = conflicts[0];
    if (!item) return;
    eventBus.emit("sync:conflict", {
      id: item.id,
      lesson_slug: item.lesson_slug,
      serverData: item.serverData,
      localData: { score: item.score, completed: item.completed },
    });
  };

  const handleDismiss = () => {
    clearSyncResults();
    refresh();
  };

  const row =
    "flex items-center gap-2 text-sm px-3 py-1 rounded-full border bg-gray-900 border-gray-700 text-gray-300 shadow-sm";
  const button =
    "ml-1 px-2 py-0.5 rounded-full border border-gray-500 text-xs font-bold text-white hover:bg-gray-700 disabled:opacity-50";

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col items-end gap-1.5 mx-2"
    >
      {!isOnline && (
        <div className={row}>
          <WifiOff className="w-4 h-4 text-yellow-500" />
          <span>Offline ({pending.length} pending)</span>
        </div>
      )}

      {isOnline && waiting > 0 && (
        <div className={row}>
          <RefreshCw className="w-4 h-4 text-blue-400 animate-spin" />
          <span>Syncing {plural(waiting, "item", "items")}...</span>
        </div>
      )}

      {isOnline && failed.length > 0 && (
        <div className={row}>
          <AlertTriangle className="w-4 h-4 text-red-400" />
          <span>
            {plural(failed.length, "item", "items")} failed to sync, try again
          </span>
          <button
            type="button"
            onClick={handleRetry}
            disabled={isRetrying}
            className={button}
          >
            {isRetrying ? "Retrying..." : "Retry"}
          </button>
        </div>
      )}

      {conflicts.length > 0 && (
        <div className={row}>
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <span>
            {conflicts.length === 1
              ? "1 lesson differs from the server"
              : `${conflicts.length} lessons differ from the server`}
          </span>
          <button type="button" onClick={handleReview} className={button}>
            Review
          </button>
        </div>
      )}

      {(saved.length > 0 || duplicates.length > 0 || rejected.length > 0) && (
        <div className={row}>
          <CheckCircle2
            className={`w-4 h-4 ${rejected.length > 0 ? "text-red-400" : "text-green-400"}`}
          />
          <span>
            {[
              saved.length > 0 && `${saved.length} saved`,
              duplicates.length > 0 && `${duplicates.length} already completed`,
              rejected.length > 0 &&
                `${rejected.length} rejected by the server`,
            ]
              .filter(Boolean)
              .join(", ")}
          </span>
          <button
            type="button"
            onClick={handleDismiss}
            aria-label="Dismiss sync results"
            className="p-0.5 rounded-full hover:bg-gray-700"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
