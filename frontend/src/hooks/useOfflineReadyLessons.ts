/**
 * useOfflineReadyLessons.ts
 * Tracks which curriculum lessons are available offline (SW cache + IndexedDB).
 * Re-checks when network status changes or when the lesson list changes.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNetworkStatus } from "../context/useNetworkStatus";
import {
  getOfflineReadySlugs,
  type OfflineLessonRef,
} from "../lib/contentCacheCheck";

export interface UseOfflineReadyLessonsResult {
  /** Slugs that can be read without a network connection */
  offlineReadySlugs: Set<string>;
  isChecking: boolean;
  isOnline: boolean;
  isOfflineReady: (slug: string) => boolean;
  refresh: () => void;
}

export function useOfflineReadyLessons(
  lessons: OfflineLessonRef[],
): UseOfflineReadyLessonsResult {
  const { isOnline } = useNetworkStatus();
  const [offlineReadySlugs, setOfflineReadySlugs] = useState<Set<string>>(
    () => new Set(),
  );
  const [isChecking, setIsChecking] = useState(false);
  const [refreshCount, setRefreshCount] = useState(0);

  const lessonKey = useMemo(
    () =>
      lessons
        .map((l) => `${l.slug}:${l.filePath ?? ""}`)
        .sort()
        .join("|"),
    [lessons],
  );

  const refresh = useCallback(() => {
    setRefreshCount((c) => c + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (lessons.length === 0) {
        if (!cancelled) setOfflineReadySlugs(new Set());
        return;
      }

      if (!cancelled) setIsChecking(true);
      try {
        const ready = await getOfflineReadySlugs(lessons);
        if (!cancelled) setOfflineReadySlugs(ready);
      } catch {
        if (!cancelled) setOfflineReadySlugs(new Set());
      } finally {
        if (!cancelled) setIsChecking(false);
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
    // lessonKey captures lesson identity; refreshCount forces re-scan
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lessonKey, isOnline, refreshCount]);

  // Re-scan when a lesson was just opened (IDB may have updated)
  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState === "visible") refresh();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [refresh]);

  const isOfflineReady = useCallback(
    (slug: string) => offlineReadySlugs.has(slug),
    [offlineReadySlugs],
  );

  return {
    offlineReadySlugs,
    isChecking,
    isOnline,
    isOfflineReady,
    refresh,
  };
}
