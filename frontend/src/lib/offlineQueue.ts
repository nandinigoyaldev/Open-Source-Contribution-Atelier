import { openDB } from "./offlineDB";
import { eventBus } from "../core/events";
import { SYNC_STORE } from "./offlineDB";

export interface QueuedAction {
  id: string;
  url: string;
  method: string;
  headers: Record<string, string>;
  body: string;
  timestamp: number;
}

type SyncType = "progress" | "quiz" | "help";

type PendingChangeItem = {
  id: string;
  lesson_slug: string;
  score?: number;
  completed?: boolean;
  timestamp: number;
  type: SyncType;
};

interface PendingSyncItem {
  lesson_slug: string;
  score?: number;
  completed?: boolean;
  timestamp: number;
}

function now() {
  return Date.now();
}

function makePendingChangeId(type: SyncType, slugOrId: string) {
  return `${type}-${slugOrId}`;
}

function getApiBase() {
  return import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
}

function getPendingList(): PendingChangeItem[] {
  try {
    return JSON.parse(localStorage.getItem("atelier_pending_sync") || "[]");
  } catch {
    return [];
  }
}

function setPendingList(items: PendingChangeItem[]) {
  localStorage.setItem("atelier_pending_sync", JSON.stringify(items));
}

async function putActionToIndexedDB(action: QueuedAction) {
  const db = await openDB();
  const tx = db.transaction("sync-queue", "readwrite");
  const store = tx.objectStore("sync-queue");
  await new Promise<void>((resolve, reject) => {
    const req = store.put(action);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

async function mirrorToLocalStorage(item: PendingChangeItem) {
  const pending = getPendingList();
  const exists = pending.some((p) => p.id === item.id);
  if (!exists) {
    pending.push(item);
    setPendingList(pending);
  }
}

function triggerServiceWorkerSyncProgress() {
  if (!("serviceWorker" in navigator)) return;

  void (async () => {
    try {
      const reg = await navigator.serviceWorker.ready;
      if ("sync" in reg) {
        interface ServiceWorkerRegistrationWithSync
          extends ServiceWorkerRegistration {
          sync: { register: (tag: string) => Promise<void> };
        }
        // Current SW supports sync-progress tag; other tags will be added later.
        await (reg as ServiceWorkerRegistrationWithSync).sync.register(
          "sync-progress",
        );
      }

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
  })();
}

export async function enqueueOfflineAction(
  url: string,
  method: string,
  headers: Record<string, string>,
  body: Record<string, any> | string,
  type: SyncType,
  lesson_slug: string,
) {
  const id = makePendingChangeId(type, lesson_slug);
  const finalUrl = url.startsWith("http") ? url : `${getApiBase()}${url}`;

  const bodyStr = typeof body === "string" ? body : JSON.stringify(body);
  const bodyObj = typeof body === "string" ? JSON.parse(body) : body;

  const action: QueuedAction = {
    id,
    url: finalUrl,
    method,
    headers,
    body: bodyStr,
    timestamp: now(),
  };

  // 1. Save to IndexedDB
  try {
    await putActionToIndexedDB(action);
  } catch (err) {
    console.error("[OfflineQueue] Failed to save action to IndexedDB:", err);
  }

  // 2. Mirror to localStorage for synchronous UI queries
  try {
    const pendingItem: PendingChangeItem = {
      id,
      lesson_slug,
      score: bodyObj.score,
      completed: bodyObj.completed,
      timestamp: action.timestamp,
      type,
    };
    await mirrorToLocalStorage(pendingItem);
  } catch (err) {
    console.error("[OfflineQueue] Failed to mirror to localStorage:", err);
  }

  // 3. Trigger SW background sync (currently sync-progress tag)
  triggerServiceWorkerSyncProgress();
}

export async function queueProgressSync(data: {
  lesson_slug: string;
  score?: number;
  completed?: boolean;
  headers: Record<string, string>;
}) {
  const API_BASE = getApiBase();

  await enqueueOfflineAction(
    `${API_BASE}/progress/me/`,
    "POST",
    data.headers,
    {
      lesson_slug: data.lesson_slug,
      score: data.score,
      completed: data.completed,
    },
    "progress",
    data.lesson_slug,
  );
}

export async function queueQuizSubmissionOffline(data: {
  lesson_slug: string;
  // Match expected backend fields loosely; concrete shape will be validated by backend.
  quiz_attempt_id?: string;
  quiz_answer_payload: Record<string, any>;
  headers: Record<string, string>;
}) {
  const API_BASE = getApiBase();
  const body = {
    lesson_slug: data.lesson_slug,
    ...(data.quiz_attempt_id ? { quiz_attempt_id: data.quiz_attempt_id } : {}),
    ...data.quiz_answer_payload,
  };

  await enqueueOfflineAction(
    `${API_BASE}/progress/quiz/submit/`,
    "POST",
    data.headers,
    body,
    "quiz",
    data.lesson_slug,
  );
}

export async function queueHelpRequestOffline(data: {
  lesson_slug: string;
  message: string;
  headers: Record<string, string>;
}) {
  const API_BASE = getApiBase();

  await enqueueOfflineAction(
    `${API_BASE}/progress/help/request/`,
    "POST",
    data.headers,
    {
      lesson_slug: data.lesson_slug,
      message: data.message,
    },
    "help",
    data.lesson_slug,
  );
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

    // Sync in order (IndexedDB getAll returns insertion order in most browsers,
    // but the TODO tracker will later make this explicit with timestamp sorting).
    actions.sort((a, b) => a.timestamp - b.timestamp);

    for (const action of actions) {
      try {
        const response = await fetch(action.url, {
          method: action.method,
          headers: action.headers,
          body: action.body,
        });

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
          const pending = getPendingList();
          const filtered = pending.filter((p) => p.lesson_slug !== bodyObj.lesson_slug);
          setPendingList(filtered);

          eventBus.emit("sync:success", { lesson_slug: bodyObj.lesson_slug });
        } else {
          console.warn(
            `[OfflineQueue] Action ${action.id} returned status ${response.status}. Will retry later.`,
          );
        }
      } catch (err) {
        console.error(`[OfflineQueue] Error syncing action ${action.id}:`, err);
        break;
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
          const pending = getPendingList();
          const filtered = pending.filter((p: PendingSyncItem) => p.lesson_slug !== lesson_slug);
          setPendingList(filtered as any);

          eventBus.emit("sync:success", { lesson_slug });
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

