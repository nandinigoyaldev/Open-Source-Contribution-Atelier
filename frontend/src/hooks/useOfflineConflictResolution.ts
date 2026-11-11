import { useState, useCallback, useEffect } from "react";

export interface ConflictRecord<T = Record<string, unknown>> {
  id: string;
  entityType: "note" | "journal";
  title?: string;
  localData: T;
  serverData: T;
  localTimestamp: string;
  serverTimestamp: string;
  resolved?: boolean;
}

const STORAGE_KEY = "atelier_offline_conflicts";

export function useOfflineConflictResolution<
  T extends Record<string, unknown> = Record<string, unknown>,
>() {
  const [conflicts, setConflicts] = useState<ConflictRecord<T>[]>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(conflicts));
    } catch (e) {
      console.error("Failed to persist conflicts to local storage:", e);
    }
  }, [conflicts]);

  const addConflict = useCallback((conflict: Omit<ConflictRecord<T>, "id">) => {
    const id = `conflict_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    const newRecord: ConflictRecord<T> = {
      ...conflict,
      id,
      resolved: false,
    };
    setConflicts((prev) => [...prev, newRecord]);
    return id;
  }, []);

  const resolveConflict = useCallback(
    (
      conflictId: string,
      choice: "local" | "remote" | "merge",
      mergedData?: T,
    ) => {
      let resolvedPayload: T | null = null;
      setConflicts((prev) => {
        const found = prev.find((c) => c.id === conflictId);
        if (found) {
          if (choice === "local") resolvedPayload = found.localData;
          else if (choice === "remote") resolvedPayload = found.serverData;
          else if (choice === "merge" && mergedData)
            resolvedPayload = mergedData;
        }
        return prev.filter((c) => c.id !== conflictId);
      });
      return resolvedPayload;
    },
    [],
  );

  const clearConflict = useCallback((conflictId: string) => {
    setConflicts((prev) => prev.filter((c) => c.id !== conflictId));
  }, []);

  return {
    conflicts,
    addConflict,
    resolveConflict,
    clearConflict,
  };
}
