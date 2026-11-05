import { openDB } from "./offlineDB";
import { eventBus } from "../core/events";
export interface QueuedAction {
  id: string;
  url: string;
  method: string;
  headers: Record<string, string>;
  body: string;
  timestamp: number;
  /** Set once a replay hit a server conflict; such items are not replayed again. */
  state?: "conflict";
}

/** Result of replaying one queued item. "failed" is the only retryable state. */
export type SyncItemStatus = "synced" | "duplicate" | "conflict" | "failed";

export interface SyncItemResult {
  id: string;
  lesson_slug: string;
  status: SyncItemStatus;
  httpStatus?: number;
  /** Only for "failed": false when the server rejected the item for good. */
  retryable?: boolean;
  /** Only for "conflict": what the server has for this lesson. */
  serverData?: unknown;
}

interface PendingSyncItem {
  id?: string;
  lesson_slug: string;
  score?: number;
  completed?: boolean;
  timestamp: number;
  /** "failed": last replay hit a temporary error. "conflict": needs the user. */
  state?: "failed" | "conflict";
  serverData?: unknown;
}

const PENDING_KEY = "atelier_pending_sync";
const RESULTS_KEY = "atelier_sync_results";
const MAX_STORED_RESULTS = 20;
const PERMANENT_REJECTIONS = [400, 404, 410, 422];

/**
 * Maps the HTTP status of a replayed request to a per-item status.
 * On /progress/me/ a 200 means the lesson was already recorded (201 and 202
 * are a fresh save), anywhere else any 2xx is a plain success.
 */
export function classifyReplayStatus(
  httpStatus: number,
  isProgressRequest = true,
): { status: SyncItemStatus; retryable: boolean } {
  if (httpStatus >= 200 && httpStatus < 300) {
    const fresh = httpStatus === 201 || httpStatus === 202;
    return {
      status: fresh || !isProgressRequest ? "synced" : "duplicate",
      retryable: false,
    };
  }
  if (httpStatus === 409) return { status: "conflict", retryable: false };
  return {
    status: "failed",
    retryable: !PERMANENT_REJECTIONS.includes(httpStatus),
  };
}

function readList<T>(key: string): T[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function updatePendingMirror(
  matches: (p: PendingSyncItem) => boolean,
  patch: Partial<PendingSyncItem> | null,
) {
  try {
    const pending = readList<PendingSyncItem>(PENDING_KEY);
    const next = patch
      ? pending.map((p) => (matches(p) ? { ...p, ...patch } : p))
      : pending.filter((p) => !matches(p));
    localStorage.setItem(PENDING_KEY, JSON.stringify(next));
  } catch (err) {
    console.error("[OfflineQueue] Failed to update localStorage mirror:", err);
  }
}

/** Settled results (saved, already completed, rejected) the status UI shows once. */
export function getSyncResults(): SyncItemResult[] {
  return readList<SyncItemResult>(RESULTS_KEY);
}

export function clearSyncResults() {
  try {
    localStorage.removeItem(RESULTS_KEY);
  } catch {
    // storage unavailable, nothing to clear
  }
}

function recordSettledResult(result: SyncItemResult) {
  try {
    const kept = getSyncResults().filter((r) => r.id !== result.id);
    kept.push(result);
    localStorage.setItem(
      RESULTS_KEY,
      JSON.stringify(kept.slice(-MAX_STORED_RESULTS)),
    );
  } catch (err) {
    console.error("[OfflineQueue] Failed to store sync result:", err);
  }
}

export async function enqueueOfflineAction(
  url: string,
  method: string,
  headers: Record<string, string>,
  body: Record<string, any> | string,
  type: string,
  slugOrId: string,
) {
  const id = `${type}-${slugOrId}`;
  const API_BASE =
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
  const finalUrl = url.startsWith("http") ? url : `${API_BASE}${url}`;

  const bodyStr = typeof body === "string" ? body : JSON.stringify(body);
  const bodyObj = typeof body === "string" ? JSON.parse(body) : body;

  const action: QueuedAction = {
    id,
    url: finalUrl,
    method,
    headers,
    body: bodyStr,
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
  } catch (err) {
    console.error("[OfflineQueue] Failed to save action to IndexedDB:", err);
  }

  // 2. Mirror to localStorage
  try {
    const pending = JSON.parse(
      localStorage.getItem("atelier_pending_sync") || "[]",
    );
    const exists = pending.some((p: any) => p.id === id);
    if (!exists) {
      pending.push({
        id,
        lesson_slug: bodyObj.lesson_slug || slugOrId,
        score: bodyObj.score ?? 100,
        completed: bodyObj.completed ?? true,
        timestamp: action.timestamp,
      });
      localStorage.setItem("atelier_pending_sync", JSON.stringify(pending));
    }
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
  }
}

export async function queueProgressSync(data: {
  lesson_slug: string;
  score?: number;
  completed?: boolean;
  headers: Record<string, string>;
}) {
  const API_BASE =
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
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
    const pending = JSON.parse(
      localStorage.getItem("atelier_pending_sync") || "[]",
    );
    const exists = pending.some(
      (p: PendingSyncItem) => p.lesson_slug === data.lesson_slug,
    );
    if (!exists) {
      pending.push({
        lesson_slug: data.lesson_slug,
        score: data.score ?? 100,
        completed: data.completed ?? true,
        timestamp: action.timestamp,
      });
      localStorage.setItem("atelier_pending_sync", JSON.stringify(pending));
      console.log(
        `[OfflineQueue] Mirrored to localStorage: ${data.lesson_slug}`,
      );
    }
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

let syncInFlight: Promise<SyncItemResult[]> | null = null;

function parseBody(body: string): Record<string, any> {
  try {
    const parsed = JSON.parse(body);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

/** Applies one replay result to the local mirror, the results list and the event bus. */
function settleResult(result: SyncItemResult, localData?: unknown) {
  const matches = (p: PendingSyncItem) =>
    (p.id !== undefined && p.id === result.id) ||
    p.lesson_slug === result.lesson_slug;

  if (result.status === "synced" || result.status === "duplicate") {
    updatePendingMirror(matches, null);
    recordSettledResult(result);
    // Emit sync success event instead of directly importing queryClient
    eventBus.emit("sync:success", {
      lesson_slug: result.lesson_slug,
      status: result.status,
    });
  } else if (result.status === "conflict") {
    updatePendingMirror(matches, {
      state: "conflict",
      serverData: result.serverData,
    });
    eventBus.emit("sync:conflict", {
      id: result.id,
      lesson_slug: result.lesson_slug,
      serverData: result.serverData,
      localData,
    });
  } else if (result.retryable) {
    updatePendingMirror(matches, { state: "failed" });
  } else {
    // The server rejected it for good, replaying would never succeed.
    updatePendingMirror(matches, null);
    recordSettledResult(result);
  }
}

/**
 * A conflict from the online bulk update. Nothing is queued for it, but it goes in
 * the pending list like a replayed one so the status UI keeps offering Review for
 * it, also when a batch has several and the prompt can only show one at a time.
 */
export function reportProgressConflict(
  serverData: { lesson_slug: string },
  localData?: { score?: number; completed?: boolean },
) {
  const { lesson_slug } = serverData;
  const id = `progress-sync-${lesson_slug}`;
  try {
    const pending = readList<PendingSyncItem>(PENDING_KEY).filter(
      (p) => p.lesson_slug !== lesson_slug,
    );
    pending.push({
      id,
      lesson_slug,
      score: localData?.score,
      completed: localData?.completed,
      timestamp: Date.now(),
      state: "conflict",
      serverData,
    });
    localStorage.setItem(PENDING_KEY, JSON.stringify(pending));
  } catch (err) {
    console.error("[OfflineQueue] Failed to store conflict:", err);
  }
  eventBus.emit("sync:conflict", { id, lesson_slug, serverData, localData });
}

async function writeQueuedAction(db: IDBDatabase, action: QueuedAction) {
  const store = db
    .transaction("sync-queue", "readwrite")
    .objectStore("sync-queue");
  await new Promise<void>((resolve, reject) => {
    const req = store.put(action);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

async function deleteQueuedAction(db: IDBDatabase, id: string) {
  const store = db
    .transaction("sync-queue", "readwrite")
    .objectStore("sync-queue");
  await new Promise<void>((resolve, reject) => {
    const req = store.delete(id);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

async function replayQueue(): Promise<SyncItemResult[]> {
  const db = await openDB();
  const tx = db.transaction("sync-queue", "readonly");
  const store = tx.objectStore("sync-queue");
  const actions: QueuedAction[] = await new Promise((resolve, reject) => {
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });

  const results: SyncItemResult[] = [];
  if (actions.length === 0) return results;

  console.log(
    `[OfflineQueue] Found ${actions.length} pending actions, starting sync...`,
  );

  for (const action of actions) {
    // Waiting for the user to pick a side, replaying would only 409 again.
    if (action.state === "conflict") continue;

    const bodyObj = parseBody(action.body);
    const lesson_slug: string = bodyObj.lesson_slug ?? action.id;

    let response: Response;
    try {
      response = await fetch(action.url, {
        method: action.method,
        headers: action.headers,
        body: action.body,
      });
    } catch (err) {
      console.error(`[OfflineQueue] Error syncing action ${action.id}:`, err);
      const result: SyncItemResult = {
        id: action.id,
        lesson_slug,
        status: "failed",
        retryable: true,
      };
      results.push(result);
      settleResult(result);
      break; // Stop and retry later on network error
    }

    const { status, retryable } = classifyReplayStatus(
      response.status,
      action.url.includes("/progress/me/"),
    );
    const result: SyncItemResult = {
      id: action.id,
      lesson_slug,
      status,
      httpStatus: response.status,
    };
    if (status === "failed") {
      result.retryable = retryable;
      console.warn(
        `[OfflineQueue] Action ${action.id} returned status ${response.status}.`,
      );
    }
    if (status === "conflict") {
      result.serverData = await response.json().catch(() => ({}));
    }

    try {
      if (status === "conflict") {
        await writeQueuedAction(db, { ...action, state: "conflict" });
      } else if (status !== "failed" || !retryable) {
        await deleteQueuedAction(db, action.id);
      }
    } catch (err) {
      console.error(
        `[OfflineQueue] Failed to update action ${action.id}:`,
        err,
      );
    }

    results.push(result);
    settleResult(result, bodyObj);
  }

  if (results.length > 0) eventBus.emit("sync:results", results);
  return results;
}

/**
 * Replays the queue and returns one result per item it attempted. Items that
 * failed with a temporary error stay queued (call it again to retry them),
 * conflicts wait for the user and are skipped.
 */
export async function syncOfflineQueue(): Promise<SyncItemResult[]> {
  if (!navigator.onLine) return [];

  if (!syncInFlight) {
    syncInFlight = replayQueue()
      .catch((err) => {
        console.error("[OfflineQueue] Error during offline queue sync:", err);
        return [] as SyncItemResult[];
      })
      .finally(() => {
        syncInFlight = null;
      });
  }
  return syncInFlight;
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
        const { id, status: httpStatus } = event.data;
        const lesson_slug: string = event.data.lesson_slug ?? id;
        console.log(`[OfflineQueue] SW synced ${lesson_slug}`);

        try {
          const { status, retryable } =
            typeof httpStatus === "number"
              ? classifyReplayStatus(
                  httpStatus,
                  typeof id === "string" &&
                    (id.startsWith("progress-sync-") ||
                      id.startsWith("lesson-")),
                )
              : { status: "synced" as SyncItemStatus, retryable: false };
          const result: SyncItemResult = {
            id,
            lesson_slug,
            status,
            httpStatus,
          };
          if (status === "failed") result.retryable = retryable;
          settleResult(result);
          eventBus.emit("sync:results", [result]);
        } catch (e) {
          console.error(
            "[OfflineQueue] Error clearing sync'd item from localStorage",
            e,
          );
        }
      } else if (event.data && event.data.type === "SYNC_CONFLICT") {
        const { id, serverData, localData } = event.data;
        // The SW only knows the slug for progress-sync-* ids
        const lesson_slug: string =
          event.data.lesson_slug ??
          localData?.lesson_slug ??
          serverData?.lesson_slug;
        console.warn(
          `[OfflineQueue] Sync conflict detected for ${lesson_slug}`,
        );
        settleResult(
          { id, lesson_slug, status: "conflict", httpStatus: 409, serverData },
          localData,
        );
        flagQueuedConflict(id);
      } else if (event.data && event.data.type === "SYNC_FAILED") {
        const { id, status: httpStatus } = event.data;
        const { retryable } = classifyReplayStatus(httpStatus ?? 0);
        const result: SyncItemResult = {
          id,
          lesson_slug: event.data.lesson_slug ?? id,
          status: "failed",
          httpStatus,
          retryable,
        };
        settleResult(result);
        eventBus.emit("sync:results", [result]);
      }
    });
  }
}

/** Keeps a conflicting item out of later replays until the user resolves it. */
async function flagQueuedConflict(id: string) {
  try {
    const db = await openDB();
    const store = db
      .transaction("sync-queue", "readwrite")
      .objectStore("sync-queue");
    const action: QueuedAction | undefined = await new Promise(
      (resolve, reject) => {
        const req = store.get(id);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      },
    );
    if (action) await writeQueuedAction(db, { ...action, state: "conflict" });
  } catch (err) {
    console.error("[OfflineQueue] Failed to flag conflicting item:", err);
  }
}

export async function removeQueuedAction(id: string, lessonSlug: string) {
  try {
    const db = await openDB();
    const writeTx = db.transaction("sync-queue", "readwrite");
    const writeStore = writeTx.objectStore("sync-queue");
    await new Promise<void>((resolve, reject) => {
      const deleteReq = writeStore.delete(id);
      deleteReq.onsuccess = () => resolve();
      deleteReq.onerror = () => reject(deleteReq.error);
    });

    const pending = JSON.parse(
      localStorage.getItem("atelier_pending_sync") || "[]",
    );
    const filtered = pending.filter((p: any) => p.lesson_slug !== lessonSlug);
    localStorage.setItem("atelier_pending_sync", JSON.stringify(filtered));
    console.log(`[OfflineQueue] Successfully removed queued action ${id}`);
  } catch (err) {
    console.error("[OfflineQueue] Error removing queued action:", err);
  }
}
