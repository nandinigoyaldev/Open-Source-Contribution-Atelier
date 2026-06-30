export const DB_NAME = "atelier-offline-db";
export const DB_VERSION = 2;
export const SYNC_STORE = "sync-queue";
export const LESSON_STORE = "lessons";

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
    };

    request.onsuccess = (event: Event) => {
      resolve((event.target as IDBOpenDBRequest).result);
    };

    request.onerror = (event: Event) => {
      reject((event.target as IDBOpenDBRequest).error);
    };
  });
}

