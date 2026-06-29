/**
 * lessonCache.ts
 * CRUD helpers for the "lessons" IndexedDB store.
 * Keeps all storage concerns isolated from UI and hooks.
 */
import { openDB, LESSON_STORE } from "./offlineDB";

export interface CachedLesson {
  slug: string;
  /** Raw markdown text */
  markdown: string;
  /** Lesson metadata (title, description, etc.) – serialised to string */
  metaJson: string;
  /** Unix ms timestamp of when this was cached */
  fetchedAt: number;
  /** Optional ETag from server for versioning */
  etag?: string;
}

// ─── read ────────────────────────────────────────────────────────────────────

export async function getCachedLesson(slug: string): Promise<CachedLesson | undefined> {
  try {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(LESSON_STORE, "readonly");
      const req = tx.objectStore(LESSON_STORE).get(slug);
      req.onsuccess = () => resolve(req.result as CachedLesson | undefined);
      req.onerror = () => reject(req.error);
    });
  } catch {
    return undefined;
  }
}

export async function getAllCachedSlugs(): Promise<string[]> {
  try {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(LESSON_STORE, "readonly");
      const req = tx.objectStore(LESSON_STORE).getAllKeys();
      req.onsuccess = () => resolve(req.result as string[]);
      req.onerror = () => reject(req.error);
    });
  } catch {
    return [];
  }
}

// ─── write ───────────────────────────────────────────────────────────────────

export async function putCachedLesson(entry: CachedLesson): Promise<void> {
  try {
    const db = await openDB();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(LESSON_STORE, "readwrite");
      const req = tx.objectStore(LESSON_STORE).put(entry);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch (err) {
    console.warn("[lessonCache] put failed:", err);
  }
}

// ─── delete ──────────────────────────────────────────────────────────────────

export async function deleteCachedLesson(slug: string): Promise<void> {
  try {
    const db = await openDB();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(LESSON_STORE, "readwrite");
      const req = tx.objectStore(LESSON_STORE).delete(slug);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch (err) {
    console.warn("[lessonCache] delete failed:", err);
  }
}

// ─── purge expired ───────────────────────────────────────────────────────────

const DEFAULT_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

export async function purgeExpiredLessons(maxAgeMs = DEFAULT_MAX_AGE_MS): Promise<void> {
  try {
    const db = await openDB();
    const cutoff = Date.now() - maxAgeMs;
    const all = await new Promise<CachedLesson[]>((resolve, reject) => {
      const tx = db.transaction(LESSON_STORE, "readonly");
      const req = tx.objectStore(LESSON_STORE).getAll();
      req.onsuccess = () => resolve(req.result as CachedLesson[]);
      req.onerror = () => reject(req.error);
    });

    const stale = all.filter((l) => l.fetchedAt < cutoff);
    if (stale.length === 0) return;

    const db2 = await openDB();
    const tx = db2.transaction(LESSON_STORE, "readwrite");
    const store = tx.objectStore(LESSON_STORE);
    stale.forEach((l) => store.delete(l.slug));
    console.log(`[lessonCache] Purged ${stale.length} expired lesson(s).`);
  } catch (err) {
    console.warn("[lessonCache] purge failed:", err);
  }
}
