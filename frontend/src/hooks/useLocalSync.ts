import { useState, useEffect, useCallback } from "react";

const STORAGE_KEY = "atelier_pending_sync";

export interface PendingSyncItem {
  id?: string;
  lesson_slug: string;
  score?: number;
  completed?: boolean;
  timestamp: number;
}

export interface ProgressEntry {
  id: number;
  lesson: number;
  lesson_slug: string;
  completed: boolean;
  score: number;
  updated_at: string;
}

export function useLocalSync() {
  const [pending, setPending] = useState<PendingSyncItem[]>([]);

  const loadPending = useCallback(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setPending(JSON.parse(stored));
      } else {
        setPending([]);
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
    [pending]
  );

  const getPendingXP = useCallback(
    (backendProgress: ProgressEntry[]) => {
      let pendingXP = 0;
      pending.forEach((p) => {
        const inBackend = backendProgress.some(
          (bp) => bp.lesson_slug === p.lesson_slug
        );
        if (!inBackend) {
          pendingXP += p.score || 0;
        }
      });
      return pendingXP;
    },
    [pending]
  );

  return {
    pending,
    isLessonPendingCompleted,
    getPendingXP,
    refresh: loadPending,
  };
}
export function useLocalSyncGeneric<T>(key: string, initialData: T) {
  const [data, setData] = useState<T>(() => {
    const stored = localStorage.getItem(key);
    return stored ? JSON.parse(stored) : initialData;
  });

  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = useCallback(
    (newData: T) => {
      localStorage.setItem(key, JSON.stringify(newData));
      setData(newData);
    },
    [key]
  );

  const sync = useCallback(async () => {
    setIsSyncing(true);
    setError(null);
    try {
      const res = await fetch(`/api/progress/${key}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("token")}`,
        },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("Sync failed");
      setIsSyncing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed");
      setIsSyncing(false);
    }
  }, [key, data]);

  return { data, setData: save, sync, isSyncing, error };
}
export default useLocalSync;