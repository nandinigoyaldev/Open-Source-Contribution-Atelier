import { precacheAndRoute, cleanupOutdatedCaches } from "workbox-precaching";
import { registerRoute } from "workbox-routing";
import {
  CacheFirst,
  NetworkFirst,
  StaleWhileRevalidate,
} from "workbox-strategies";
import { ExpirationPlugin } from "workbox-expiration";

cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);

// Cache curriculum content dynamically if not precached
registerRoute(
  ({ url }) => url.pathname.startsWith("/content/"),
  new CacheFirst({
    cacheName: "content-runtime-cache",
    plugins: [
      new ExpirationPlugin({
        maxEntries: 100,
        maxAgeSeconds: 30 * 24 * 60 * 60, // 30 days
      }),
    ],
  }),
);

// Cache API GET responses for instant dashboard/progress loads
// Serves cached data immediately, revalidates in background
const API_CACHE_PATHS = [
  "/api/dashboard/",
  "/api/progress/",
  "/api/leaderboard/",
  "/api/recommendations/",
  "/api/challenges/",
  "/api/users/me/learning-path/",
  "/api/content/lessons/",
];

registerRoute(
  ({ request, url }) => {
    if (request.method !== "GET") return false;
    return API_CACHE_PATHS.some((p) => url.pathname.startsWith(p));
  },
  new NetworkFirst({
    cacheName: "api-runtime-cache",
    plugins: [
      new ExpirationPlugin({
        maxEntries: 50,
        maxAgeSeconds: 60 * 60, // 1 hour
      }),
    ],
  }),
);

const DB_NAME = "atelier-offline-db";
const STORE_NAME = "sync-queue";
const QUIZ_STORE_NAME = "pending_quiz_sync";
// Must match QUEUE_SCHEMA_VERSION in src/lib/offlineQueue.ts. Records written
// by a newer build are left alone.
const QUEUE_SCHEMA_VERSION = 2;

self.addEventListener("install", (event) => {
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
    event.waitUntil(syncProgressQueueForSyncEvent());
  }
  if (event.tag === "sync-quiz-progress") {
    event.waitUntil(syncQuizQueue());
  }
});

self.addEventListener("message", (event) => {
  console.log("[ServiceWorker] Message received:", event.data);
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  } else if (event.data && event.data.type === "TRIGGER_SYNC") {
    // The page asked: it sees the outcome in the messages, nothing to reschedule
    event.waitUntil(syncProgressQueue().catch(() => {}));
  } else if (event.data && event.data.type === "TRIGGER_QUIZ_SYNC") {
    event.waitUntil(syncQuizQueue());
  }
});

self.addEventListener("push", (event) => {
  console.log("[ServiceWorker] Push event received:", event);
  if (!event.data) return;

  try {
    const data = event.data.json();
    const title = data.title || "New Notification";
    const options = {
      body: data.message || "You have a new message.",
      icon: "/vite.svg", // Fallback icon
      badge: "/vite.svg",
      data: {
        url: data.url || "/",
      },
    };

    event.waitUntil(self.registration.showNotification(title, options));
  } catch (err) {
    console.error("[ServiceWorker] Error parsing push data", err);
  }
});

self.addEventListener("notificationclick", (event) => {
  console.log("[ServiceWorker] Notification click Received.");
  event.notification.close();

  const urlToOpen = event.notification.data?.url || "/";

  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((windowClients) => {
        // Check if there is already a window/tab open with the target URL
        for (let i = 0; i < windowClients.length; i++) {
          const client = windowClients[i];
          if (client.url.includes(urlToOpen) && "focus" in client) {
            return client.focus();
          }
        }
        // If not, open a new window
        if (self.clients.openWindow) {
          return self.clients.openWindow(urlToOpen);
        }
      }),
  );
});

function openDB() {
  return new Promise((resolve, reject) => {
    // No version: open whatever the page upgraded the database to. Asking for
    // an older one than the page's (this used to say 3, the page is on 4)
    // fails with a VersionError and nothing gets replayed.
    const request = indexedDB.open(DB_NAME);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
      if (!db.objectStoreNames.contains(QUIZ_STORE_NAME)) {
        const quizStore = db.createObjectStore(QUIZ_STORE_NAME, {
          keyPath: "id",
        });
        quizStore.createIndex("queuedAt", "queuedAt", { unique: false });
      }
    };
    request.onsuccess = (event) => {
      const db = event.target.result;
      // Let the page upgrade the schema instead of blocking it
      db.onversionchange = () => db.close();
      resolve(db);
    };
    request.onerror = (event) => {
      reject(event.target.error);
    };
  });
}

function getAllFromStore(db, storeName) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(storeName, "readonly");
    const store = transaction.objectStore(storeName);
    const request = store.getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function deleteFromStore(db, storeName, id) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(storeName, "readwrite");
    const store = transaction.objectStore(storeName);
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

// What the server answers for a request that will never succeed on a retry
const PERMANENT_REJECTIONS = [400, 404, 410, 422];

/**
 * Reads the record with `id` and applies what `decide` returns ({ put } or
 * { remove: true }) in one transaction, so a check on the stored revision
 * cannot be overtaken by a write from the page. Resolves after the commit.
 * Records from a newer build are never changed.
 */
function editStored(db, id, decide) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    let changed = false;
    let record;
    tx.oncomplete = () => resolve({ changed, record });
    tx.onerror = () => reject(tx.error || new Error("IndexedDB write failed"));
    tx.onabort = () => reject(tx.error || new Error("IndexedDB write aborted"));
    const read = store.get(id);
    read.onerror = () => reject(read.error);
    read.onsuccess = () => {
      record = read.result;
      if (record && (record.schemaVersion || 1) > QUEUE_SCHEMA_VERSION) return;
      const edit = decide(record);
      if (!edit) return;
      changed = true;
      if (edit.put) {
        record = edit.put;
        store.put(edit.put);
      } else {
        record = undefined;
        store.delete(id);
      }
    };
  });
}

const sameRevision = (stored, action) =>
  !!stored && stored.idempotencyKey === action.idempotencyKey;

function kindFromUrl(url) {
  if (url.includes("/progress/me/")) return "progress";
  if (url.includes("/progress/bookmarks/")) return "bookmark";
  if (url.includes("/progress/quiz-attempts/")) return "quiz";
  if (url.includes("/progress/code-submissions/")) return "code_submission";
  return "other";
}

function tokenOwner(authorization) {
  const payload = String(authorization || "")
    .replace(/^Bearer\s+/i, "")
    .split(".")[1];
  if (!payload) return undefined;
  try {
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const claims = JSON.parse(
      atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, "=")),
    );
    const id = claims && (claims.user_id ?? claims.sub);
    return id === undefined || id === null ? undefined : String(id);
  } catch (e) {
    return undefined;
  }
}

/**
 * A record from before idempotency keys has none. The page and this worker may
 * both find it, so the key is committed in one transaction and whoever comes
 * second uses the stored one. Resolves the committed record (null when it is
 * gone). Mirrors upgradeQueuedAction() in src/lib/offlineQueue.ts.
 */
async function commitLegacyKey(db, action) {
  const key = crypto.randomUUID();
  const headers = {};
  for (const [name, value] of Object.entries(action.headers || {})) {
    if (name.toLowerCase() !== "idempotency-key") headers[name] = value;
  }
  headers["Idempotency-Key"] = key;
  const authorization = Object.entries(action.headers || {}).find(
    ([name]) => name.toLowerCase() === "authorization",
  );
  const upgraded = {
    ...action,
    headers,
    schemaVersion: QUEUE_SCHEMA_VERSION,
    seq: 0,
    idempotencyKey: key,
    kind: kindFromUrl(action.url),
    owner: tokenOwner(authorization && authorization[1]),
  };
  const { record } = await editStored(db, action.id, (stored) =>
    stored && (stored.schemaVersion || 1) < QUEUE_SCHEMA_VERSION
      ? { put: upgraded }
      : null,
  );
  return record || null;
}

// Resolves { retry } : true when something was left queued because of a
// temporary problem (offline, 5xx, a key still being processed). The sync
// event turns that into a rejected promise so the browser schedules another
// attempt; the page replaying the queue is the fallback.
async function syncProgressQueue() {
  console.log("[ServiceWorker] Starting background queue sync...");
  let retry = false;
  let db;
  try {
    db = await openDB();
  } catch (err) {
    console.error("[ServiceWorker] Failed to open IndexedDB:", err);
    return { retry: true };
  }

  let actions;
  try {
    actions = await getAllFromStore(db, STORE_NAME);
  } catch (err) {
    console.error("[ServiceWorker] Failed to read IndexedDB store:", err);
    db.close();
    return { retry: true };
  }

  // getAll() is key order; replay in the order things were queued (seq, set
  // by the page from its stored cursor; records from before it have none)
  actions = (actions || [])
    .filter((a) => (a.schemaVersion || 1) <= QUEUE_SCHEMA_VERSION)
    .sort(
      (a, b) =>
        (a.seq || 0) - (b.seq || 0) ||
        (a.timestamp || 0) - (b.timestamp || 0) ||
        String(a.id).localeCompare(String(b.id)),
    );

  if (actions.length === 0) {
    console.log("[ServiceWorker] Queue is empty. Nothing to sync.");
    db.close();
    return { retry };
  }

  console.log(
    `[ServiceWorker] Found ${actions.length} pending actions to sync.`,
  );

  // Lessons/bookmarks with an older action still waiting: newer ones wait too
  const blocked = new Set();
  const entityOf = (action) => {
    let slug = null;
    try {
      slug = JSON.parse(action.body || "{}").lesson_slug || null;
    } catch (e) {}
    if (action.kind === "bookmark") {
      return `bookmark:${String(action.id).replace(/^bookmark-/, "")}`;
    }
    return slug && (action.kind === "progress" || !action.kind)
      ? `progress:${slug}`
      : action.id;
  };

  for (let action of actions) {
    const entity = entityOf(action);
    // The page already got the 409 for this one and is waiting on the user
    if (action.state === "conflict") {
      blocked.add(entity);
      continue;
    }
    if (blocked.has(entity)) continue;
    try {
      if (!action.idempotencyKey) {
        const committed = await commitLegacyKey(db, action);
        if (!committed) continue; // removed meanwhile
        action = committed;
      }
      // Marked as sent before it goes out: if the answer is lost the server may
      // still have applied it, and the page must not treat it as never sent.
      // Not sent if it was replaced since.
      const marked = await editStored(db, action.id, (stored) =>
        sameRevision(stored, action)
          ? {
              put: {
                ...stored,
                dispatchedAt: stored.dispatchedAt || Date.now(),
              },
            }
          : null,
      );
      if (!marked.changed) continue;
    } catch (err) {
      // Left queued and not sent; the page can try again
      console.error(
        `[ServiceWorker] Could not prepare action ${action.id}:`,
        err,
      );
      blocked.add(entity);
      retry = true;
      continue;
    }
    try {
      console.log(
        `[ServiceWorker] Replaying action: ${action.id} to ${action.url}`,
      );
      const response = await fetch(action.url, {
        method: action.method,
        headers: action.headers,
        body: action.body || undefined,
      });

      // Extract lesson slug if id starts with 'progress-sync-' or 'bookmark-'
      let lesson_slug = null;
      if (action.id && action.id.startsWith("progress-sync-")) {
        lesson_slug = action.id.replace("progress-sync-", "");
      } else if (action.id && action.id.startsWith("bookmark-")) {
        lesson_slug = action.id.replace("bookmark-", "");
      }
      // idempotencyKey names the revision that was sent, so the page can tell
      // an answer for a replaced action from one for the queued action
      const meta = {
        kind: action.kind,
        method: action.method,
        idempotencyKey: action.idempotencyKey,
      };
      // Only this revision is removed: a newer write for the same id stays
      const removeSent = () =>
        editStored(db, action.id, (stored) =>
          sameRevision(stored, action) ? { remove: true } : null,
        );
      const conflictBody =
        response.status === 409
          ? await response
              .clone()
              .json()
              .catch(() => ({}))
          : null;
      // A 409 about the Idempotency-Key itself (the page is sending the same
      // key right now), not newer data on the server
      const keyRejection =
        conflictBody &&
        "idempotency_key" in conflictBody &&
        !("code" in conflictBody);
      // Removing a bookmark that is already gone is done, not failed
      const alreadyRemoved =
        action.kind === "bookmark" &&
        action.method === "DELETE" &&
        response.status === 404;

      if (response.ok || response.status === 400 || alreadyRemoved) {
        console.log(
          `[ServiceWorker] Action ${action.id} synced successfully (Status: ${response.status})`,
        );

        // Delete from IndexedDB
        await removeSent();

        // Notify clients
        await notifyClients({
          type: "SYNC_SUCCESS",
          id: action.id,
          status: response.status,
          lesson_slug: lesson_slug,
          entity_type: action.entity_type,
          entity_id: action.entity_id,
          ...meta,
        });
      } else if (keyRejection) {
        const inFlight = /being processed/i.test(
          String(conflictBody.error || ""),
        );
        if (inFlight) {
          blocked.add(entity);
          retry = true;
        } else {
          // This key will never be accepted: same as the page, drop it
          await removeSent();
        }
        await notifyClients({
          type: "SYNC_FAILED",
          id: action.id,
          status: response.status,
          lesson_slug: lesson_slug,
          retryable: inFlight,
          ...meta,
        });
      } else if (response.status === 409) {
        console.warn(
          `[ServiceWorker] Conflict detected on server for action ${action.id}`,
        );
        blocked.add(entity);
        const serverData = conflictBody || {};
        let localData = {};
        try {
          localData = JSON.parse(action.body);
        } catch (e) {}
        if (action.kind === "bookmark") {
          localData = { lesson_slug, bookmarked: action.method === "POST" };
        }

        // Kept in the queue with the server's answer before any page is told:
        // with every tab closed nobody receives the message, and the page that
        // opens next shows the conflict from the queue instead of sending the
        // request again.
        await editStored(db, action.id, (stored) =>
          sameRevision(stored, action)
            ? { put: { ...stored, state: "conflict", serverData } }
            : null,
        );
        await notifyClients({
          type: "SYNC_CONFLICT",
          id: action.id,
          lesson_slug: lesson_slug,
          serverData,
          localData,
          ...meta,
        });
      } else if (PERMANENT_REJECTIONS.includes(response.status)) {
        console.warn(
          `[ServiceWorker] Action ${action.id} was rejected for good (Status: ${response.status}). Dropping.`,
        );
        // Same policy as the page: replaying it would only be rejected again,
        // and it must not hold up the next write for the same lesson
        await removeSent();
        await notifyClients({
          type: "SYNC_FAILED",
          id: action.id,
          status: response.status,
          lesson_slug: lesson_slug,
          retryable: false,
          ...meta,
        });
      } else {
        console.warn(
          `[ServiceWorker] Action ${action.id} sync failed (Status: ${response.status}). Retrying later.`,
        );
        // Stays queued, but tell the page so the status UI can offer Retry
        blocked.add(entity);
        // A dead or refused token is for the page to sort out
        if (response.status !== 401 && response.status !== 403) retry = true;
        await notifyClients({
          type: "SYNC_FAILED",
          id: action.id,
          status: response.status,
          lesson_slug: lesson_slug,
          ...meta,
        });
      }
      // Its stored token is dead; the page replays with a fresh one
      if (response.status === 401) break;
    } catch (err) {
      console.error(
        `[ServiceWorker] Fetch error for action ${action.id}:`,
        err,
      );
      // Keep in queue and try again later on network error
      retry = true;
      break;
    }
  }
  db.close();
  return { retry };
}

// Background sync only retries when the event's promise rejects
async function syncProgressQueueForSyncEvent() {
  const { retry } = await syncProgressQueue();
  if (retry) throw new Error("Offline queue still has actions to replay");
}

// Overlapping triggers (page message + Background Sync event after a
// reconnect) share one run, so a queued submission is never replayed twice.
let quizSyncInFlight = null;

function syncQuizQueue() {
  if (!quizSyncInFlight) {
    quizSyncInFlight = runQuizSync().finally(() => {
      quizSyncInFlight = null;
    });
  }
  return quizSyncInFlight;
}

async function runQuizSync() {
  console.log("[ServiceWorker] Starting offline quiz submission sync...");
  let db;
  try {
    db = await openDB();
  } catch (err) {
    console.error("[ServiceWorker] Failed to open IndexedDB:", err);
    return;
  }

  let submissions;
  try {
    submissions = await getAllFromStore(db, QUIZ_STORE_NAME);
  } catch (err) {
    console.error("[ServiceWorker] Failed to read quiz submission queue:", err);
    return;
  }

  if (!submissions || submissions.length === 0) {
    console.log(
      "[ServiceWorker] Quiz submission queue is empty. Nothing to sync.",
    );
    return;
  }

  console.log(
    `[ServiceWorker] Found ${submissions.length} pending quiz submissions to sync.`,
  );

  for (const submission of submissions) {
    try {
      console.log(
        `[ServiceWorker] Replaying quiz submission: ${submission.id} to ${submission.url}`,
      );
      const response = await fetch(submission.url, {
        method: submission.method,
        headers: submission.headers,
        body: submission.body,
      });

      if (response.ok) {
        console.log(
          `[ServiceWorker] Quiz submission ${submission.id} synced successfully`,
        );
        await deleteFromStore(db, QUIZ_STORE_NAME, submission.id);
        await notifyClients({
          type: "QUIZ_SYNC_SUCCESS",
          id: submission.id,
          question_id: submission.question_id,
        });
      } else if (response.status === 401 || response.status >= 500) {
        // Transient failure (expired token / server trouble): keep queued so a
        // future sync event can retry it.
        console.warn(
          `[ServiceWorker] Quiz submission ${submission.id} failed transiently (Status: ${response.status}). Retrying later.`,
        );
      } else {
        // Permanent rejection (e.g. bad payload or 403 replay-protection from
        // an expired one-time nonce): drop it and let the client know.
        console.warn(
          `[ServiceWorker] Quiz submission ${submission.id} rejected permanently (Status: ${response.status}). Dropping.`,
        );
        await deleteFromStore(db, QUIZ_STORE_NAME, submission.id);
        await notifyClients({
          type: "QUIZ_SYNC_FAILED",
          id: submission.id,
          question_id: submission.question_id,
          status: response.status,
        });
      }
    } catch (err) {
      console.error(
        `[ServiceWorker] Fetch error for quiz submission ${submission.id}:`,
        err,
      );
      // Network still unavailable — leave queued for the next sync event.
    }
  }
}
