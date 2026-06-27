/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import type { ProgressEntry } from "./useUserProgress";

const STORAGE_KEY = "atelier_pending_sync";

export interface PendingProgress {
  lesson_slug: string;
  score?: number;
  completed?: boolean;
}

export function useLocalSync() {
  const [pending, setPending] = useState<PendingProgress[]>([]);

  const loadPending = useCallback(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY) || "[]";
      if (stored) {
        setPending(JSON.parse(stored));
        console.log("Pending from localStorage:", JSON.parse(stored));
      } else {
        setPending([]);
        console.log("No pending items in localStorage");
      }
    } catch (e) {
      console.error("Failed to load pending sync from localStorage", e);
      setPending([]);
    }
  }, []);

  useEffect(() => {
    loadPending();

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) {
        loadPending();
      }
    };

    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, [loadPending]);

  const isLessonPendingCompleted = useCallback(
    (slug: string) => {
      return pending.some((p) => p.lesson_slug === slug && p.completed);
    },
    [pending],
  );

  const getPendingXP = useCallback(
    (backendProgress: ProgressEntry[]) => {
      let pendingXP = 0;
      pending.forEach((p) => {
        const inBackend = backendProgress.some(
          (bp) => bp.lesson_slug === p.lesson_slug,
        );
        if (!inBackend) {
          pendingXP += p.score || 0;
        }
      });
      return pendingXP;
    },
    [pending],
  );

  return {
    pending,
    isLessonPendingCompleted,
    getPendingXP,
    refresh: loadPending,
  };
}
