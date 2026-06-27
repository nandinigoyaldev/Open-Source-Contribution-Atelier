/**
 * useOfflineLesson.ts
 * Offline-first hook for fetching lesson markdown content.
 *
 * Strategy:
 *  1. If offline → serve from IndexedDB cache (if available).
 *  2. If online  → fetch from network, update cache, then return.
 *  3. If online but cache is stale (>= maxAgeMs) → re-fetch to refresh cache.
 *
 * Returns:
 *  - markdown       : string content
 *  - source         : "network" | "cache" | "fallback"
 *  - isLoading      : boolean
 *  - error          : Error | null
 *  - refresh()      : force a network re-fetch
 *  - isCached       : boolean — whether this slug exists in the local cache
 */
import { useCallback, useEffect, useState } from "react";
import { useNetworkStatus } from "../context/useNetworkStatus";
import {
  getCachedLesson,
  putCachedLesson,
  purgeExpiredLessons,
  CachedLesson,
} from "../lib/lessonCache";
import { Lesson, fetchLessonContent } from "../lib/lessons";

type ContentSource = "network" | "cache" | "fallback";

interface UseOfflineLessonResult {
  markdown: string;
  source: ContentSource;
  isLoading: boolean;
  error: Error | null;
  refresh: () => void;
  isCached: boolean;
}

const CACHE_MAX_AGE_MS =
  Number((import.meta as { env?: Record<string, string> }).env?.VITE_LESSON_CACHE_MAX_AGE || 0) ||
  7 * 24 * 60 * 60 * 1000; // 7 days default

export function useOfflineLesson(lesson: Lesson | undefined): UseOfflineLessonResult {
  const { isOnline } = useNetworkStatus();
  const [markdown, setMarkdown] = useState("");
  const [source, setSource] = useState<ContentSource>("network");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [isCached, setIsCached] = useState(false);
  // incrementing this triggers a forced-network refresh
  const [refreshCount, setRefreshCount] = useState(0);

  const refresh = useCallback(() => {
    setRefreshCount((c) => c + 1);
  }, []);

  useEffect(() => {
    if (!lesson) return;

    let cancelled = false;
    const slug = lesson.slug;
    const now = Date.now();

    async function loadContent(forceNetwork: boolean) {
      if (!cancelled) setIsLoading(true);
      if (!cancelled) setError(null);

      try {
        // 1. Check IndexedDB cache
        const cached: CachedLesson | undefined = await getCachedLesson(slug);
        const isFresh = cached && now - cached.fetchedAt < CACHE_MAX_AGE_MS;

        if (!cancelled) setIsCached(!!cached);

        // 2. Serve from cache when offline OR cache is fresh and not forced
        if (!forceNetwork && (!isOnline || isFresh) && cached) {
          if (!cancelled) {
            setMarkdown(cached.markdown);
            setSource("cache");
          }
          return;
        }

        // 3. Offline + not cached → show fallback
        if (!isOnline && !cached) {
          if (!cancelled) {
            setMarkdown(
              `# ${lesson.title}\n\n> **You are offline** and this lesson has not been cached yet.\n> Connect to the internet to view this lesson for the first time.`
            );
            setSource("fallback");
          }
          return;
        }

        // 4. Fetch from network
        let text: string;
        if (lesson.filePath) {
          text = await fetchLessonContent(lesson.filePath);
        } else {
          text = `# ${lesson.title}\n\n${lesson.explanation}`;
        }

        // 5. Store in IndexedDB for offline reuse
        await putCachedLesson({
          slug,
          markdown: text,
          metaJson: JSON.stringify(lesson),
          fetchedAt: now,
        });
        if (!cancelled) setIsCached(true);

        // 6. Background purge of old entries (fire-and-forget)
        purgeExpiredLessons(CACHE_MAX_AGE_MS).catch(() => {});

        if (!cancelled) {
          setMarkdown(text);
          setSource("network");
        }
      } catch (err) {
        if (cancelled) return;
        const e = err instanceof Error ? err : new Error(String(err));
        setError(e);

        // Last-resort: try cached version even if stale
        const stale = await getCachedLesson(slug).catch(() => undefined);
        if (!cancelled) {
          if (stale) {
            setMarkdown(stale.markdown);
            setSource("cache");
          } else {
            setMarkdown(
              `# Error loading lesson\n\nCould not load **${lesson.title}**. Please check your connection.`
            );
            setSource("fallback");
          }
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    // refreshCount > 0 means user clicked refresh → force network
    void loadContent(refreshCount > 0);

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lesson?.slug, isOnline, refreshCount]);

  return { markdown, source, isLoading, error, refresh, isCached };
}
