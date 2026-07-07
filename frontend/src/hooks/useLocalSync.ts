 feat/localsync-hook
// frontend/src/hooks/useLocalSync.ts
import { useState, useEffect, useCallback } from 'react';

export function useLocalSync<T>(key: string, initialData: T) {
  const [data, setData] = useState<T>(() => {
    const stored = localStorage.getItem(key);
    return stored ? JSON.parse(stored) : initialData;
  });

  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Save to localStorage
  const save = useCallback((newData: T) => {
    localStorage.setItem(key, JSON.stringify(newData));
    setData(newData);
  }, [key]);

  // Sync with server
  const sync = useCallback(async () => {
    setIsSyncing(true);
    setError(null);

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
main
    try {
      // POST to server
      const res = await fetch(`/api/progress/${key}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error('Sync failed');
      setIsSyncing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync failed');
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