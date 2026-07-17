export const DB_NAME = "atelier-offline-db";
export const DB_VERSION = 3;
export const SYNC_STORE = "sync-queue";
export const LESSON_STORE = "lessons";

// New stores per spec
export const PENDING_CHANGES_STORE = "pendingChanges";
export const OFFLINE_CONTENT_STORE = "offlineContent";
export const SYNC_LOG_STORE = "syncLog";


export function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event: IDBVersionChangeEvent) => {
      const db = (event.target as IDBOpenDBRequest).result;

      // v1 store — preserve
      if (!db.objectStoreNames.contains(SYNC_STORE)) {
        db.createObjectStore(SYNC_STORE, { keyPath: "id" });
      }

      // v2 store — lesson content cache (legacy, keep)
      if (!db.objectStoreNames.contains(LESSON_STORE)) {
        const store = db.createObjectStore(LESSON_STORE, { keyPath: "slug" });
        store.createIndex("fetchedAt", "fetchedAt", { unique: false });
      }

      // v3 store — pending changes queue
      if (!db.objectStoreNames.contains(PENDING_CHANGES_STORE)) {
        const store = db.createObjectStore(PENDING_CHANGES_STORE, { keyPath: "id" });
        store.createIndex("timestamp", "timestamp", { unique: false });
      }

      // v3 store — offline lesson content
      if (!db.objectStoreNames.contains(OFFLINE_CONTENT_STORE)) {
        const store = db.createObjectStore(OFFLINE_CONTENT_STORE, { keyPath: "lessonSlug" });
        store.createIndex("fetchedAt", "fetchedAt", { unique: false });
      }

      // v3 store — sync log
      if (!db.objectStoreNames.contains(SYNC_LOG_STORE)) {
        db.createObjectStore(SYNC_LOG_STORE, { keyPath: "syncId" });
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
