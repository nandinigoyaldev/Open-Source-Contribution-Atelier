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
const DB_VERSION = 3;

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
    event.waitUntil(syncProgressQueue());
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
    event.waitUntil(syncProgressQueue());
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
    const request = indexedDB.open(DB_NAME, DB_VERSION);
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
      resolve(event.target.result);
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

async function syncProgressQueue() {
  console.log("[ServiceWorker] Starting background queue sync...");
  let db;
  try {
    db = await openDB();
  } catch (err) {
    console.error("[ServiceWorker] Failed to open IndexedDB:", err);
    return;
  }

  let actions;
  try {
    actions = await getAllFromStore(db, STORE_NAME);
  } catch (err) {
    console.error("[ServiceWorker] Failed to read IndexedDB store:", err);
    return;
  }

  if (!actions || actions.length === 0) {
    console.log("[ServiceWorker] Queue is empty. Nothing to sync.");
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

      // Extract lesson slug if id starts with 'progress-sync-'
      let lesson_slug = null;
      if (action.id && action.id.startsWith("progress-sync-")) {
        lesson_slug = action.id.replace("progress-sync-", "");
      }

      if (response.ok || response.status === 400) {
        console.log(
          `[ServiceWorker] Action ${action.id} synced successfully (Status: ${response.status})`,
        );

        // Delete from IndexedDB
        await deleteFromStore(db, STORE_NAME, action.id);

        // Notify clients
        await notifyClients({
          type: "SYNC_SUCCESS",
          id: action.id,
          lesson_slug: lesson_slug,
          entity_type: action.entity_type,
          entity_id: action.entity_id,
        });
      } else if (response.status === 409) {
        console.warn(
          `[ServiceWorker] Conflict detected on server for action ${action.id}`,
        );
        // On 409 Conflict, notify client of the conflict to open resolution UI, do not delete from store yet
        const serverData = await response
          .clone()
          .json()
          .catch(() => ({}));
        let localData = {};
        try {
          localData = JSON.parse(action.body);
        } catch (e) {}

        await notifyClients({
          type: "SYNC_CONFLICT",
          id: action.id,
          lesson_slug: lesson_slug,
          serverData,
          localData,
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
