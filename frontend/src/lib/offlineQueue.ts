import { openDB } from "./offlineDB";
import { queryClient } from "../app/App";

export interface QueuedAction {
  id: string;
  url: string;
  method: string;
  headers: Record<string, string>;
  body: string;
  timestamp: number;
}

export async function queueProgressSync(data: {
  lesson_slug: string;
  score?: number;
  completed?: boolean;
  headers: Record<string, string>;
}) {
  const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
  const id = `progress-sync-${data.lesson_slug}`;

  const action: QueuedAction = {
    id,
    url: `${API_BASE}/progress/me/`,
    method: "POST",
    headers: data.headers,
    body: JSON.stringify({
      lesson_slug: data.lesson_slug,
      score: data.score,
      completed: data.completed,
    }),
    timestamp: Date.now(),
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
    const pending = JSON.parse(localStorage.getItem("atelier_pending_sync") || "[]");
    const exists = pending.some((p: any) => p.lesson_slug === data.lesson_slug);
    if (!exists) {
      pending.push({
        lesson_slug: data.lesson_slug,
        score: data.score ?? 100,
        completed: data.completed ?? true,
        timestamp: action.timestamp,
      });
      localStorage.setItem("atelier_pending_sync", JSON.stringify(pending));
      console.log(`[OfflineQueue] Mirrored to localStorage: ${data.lesson_slug}`);
    }
  } catch (err) {
    console.error("[OfflineQueue] Failed to mirror to localStorage:", err);
  }

  // 3. Trigger Service Worker background sync
  if ("serviceWorker" in navigator) {
    try {
      const reg = await navigator.serviceWorker.ready;
      if ("sync" in reg) {
        await (reg as any).sync.register("sync-progress");
        console.log("[OfflineQueue] Registered background sync tag 'sync-progress'");
      }

      // Send message to SW to trigger sync immediately if SW is active
      if (navigator.serviceWorker.controller) {
        navigator.serviceWorker.controller.postMessage({ type: "TRIGGER_SYNC" });
      }
    } catch (err) {
      console.warn("[OfflineQueue] Service worker sync registration failed/unsupported:", err);
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

    console.log(`[OfflineQueue] Found ${actions.length} pending actions, starting sync...`);

    for (const action of actions) {
      try {
        const response = await fetch(action.url, {
          method: action.method,
          headers: action.headers,
          body: action.body,
        });

        // 200/201 is success. 400 or 409 means bad request/already completed, so discard.
        if (response.ok || response.status === 400 || response.status === 409) {
          const bodyObj = JSON.parse(action.body);
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
          const pending = JSON.parse(localStorage.getItem("atelier_pending_sync") || "[]");
          const filtered = pending.filter((p: any) => p.lesson_slug !== bodyObj.lesson_slug);
          localStorage.setItem("atelier_pending_sync", JSON.stringify(filtered));

          // Invalidate React Query progress query
          queryClient.invalidateQueries({ queryKey: ["userProgress"] });
        } else {
          console.warn(`[OfflineQueue] Action ${action.id} returned status ${response.status}. Will retry later.`);
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
        const lesson_slug = event.data.lesson_slug;
        console.log(`[OfflineQueue] SW synced ${lesson_slug}`);

        try {
          const pending = JSON.parse(localStorage.getItem("atelier_pending_sync") || "[]");
          const filtered = pending.filter((p: any) => p.lesson_slug !== lesson_slug);
          localStorage.setItem("atelier_pending_sync", JSON.stringify(filtered));

          // Invalidate React Query progress query
          queryClient.invalidateQueries({ queryKey: ["userProgress"] });
        } catch (e) {
          console.error("[OfflineQueue] Error clearing sync'd item from localStorage", e);
        }
      }
    });
  }
}
