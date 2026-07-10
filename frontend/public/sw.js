self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

// 1. Listen for standard Background Sync API events from the browser engine
self.addEventListener("sync", (event) => {
  if (event.tag === "sync-progress") {
    event.waitUntil(replaySyncQueue());
  }
});

// 2. Fallback: Listen for postMessage manual triggers from the application UI
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "TRIGGER_SYNC") {
    event.waitUntil(replaySyncQueue());
  }
});

async function replaySyncQueue() {
  // Use the standard name matching the local IndexedDB setup
  const dbName = "atelier-offline-db";
  const dbVersion = 1;

  return new Promise((resolve, reject) => {
    const request = indexedDB.open(dbName, dbVersion);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("sync-queue")) {
        return resolve();
      }

      const tx = db.transaction("sync-queue", "readonly");
      const store = tx.objectStore("sync-queue");
      const getAllRequest = store.getAll();

      getAllRequest.onsuccess = async () => {
        const actions = getAllRequest.result;
        if (!actions || actions.length === 0) return resolve();

        for (const action of actions) {
          try {
            const response = await fetch(action.url, {
              method: action.method,
              headers: action.headers,
              body: action.body,
            });

            // Accept 200/201 success, or 400/409 (already processed/bad request) to clean the queue
            if (
              response.ok ||
              response.status === 400 ||
              response.status === 409
            ) {
              const writeTx = db.transaction("sync-queue", "readwrite");
              writeTx.objectStore("sync-queue").delete(action.id);

              // Broadcast back to frontend contexts to clear UI mirrors and localstorage
              const bodyObj = JSON.parse(action.body);
              const clients = await self.clients.matchAll();
              clients.forEach((client) => {
                client.postMessage({
                  type: "SYNC_SUCCESS",
                  lesson_slug: bodyObj.lesson_slug,
                });
              });
            }
          } catch (err) {
            console.error(
              "[SW Sync Queue] Error syncing action item, halting for retry:",
              err,
            );
            break; // Halt execution loop if network breaks mid-sync
          }
        }
        resolve();
      };
    };
  });
}
