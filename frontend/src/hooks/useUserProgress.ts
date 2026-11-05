import { useMemo, useRef, useCallback, useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";
import { reportProgressConflict } from "../lib/offlineQueue";
import { useLocalSync } from "./useLocalSync";
import { useOfflineSync } from "./useOfflineSync";

export interface ProgressEntry {
  id: number;
  lesson: number;
  lesson_slug: string;
  completed: boolean;
  score: number;
  /** Server side counter, sent back as expected_version on the next write. */
  version?: number;
  updated_at: string;
}

// NEW: Interface for our bulk sync payload
type SyncPayload = {
  lesson_slug: string;
  score?: number;
  completed?: boolean;
  client_timestamp?: number;
  expected_version?: number;
};

type BulkUpdateResponse = {
  /** Current version of every lesson in the batch that was not refused. */
  versions?: Record<string, number>;
  /** Lessons the server refused because this client was behind, with their current row. */
  conflicts?: ProgressEntry[];
};

/**
 * What this client last saw for a lesson. 0 means it saw no row at all. undefined
 * means it does not know (list not loaded, or an entry with no version such as an
 * optimistic one), so the field is left out and the server only lets the write
 * move progress forward.
 */
function lastSeenVersion(entries: ProgressEntry[] | undefined, slug: string) {
  if (!entries) return undefined;
  const entry = entries.find((p) => p.lesson_slug === slug);
  return entry ? entry.version : 0;
}

export type ProgressAnnouncement = {
  type: "success" | "error";
  message: string;
} | null;

export function useUserProgress() {
  const queryClient = useQueryClient();
  useLocalSync();
  const { syncProgress: queueOfflineSyncProgress } = useOfflineSync();

  // NEW: Refs to handle debouncing and UI rollback state safely without triggering re-renders
  const pendingSyncQueue = useRef<Map<string, SyncPayload>>(new Map());
  const syncTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const snapshotRef = useRef<ProgressEntry[] | null>(null);
  // Screen reader announcement for the result of a completion sync
  const [announcement, setAnnouncement] = useState<ProgressAnnouncement>(null);
  const inFlightRef = useRef(0);

  // 1. Query to fetch all progress
  const { data: progress = [], isLoading } = useQuery<ProgressEntry[]>({
    queryKey: ["userProgress"],
    queryFn: () => fetchApi("/progress/me/", { suppressErrorToast: true }),
    // Uses global staleTime default from queryClient (5 min)
  });

  // 2. NEW: Bulk Mutation to replace the single sync mutation
  const bulkSyncMutation = useMutation({
    mutationFn: (lessons: SyncPayload[]) =>
      fetchApi<BulkUpdateResponse>("/progress/bulk-update/", {
        suppressErrorToast: true,
        method: "POST",
        body: JSON.stringify({
          lessons,
          metadata: { timestamp: Date.now() },
        }),
      }),
    onMutate: () => {
      inFlightRef.current += 1;
    },
    // Here and not on mutate(): those callbacks are skipped if the page unmounts
    // while the request is in flight, and a conflict must not get lost with them.
    onSuccess: (data, lessons) => {
      const versions = data?.versions;
      if (versions) {
        queryClient.setQueryData<ProgressEntry[]>(["userProgress"], (old) =>
          old?.map((p) =>
            versions[p.lesson_slug] !== undefined
              ? { ...p, version: versions[p.lesson_slug] }
              : p,
          ),
        );
      }
      for (const conflict of data?.conflicts ?? []) {
        reportProgressConflict(
          conflict,
          lessons.find((l) => l.lesson_slug === conflict.lesson_slug),
        );
      }
    },
    onSettled: () => {
      inFlightRef.current = Math.max(0, inFlightRef.current - 1);
      // If more completions are still queued or in flight, a refetch now would
      // return totals that do not include them yet and overwrite the optimistic
      // cache. The last batch to settle refetches instead.
      if (inFlightRef.current > 0 || pendingSyncQueue.current.size > 0) return;
      // Clear snapshot and force a refetch to ensure perfect sync with the database
      snapshotRef.current = null;
      queryClient.invalidateQueries({ queryKey: ["userProgress"] });
    },
  });

  // Clear timeout on unmount to avoid memory leaks
  useEffect(() => {
    return () => {
      if (syncTimeoutRef.current) clearTimeout(syncTimeoutRef.current);
    };
  }, []);

  // 3. Exposed Sync Function (Optimistic + Debounced)
  const syncProgress = useCallback(
    async (vars: {
      lesson_slug: string;
      score?: number;
      completed?: boolean;
    }) => {
      // Cancel outgoing refetches so they don't overwrite our optimistic UI
      await queryClient.cancelQueries({ queryKey: ["userProgress"] });

      // Read before the optimistic update below. A lesson already waiting in this
      // batch keeps the version it started from.
      const queued = pendingSyncQueue.current.get(vars.lesson_slug);
      const expected_version = queued
        ? queued.expected_version
        : lastSeenVersion(
            queryClient.getQueryData<ProgressEntry[]>(["userProgress"]),
            vars.lesson_slug,
          );

      // Take a snapshot of the pristine state ONLY if this is the start of a new bulk batch
      if (pendingSyncQueue.current.size === 0) {
        snapshotRef.current =
          queryClient.getQueryData<ProgressEntry[]>(["userProgress"]) || [];
      }

      // --- OPTIMISTIC UI UPDATE ---
      // Update the React state instantly so the user sees no lag
      queryClient.setQueryData<ProgressEntry[]>(
        ["userProgress"],
        (old = []) => {
          const existingIdx = old.findIndex(
            (p) => p.lesson_slug === vars.lesson_slug,
          );
          const now = new Date().toISOString();

          if (existingIdx >= 0) {
            const updated = [...old];
            updated[existingIdx] = {
              ...updated[existingIdx],
              score:
                vars.score !== undefined
                  ? vars.score
                  : updated[existingIdx].score,
              completed:
                vars.completed !== undefined
                  ? vars.completed
                  : updated[existingIdx].completed,
              updated_at: now,
            };
            return updated;
          } else {
            return [
              ...old,
              {
                id: Date.now(), // Fake ID for optimistic UI
                lesson: 0,
                lesson_slug: vars.lesson_slug,
                score: vars.score || 0,
                completed: vars.completed || false,
                updated_at: now,
              },
            ];
          }
        },
      );

      // --- DEBOUNCE & BATCH LOGIC ---
      // Add or update the lesson in our pending queue
      pendingSyncQueue.current.set(vars.lesson_slug, {
        ...vars,
        client_timestamp: Date.now(),
        expected_version,
      });

      // Reset the 3-second timer on every fast click
      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }

      syncTimeoutRef.current = setTimeout(async () => {
        const queue = Array.from(pendingSyncQueue.current.values());
        if (queue.length > 0) {
          if (!navigator.onLine) {
            console.log(
              "[useUserProgress] Offline, queueing updates via useOfflineSync",
            );
            for (const item of queue) {
              await queueOfflineSyncProgress({
                lesson_slug: item.lesson_slug,
                score: item.score,
                completed: item.completed,
                expected_version: item.expected_version,
              });
            }
            pendingSyncQueue.current.clear();
            return;
          }

          const previousState = snapshotRef.current;

          // One announcement per batch, only when a completion is involved
          const hasCompletion = queue.some((item) => item.completed);
          if (hasCompletion) setAnnouncement(null);

          bulkSyncMutation.mutate(queue, {
            onSuccess: (data) => {
              if (!hasCompletion) return;
              setAnnouncement(
                data?.conflicts?.length
                  ? {
                      type: "error",
                      message:
                        "This lesson changed somewhere else. Review the difference to keep your progress.",
                    }
                  : { type: "success", message: "Lesson completion saved." },
              );
            },
            onError: (err) => {
              if (hasCompletion) {
                setAnnouncement({
                  type: "error",
                  message:
                    "Could not save lesson completion. Your progress was restored. Please try again.",
                });
              }
              console.error("Bulk sync failed, rolling back UI...", err);
              // --- ROLLBACK UI ON FAILURE ---
              if (previousState) {
                queryClient.setQueryData(["userProgress"], previousState);
              }
            },
          });

          pendingSyncQueue.current.clear();
        }
      }, 3000); // 3-second debounce window
    },
    [queryClient, bulkSyncMutation],
  );

  // 4. Convenience helpers
  const isLessonCompleted = useCallback(
    (slug: string) => {
      const isCompletedInBackend = progress.some(
        (p) => p.lesson_slug === slug && p.completed,
      );
      if (isCompletedInBackend) return true;

      try {
        const pending = JSON.parse(
          localStorage.getItem("atelier_pending_sync") || "[]",
        ) as { lesson_slug: string; score: number; completed: boolean }[];
        return pending.some((p) => p.lesson_slug === slug && p.completed);
      } catch {
        return false;
      }
    },
    [progress],
  );

  const totalXP = useMemo(() => {
    const backendXP = progress.reduce((acc, p) => acc + p.score, 0);
    let pendingXP = 0;
    try {
      const pending = JSON.parse(
        localStorage.getItem("atelier_pending_sync") || "[]",
      ) as { lesson_slug: string; score: number; completed: boolean }[];
      pending.forEach((p) => {
        const inBackend = progress.some(
          (bp) => bp.lesson_slug === p.lesson_slug,
        );
        if (!inBackend) {
          pendingXP += p.score || 0;
        }
      });
    } catch {
      // Ignore invalid JSON in localStorage
    }
    return backendXP + pendingXP;
  }, [progress]);

  return {
    progress,
    isLoading,
    isLessonCompleted,
    totalXP,
    syncProgress, // Now linked to our custom debounced function
    isSyncing: bulkSyncMutation.isPending,
    announcement,
  };
}
