import { useState, useEffect, useCallback } from "react";

/**
 * A generic hook for syncing arbitrary data to localStorage
 * with optional server-side persistence.
 */
export function useLocalSyncGeneric<T>(key: string, initialData: T) {
  const [data, setData] = useState<T>(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem(key);
      return stored ? JSON.parse(stored) : initialData;
    }
    return initialData;
  });

  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Save to localStorage
  const save = useCallback(
    (newData: T) => {
      localStorage.setItem(key, JSON.stringify(newData));
      setData(newData);
    },
    [key],
  );

  // Sync with server
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

  // Auto-save on change
  useEffect(() => {
    const timer = setTimeout(() => {
      if (data) localStorage.setItem(key, JSON.stringify(data));
    }, 500);
    return () => clearTimeout(timer);
  }, [data, key]);

  return { data, setData: save, sync, isSyncing, error };
}
