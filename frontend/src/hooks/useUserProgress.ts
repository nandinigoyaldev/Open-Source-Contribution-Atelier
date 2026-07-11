import { useMemo, useRef, useCallback, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";
import { useLocalSync } from "./useLocalSync";

export interface ProgressEntry {
  id: number;
  lesson: number;
  lesson_slug: string;
  completed: boolean;
  score: number;
  updated_at: string;
}

// NEW: Interface for our bulk sync payload
type SyncPayload = {
  lesson_slug: string;
  score?: number;
  completed?: boolean;
  client_timestamp?: number;
};

export function useUserProgress() {
  const queryClient = useQueryClient();
  useLocalSync();

  // NEW: Refs to handle debouncing and UI rollback state safely without triggering re-renders
  const pendingSyncQueue = useRef<Map<string, SyncPayload>>(new Map());
  const syncTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const snapshotRef = useRef<ProgressEntry[] | null>(null);

  // 1. Query to fetch all progress
  const { data: progress = [], isLoading } = useQuery<ProgressEntry[]>({
    queryKey: ["userProgress"],
    queryFn: () => fetchApi("/progress/me/", { suppressErrorToast: true }),
    // Uses global staleTime default from queryClient (5 min)
  });

  // 2. NEW: Bulk Mutation to replace the single sync mutation
  const bulkSyncMutation = useMutation({
    mutationFn: (lessons: SyncPayload[]) =>
      fetchApi("/progress/bulk-update/", {
        suppressErrorToast: true,
        method: "POST",
        body: JSON.stringify({
          lessons,
          metadata: { timestamp: Date.now() },
        }),
      }),
    onSettled: () => {
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
      });

      // Reset the 3-second timer on every fast click
      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }

      syncTimeoutRef.current = setTimeout(() => {
        const queue = Array.from(pendingSyncQueue.current.values());
        if (queue.length > 0) {
          const previousState = snapshotRef.current;

          bulkSyncMutation.mutate(queue, {
            onError: (err) => {
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
  };
}
