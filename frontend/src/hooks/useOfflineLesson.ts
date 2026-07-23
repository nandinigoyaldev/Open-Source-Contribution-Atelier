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

export function useOfflineLesson(
  lesson: Lesson | undefined,
): UseOfflineLessonResult {
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
    const l: Lesson = lesson; // narrowed to non-undefined for use inside async closure
    const now = Date.now();

    async function loadContent(forceNetwork: boolean) {
      if (!cancelled) setIsLoading(true);
      if (!cancelled) setError(null);

      try {
        // 1. Check Cache Storage API
        const cache = await caches.open("content-runtime-cache");
        const cachePath = l.filePath ? `/content/${l.filePath}` : null;
        let cachedResponse = cachePath ? await cache.match(cachePath) : null;

        if (!cancelled) setIsCached(!!cachedResponse);

        // 2. Serve from cache when offline OR cache is present and not forced
        if (!forceNetwork && (!isOnline || cachedResponse)) {
          if (cachedResponse) {
            const cachedText = await cachedResponse.text();
            if (!cancelled) {
              setMarkdown(cachedText);
              setSource("cache");
            }
            return;
          }
        }

        // 3. Offline + not cached → show fallback
        if (!isOnline && !cachedResponse) {
          if (!cancelled) {
            setMarkdown(
              `# ${l.title}\n\n> **You are offline** and this lesson has not been cached yet.\n> Connect to the internet to view this lesson for the first time.`,
            );
            setSource("fallback");
          }
          return;
        }

        // 4. Fetch from network
        let text: string;
        if (l.filePath) {
          text = await fetchLessonContent(l.filePath);
          // Explicitly update Cache Storage
          try {
            const cacheToUpdate = await caches.open("content-runtime-cache");
            await cacheToUpdate.put(cachePath!, new Response(text));
          } catch (e) {
            console.warn("[useOfflineLesson] Failed to write cache:", e);
          }
        } else {
          text = `# ${l.title}\n\n${l.explanation}`;
        }

        if (!cancelled) setIsCached(true);

        if (!cancelled) {
          setMarkdown(text);
          setSource("network");
        }
      } catch (err) {
        if (cancelled) return;
        const e = err instanceof Error ? err : new Error(String(err));
        setError(e);

        // Last-resort: try cached version even if stale
        if (l.filePath) {
          try {
            const cache = await caches.open("content-runtime-cache");
            const fallbackResponse = await cache.match(
              `/content/${l.filePath}`,
            );
            if (!cancelled) {
              if (fallbackResponse) {
                const text = await fallbackResponse.text();
                setMarkdown(text);
                setSource("cache");
              } else {
                setMarkdown(
                  `# Error loading lesson\n\nCould not load **${l.title}**. Please check your connection.`,
                );
                setSource("fallback");
              }
            }
          } catch {
            if (!cancelled) {
              setMarkdown(
                `# Error loading lesson\n\nCould not load **${l.title}**. Please check your connection.`,
              );
              setSource("fallback");
            }
          }
        } else {
          if (!cancelled) {
            setMarkdown(
              `# Error loading lesson\n\nCould not load **${l.title}**. Please check your connection.`,
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
