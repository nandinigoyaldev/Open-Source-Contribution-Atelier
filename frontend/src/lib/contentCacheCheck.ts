/**
 * contentCacheCheck.ts
 * Detect whether lesson Markdown under /content/ is available offline
 * via the Cache API (service worker) and/or IndexedDB lesson cache.
 */
import { getAllCachedSlugs, getCachedLesson } from "./lessonCache";

/** Workbox runtime cache name from src/sw.js */
export const CONTENT_RUNTIME_CACHE = "content-runtime-cache";

export interface OfflineLessonRef {
  slug: string;
  filePath?: string;
}

/** Build the absolute URL the SW would cache for a content file. */
export function contentUrlForFilePath(filePath: string): string {
  const normalized = filePath.replace(/^\/+/, "");
  if (typeof window !== "undefined" && window.location?.origin) {
    return new URL(`/content/${normalized}`, window.location.origin).href;
  }
  return `/content/${normalized}`;
}

/**
 * Check whether a URL is present in any Cache Storage cache
 * (runtime content cache first, then all caches as fallback).
 */
export async function isUrlInCacheStorage(url: string): Promise<boolean> {
  if (typeof caches === "undefined") return false;

  try {
    const runtime = await caches.open(CONTENT_RUNTIME_CACHE);
    if (await runtime.match(url, { ignoreSearch: true })) return true;

    const names = await caches.keys();
    for (const name of names) {
      if (name === CONTENT_RUNTIME_CACHE) continue;
      const cache = await caches.open(name);
      if (await cache.match(url, { ignoreSearch: true })) return true;
    }
  } catch {
    return false;
  }

  return false;
}

/** True if this lesson's /content/{filePath} asset is in the SW cache. */
export async function isContentFileCached(
  filePath: string | undefined,
): Promise<boolean> {
  if (!filePath) return false;
  return isUrlInCacheStorage(contentUrlForFilePath(filePath));
}

/** True if IndexedDB has markdown for this slug. */
export async function isLessonInIndexedDb(slug: string): Promise<boolean> {
  const entry = await getCachedLesson(slug);
  return !!entry?.markdown;
}

/**
 * A lesson is offline-ready when either:
 *  - IndexedDB has the lesson markdown (from prior online open), or
 *  - the SW Cache API has /content/{filePath}
 */
export async function isLessonOfflineReady(
  lesson: OfflineLessonRef,
): Promise<boolean> {
  if (await isLessonInIndexedDb(lesson.slug)) return true;
  return isContentFileCached(lesson.filePath);
}

/**
 * Batch-check which lessons are available offline.
 * Returns a Set of offline-ready slugs.
 */
export async function getOfflineReadySlugs(
  lessons: OfflineLessonRef[],
): Promise<Set<string>> {
  const ready = new Set<string>();
  if (lessons.length === 0) return ready;

  let idbSlugs: Set<string>;
  try {
    idbSlugs = new Set(await getAllCachedSlugs());
  } catch {
    idbSlugs = new Set();
  }

  await Promise.all(
    lessons.map(async (lesson) => {
      if (idbSlugs.has(lesson.slug)) {
        ready.add(lesson.slug);
        return;
      }
      if (await isContentFileCached(lesson.filePath)) {
        ready.add(lesson.slug);
      }
    }),
  );

  return ready;
}
