const DB_NAME = "atelier-offline-db";
const STORE_NAME = "sync-queue";
const DB_VERSION = 1;

self.addEventListener("install", () => {
  console.log("[ServiceWorker] Installed");
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  console.log("[ServiceWorker] Activated");
  event.waitUntil(self.clients.claim());
});

self.addEventListener("sync", (event) => {
  console.log("[ServiceWorker] Sync event fired for tag:", event.tag);
  if (event.tag === "sync-progress") {
    event.waitUntil(syncProgressQueue());
  }
});

self.addEventListener("message", (event) => {
  console.log("[ServiceWorker] Message received:", event.data);
  if (event.data && event.data.type === "TRIGGER_SYNC") {
    event.waitUntil(syncProgressQueue());
  }
});

function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
    };
    request.onsuccess = (event) => {
      resolve(event.target.result);
    };
    request.onerror = (event) => {
      reject(event.target.error);
    };
  });
}

function deleteFromStore(db, id) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, "readwrite");
    const store = transaction.objectStore(STORE_NAME);
    const request = store.delete(id);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

async function notifyClients(message) {
  const clients = await self.clients.matchAll();
  clients.forEach((client) => {
    client.postMessage(message);
  });
}

async function syncProgressQueue() {
  console.log("[ServiceWorker] Starting background queue sync...");
  let db;
  try {
    db = await openDB();
  } catch (err) {
    console.error("[ServiceWorker] Failed to open IndexedDB:", err);
    return;
  }

  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, "readonly");
    const store = transaction.objectStore(STORE_NAME);
    const request = store.getAll();

    request.onsuccess = async () => {
      const actions = request.result;
      if (!actions || actions.length === 0) {
        console.log("[ServiceWorker] Queue is empty. Nothing to sync.");
        resolve();
        return;
      }

      console.log(
        `[ServiceWorker] Found ${actions.length} pending actions to sync.`,
      );

      for (const action of actions) {
        try {
          console.log(
            `[ServiceWorker] Replaying action: ${action.id} to ${action.url}`,
          );
          const response = await fetch(action.url, {
            method: action.method,
            headers: action.headers,
            body: action.body,
          });

          // 200, 201 are success. 400 or 409 means bad request / already completed, so discard.
          if (
            response.ok ||
            response.status === 400 ||
            response.status === 409
          ) {
            console.log(
              `[ServiceWorker] Action ${action.id} synced successfully (Status: ${response.status})`,
            );

            // Delete from IndexedDB
            await deleteFromStore(db, action.id);

            // Notify clients
            let bodyObj = {};
            try {
              bodyObj = JSON.parse(action.body);
            } catch (e) {}

            await notifyClients({
              type: "SYNC_SUCCESS",
              id: action.id,
              lesson_slug: bodyObj.lesson_slug,
            });
          } else {
            console.warn(
              `[ServiceWorker] Action ${action.id} sync failed (Status: ${response.status}). Retrying later.`,
            );
          }
        } catch (err) {
          console.error(
            `[ServiceWorker] Fetch error for action ${action.id}:`,
            err,
          );
          // Keep in queue and resolve to try again later on network error
        }
      }
      resolve();
    };

    request.onerror = () => {
      console.error(
        "[ServiceWorker] Failed to read IndexedDB store:",
        request.error,
      );
      reject(request.error);
    };
  });
}
