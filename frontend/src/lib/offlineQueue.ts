/// <reference lib="webworker" />
import { openDB } from "./offlineDB";
import { queryClient } from "./queryClient";

export interface QueuedAction {
  id: string;
  url: string;
  method: string;
  headers: Record<string, string>;
  body: string;
  timestamp: number;
  entity_type: string;
  entity_id: string;
}

export interface PendingSyncItem {
  id: string;
  entity_type: string;
  entity_id: string;
  timestamp: number;
  [key: string]: any;
}

/**
 * Enqueues an offline action into IndexedDB and triggers a background sync via the Service Worker.
 */
export async function enqueueOfflineAction(
  url: string,
  method: string,
  headers: Record<string, string>,
  body: any,
  entity_type: string,
  entity_id: string
) {
  const API_BASE =
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
  const fullUrl = url.startsWith("http") ? url : `${API_BASE}${url}`;
  
  const id = `${entity_type}-${entity_id}`;
  const timestamp = Date.now();
  
  // Inject client_timestamp into the payload for conflict resolution on the backend
  const bodyObj = { ...body, client_timestamp: timestamp };

  const action: QueuedAction = {
    id,
    url: fullUrl,
    method,
    headers,
    body: JSON.stringify(bodyObj),
    timestamp,
    entity_type,
    entity_id,
  };

  // 1. Save to IndexedDB
  try {
    const db = await openDB();
    const tx = db.transaction("sync-queue", "readwrite");
    const store = tx.objectStore("sync-queue");
    await new Promise<void>((resolve, reject) => {
      const req = store.put(action);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
    console.log(`[OfflineQueue] Queued action ${id} in IndexedDB`);
  } catch (err) {
    console.error("[OfflineQueue] Failed to save action to IndexedDB:", err);
  }

  // 2. Save/mirror to localStorage for synchronous UI queries
  try {
    const pending = JSON.parse(
      localStorage.getItem("atelier_pending_sync") || "[]",
    );
    const existingIndex = pending.findIndex((p: PendingSyncItem) => p.id === id);
    const newItem = { id, entity_type, entity_id, timestamp, ...bodyObj };
    if (existingIndex >= 0) {
      pending[existingIndex] = newItem;
    } else {
      pending.push(newItem);
    }
    localStorage.setItem("atelier_pending_sync", JSON.stringify(pending));
    console.log(`[OfflineQueue] Mirrored to localStorage: ${id}`);
  } catch (err) {
    console.error("[OfflineQueue] Failed to mirror to localStorage:", err);
  }

  // 3. Trigger Service Worker background sync
  if ("serviceWorker" in navigator) {
    try {
      const reg = await navigator.serviceWorker.ready;
      if ("sync" in reg) {
        interface ServiceWorkerRegistrationWithSync extends ServiceWorkerRegistration {
          sync: { register: (tag: string) => Promise<void> };
        }
        await (reg as ServiceWorkerRegistrationWithSync).sync.register(
          "sync-progress",
        );
        console.log(
          "[OfflineQueue] Registered background sync tag 'sync-progress'",
        );
      }

      // Send message to SW to trigger sync immediately if SW is active
      if (navigator.serviceWorker.controller) {
        navigator.serviceWorker.controller.postMessage({
          type: "TRIGGER_SYNC",
        });
      }
    } catch (err) {
      console.warn(
        "[OfflineQueue] Service worker sync registration failed/unsupported:",
        err,
      );
    }
  }
}

export async function syncOfflineQueue() {
  if (!navigator.onLine) return;

  try {
    const db = await openDB();
    const tx = db.transaction("sync-queue", "readonly");
    const store = tx.objectStore("sync-queue");
    const actions: QueuedAction[] = await new Promise((resolve, reject) => {
      const req = store.getAll();
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });

    if (actions.length === 0) return;

    console.log(
      `[OfflineQueue] Found ${actions.length} pending actions, starting sync...`,
    );

    for (const action of actions) {
      try {
        const response = await fetch(action.url, {
          method: action.method,
          headers: action.headers,
          body: action.body,
        });

        // 200/201 is success. 400 or 409 means bad request/already completed, so discard.
        if (response.ok || response.status === 400 || response.status === 409) {
          console.log(`[OfflineQueue] Successfully synced action ${action.id}`);

          // Remove from IndexedDB
          const writeTx = db.transaction("sync-queue", "readwrite");
          const writeStore = writeTx.objectStore("sync-queue");
          await new Promise<void>((resolve, reject) => {
            const deleteReq = writeStore.delete(action.id);
            deleteReq.onsuccess = () => resolve();
            deleteReq.onerror = () => reject(deleteReq.error);
          });

          // Remove from localStorage
          const pending = JSON.parse(
            localStorage.getItem("atelier_pending_sync") || "[]",
          );
          const filtered = pending.filter(
            (p: PendingSyncItem) => p.id !== action.id,
          );
          localStorage.setItem(
            "atelier_pending_sync",
            JSON.stringify(filtered),
          );

          // Invalidate React Query progress query depending on entity type
          if (action.entity_type === "lesson") {
            queryClient.invalidateQueries({ queryKey: ["userProgress"] });
          } else if (action.entity_type === "quiz") {
            queryClient.invalidateQueries({ queryKey: ["quizAttempts"] });
          } else if (action.entity_type === "code_submission") {
            queryClient.invalidateQueries({ queryKey: ["codeSubmissions"] });
          }
        } else {
          console.warn(
            `[OfflineQueue] Action ${action.id} returned status ${response.status}. Will retry later.`,
          );
        }
      } catch (err) {
        console.error(`[OfflineQueue] Error syncing action ${action.id}:`, err);
        break; // Stop and retry later on network error
      }
    }
  } catch (err) {
    console.error("[OfflineQueue] Error during offline queue sync:", err);
  }
}

// Register service worker listener and online trigger
if (typeof window !== "undefined") {
  window.addEventListener("online", () => {
    console.log("[OfflineQueue] Browser went online. Triggering sync...");
    syncOfflineQueue();
  });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.addEventListener("message", (event) => {
      if (event.data && event.data.type === "SYNC_SUCCESS") {
        const id = event.data.id;
        const entity_type = event.data.entity_type;
        console.log(`[OfflineQueue] SW synced ${id}`);

        try {
          const pending = JSON.parse(
            localStorage.getItem("atelier_pending_sync") || "[]",
          );
          const filtered = pending.filter(
            (p: PendingSyncItem) => p.id !== id,
          );
          localStorage.setItem(
            "atelier_pending_sync",
            JSON.stringify(filtered),
          );

          if (entity_type === "lesson") {
            queryClient.invalidateQueries({ queryKey: ["userProgress"] });
          } else if (entity_type === "quiz") {
            queryClient.invalidateQueries({ queryKey: ["quizAttempts"] });
          } else if (entity_type === "code_submission") {
            queryClient.invalidateQueries({ queryKey: ["codeSubmissions"] });
          }
        } catch (e) {
          console.error(
            "[OfflineQueue] Error clearing sync'd item from localStorage",
            e,
          );
        }
      }
    });
  }
}
