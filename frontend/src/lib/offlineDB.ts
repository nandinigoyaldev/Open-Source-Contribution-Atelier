export const DB_NAME = "atelier-offline-db";
export const DB_VERSION = 4;
export const SYNC_STORE = "sync-queue";
export const LESSON_STORE = "lessons";
export const QUIZ_SYNC_STORE = "pending_quiz_sync";
export const CURRICULUM_STORE = "curriculum-manifests";

export function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event: IDBVersionChangeEvent) => {
      const db = (event.target as IDBOpenDBRequest).result;

      // v1 store — preserve
      if (!db.objectStoreNames.contains(SYNC_STORE)) {
        db.createObjectStore(SYNC_STORE, { keyPath: "id" });
      }

      // v2 store — lesson content cache
      if (!db.objectStoreNames.contains(LESSON_STORE)) {
        const store = db.createObjectStore(LESSON_STORE, { keyPath: "slug" });
        store.createIndex("fetchedAt", "fetchedAt", { unique: false });
      }

      // v3 store — offline quiz submissions awaiting background sync
      if (!db.objectStoreNames.contains(QUIZ_SYNC_STORE)) {
        const quizStore = db.createObjectStore(QUIZ_SYNC_STORE, {
          keyPath: "id",
        });
        quizStore.createIndex("queuedAt", "queuedAt", { unique: false });
      }

      // v4 store — versioned offline-first curriculum manifest cache (Issue #3285)
      if (!db.objectStoreNames.contains(CURRICULUM_STORE)) {
        const curriculumStore = db.createObjectStore(CURRICULUM_STORE, {
          keyPath: "id",
        });
        curriculumStore.createIndex("version", "version", { unique: false });
        curriculumStore.createIndex("status", "status", { unique: false });
        curriculumStore.createIndex("cachedAt", "cachedAt", { unique: false });
      }
    };

    request.onsuccess = (event: Event) => {
      resolve((event.target as IDBOpenDBRequest).result);
    };

    request.onerror = (event: Event) => {
      reject((event.target as IDBOpenDBRequest).error);
    };
  });
}
