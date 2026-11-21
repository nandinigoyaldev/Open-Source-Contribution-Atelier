import { openDB } from "./offlineDB";
import { eventBus } from "../core/events";
import { getAccessToken } from "./authToken";

/**
 * Shape version of the records in the "sync-queue" store. Bump it when
 * QueuedAction changes and teach upgradeQueuedAction() to read the old shape.
 *   1: id, url, method, headers, body, timestamp
 *   2: adds schemaVersion, seq, idempotencyKey, kind, owner
 */
export const QUEUE_SCHEMA_VERSION = 2;

export type QueueKind =
  | "progress"
  | "bookmark"
  | "quiz"
  | "code_submission"
  | "other";

export interface QueuedAction {
  /** `${type}-${slug}`: a newer write for the same thing replaces the older one. */
  id: string;
  url: string;
  method: string;
  headers: Record<string, string>;
  body: string;
  timestamp: number;
  schemaVersion?: number;
  /** Enqueue order, taken from the stored cursor. Replay goes by this, not by id. */
  seq?: number;
  /** Sent as Idempotency-Key, so a replay the server already applied is not applied twice. */
  idempotencyKey?: string;
  kind?: QueueKind;
  /** user_id of the token the action was queued with. */
  owner?: string;
  /** Set once a replay hit a server conflict; such items are not replayed again. */
  state?: "conflict";
}

/** Result of replaying one queued item. "failed" is the only retryable state. */
export type SyncItemStatus = "synced" | "duplicate" | "conflict" | "failed";

export interface SyncItemResult {
  id: string;
  lesson_slug: string;
  status: SyncItemStatus;
  kind?: QueueKind;
  httpStatus?: number;
  /** Only for "failed": false when the server rejected the item for good. */
  retryable?: boolean;
  /** Only for "conflict": what the server has for this lesson. */
  serverData?: unknown;
}

interface PendingSyncItem {
  id?: string;
  kind?: QueueKind;
  lesson_slug: string;
  score?: number;
  completed?: boolean;
  /** Bookmarks only: what this device wants, true for saved. */
  bookmarked?: boolean;
  timestamp: number;
  /** "failed": last replay hit a temporary error. "conflict": needs the user. */
  state?: "failed" | "conflict";
  serverData?: unknown;
}

const PENDING_KEY = "atelier_pending_sync";
const RESULTS_KEY = "atelier_sync_results";
/** Where the next enqueue position lives, so the order survives a reload. */
const CURSOR_KEY = "atelier_sync_cursor";
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

/** The 409 the Idempotency-Key layer answers with, as opposed to a data conflict. */
function isIdempotencyRejection(body: unknown): body is { error?: unknown } {
  return (
    typeof body === "object" &&
    body !== null &&
    "idempotency_key" in body &&
    !("code" in body)
  );
}

/**
 * classifyReplayStatus() plus what depends on the endpoint: a bookmark removal
 * that 404s was already removed, and a 409 about the idempotency key itself is
 * not a conflict with newer data.
 */
export function classifyQueuedReplay(
  action: { kind?: QueueKind; method?: string },
  httpStatus: number,
  body?: unknown,
): { status: SyncItemStatus; retryable: boolean } {
  if (httpStatus === 409 && isIdempotencyRejection(body)) {
    // Another tab or the service worker is sending the same key right now:
    // leave it queued. Any other key error will not go away on a retry.
    const inFlight = /being processed/i.test(String(body.error ?? ""));
    return { status: "failed", retryable: inFlight };
  }
  const method = (action.method ?? "").toUpperCase();
  if (action.kind === "bookmark") {
    if (method === "DELETE" && httpStatus === 404) {
      return { status: "duplicate", retryable: false };
    }
    // Like /progress/me/: 201 saved it, 200 means it was already saved
    return classifyReplayStatus(httpStatus, method === "POST");
  }
  return classifyReplayStatus(httpStatus, action.kind === "progress");
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

/** Puts `entry` in the mirror in place of an older entry with the same id. */
function replacePendingEntry(entry: PendingSyncItem) {
  try {
    const pending = readList<PendingSyncItem>(PENDING_KEY).filter(
      (p) => p.id !== entry.id,
    );
    pending.push(entry);
    localStorage.setItem(PENDING_KEY, JSON.stringify(pending));
  } catch (err) {
    console.error("[OfflineQueue] Failed to mirror to localStorage:", err);
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

function readCursor(): { version: number; nextSeq: number } {
  try {
    const parsed = JSON.parse(localStorage.getItem(CURSOR_KEY) || "null");
    if (parsed && Number.isInteger(parsed.nextSeq) && parsed.nextSeq > 0) {
      return parsed;
    }
  } catch {
    // unreadable, start over below
  }
  return { version: QUEUE_SCHEMA_VERSION, nextSeq: 1 };
}

/**
 * Hands out the next enqueue position and moves the cursor past it. `atLeast`
 * is one past the highest seq still queued, so a cursor lost with cleared
 * storage can never hand out a position behind a queued action.
 */
function takeSeq(atLeast: number): number {
  const seq = Math.max(readCursor().nextSeq, atLeast);
  try {
    localStorage.setItem(
      CURSOR_KEY,
      JSON.stringify({ version: QUEUE_SCHEMA_VERSION, nextSeq: seq + 1 }),
    );
  } catch {
    // storage unavailable: atLeast still keeps the order for this queue
  }
  return seq;
}

function newIdempotencyKey(): string {
  const c = globalThis.crypto;
  if (c && typeof c.randomUUID === "function") return c.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

function findHeader(
  headers: Record<string, string> | undefined,
  name: string,
): string | undefined {
  const wanted = name.toLowerCase();
  for (const [key, value] of Object.entries(headers ?? {})) {
    if (key.toLowerCase() === wanted) return value;
  }
  return undefined;
}

function withoutHeaders(
  headers: Record<string, string> | undefined,
  names: string[],
): Record<string, string> {
  const drop = names.map((n) => n.toLowerCase());
  return Object.fromEntries(
    Object.entries(headers ?? {}).filter(
      ([key]) => !drop.includes(key.toLowerCase()),
    ),
  );
}

/** user_id claim of a JWT access token (or "Bearer <token>"), undefined when unreadable. */
export function tokenOwner(token?: string | null): string | undefined {
  const payload = token?.replace(/^Bearer\s+/i, "").split(".")[1];
  if (!payload) return undefined;
  try {
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const claims = JSON.parse(
      atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, "=")),
    );
    const id = claims?.user_id ?? claims?.sub;
    return id === undefined || id === null ? undefined : String(id);
  } catch {
    return undefined;
  }
}

function kindFromUrl(url: string): QueueKind {
  if (url.includes("/progress/me/")) return "progress";
  if (url.includes("/progress/bookmarks/")) return "bookmark";
  if (url.includes("/progress/quiz-attempts/")) return "quiz";
  if (url.includes("/progress/code-submissions/")) return "code_submission";
  return "other";
}

function kindFromId(id: unknown): QueueKind | undefined {
  if (typeof id !== "string") return undefined;
  if (id.startsWith("bookmark-")) return "bookmark";
  if (id.startsWith("progress-") || id.startsWith("lesson-")) return "progress";
  return undefined;
}

const SLUG_PREFIXES = ["bookmark-", "progress-sync-", "progress-", "lesson-"];

function slugFromId(id: string): string {
  const prefix = SLUG_PREFIXES.find((p) => id.startsWith(p));
  return prefix ? id.slice(prefix.length) : id;
}

/**
 * Brings a stored record up to QUEUE_SCHEMA_VERSION. Returns null for anything
 * this build cannot read, a record from a newer build after a rollback
 * included: that one stays in the store untouched for the build that wrote it.
 */
export function upgradeQueuedAction(record: unknown): QueuedAction | null {
  if (!record || typeof record !== "object") return null;
  const action = record as QueuedAction;
  if (typeof action.id !== "string" || typeof action.url !== "string") {
    return null;
  }
  const version = action.schemaVersion ?? 1;
  if (version > QUEUE_SCHEMA_VERSION) return null;
  if (version === QUEUE_SCHEMA_VERSION) return action;

  // v1 had no order and no key. Everything v1 was queued before any v2 action,
  // so seq 0 replays them first, by timestamp among themselves.
  const idempotencyKey =
    findHeader(action.headers, "Idempotency-Key") ?? newIdempotencyKey();
  return {
    ...action,
    headers: {
      ...withoutHeaders(action.headers, ["Idempotency-Key"]),
      "Idempotency-Key": idempotencyKey,
    },
    schemaVersion: QUEUE_SCHEMA_VERSION,
    seq: 0,
    idempotencyKey,
    kind: kindFromUrl(action.url),
    owner: tokenOwner(findHeader(action.headers, "Authorization")),
  };
}

function replayOrder(a: QueuedAction, b: QueuedAction): number {
  return (
    (a.seq ?? 0) - (b.seq ?? 0) ||
    (a.timestamp ?? 0) - (b.timestamp ?? 0) ||
    (a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
  );
}

/**
 * Every queued action this build can replay, upgraded to the current schema
 * and sorted by enqueue order. getAll() alone returns them in key order, which
 * for `${type}-${slug}` ids has nothing to do with when they were queued.
 */
async function loadQueue(db: IDBDatabase): Promise<QueuedAction[]> {
  const tx = db.transaction("sync-queue", "readonly");
  const store = tx.objectStore("sync-queue");
  const records: unknown[] = await new Promise((resolve, reject) => {
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result ?? []);
    req.onerror = () => reject(req.error);
  });

  const actions: QueuedAction[] = [];
  for (const record of records) {
    const action = upgradeQueuedAction(record);
    if (!action) {
      console.warn(
        "[OfflineQueue] Skipping a queued item this version cannot read",
      );
      continue;
    }
    if (action !== record) {
      // Stored right away so the new idempotency key stays the same on retries
      try {
        await writeQueuedAction(db, action);
      } catch (err) {
        console.error(`[OfflineQueue] Failed to upgrade ${action.id}:`, err);
      }
    }
    actions.push(action);
  }
  return actions.sort(replayOrder);
}

function newQueuedAction(
  id: string,
  url: string,
  method: string,
  headers: Record<string, string>,
  body: string,
  kind: QueueKind = kindFromUrl(url),
): QueuedAction {
  const idempotencyKey = newIdempotencyKey();
  return {
    id,
    url,
    method,
    // The key goes in the stored headers too, the service worker sends those as they are
    headers: {
      ...withoutHeaders(headers, ["Idempotency-Key"]),
      "Idempotency-Key": idempotencyKey,
    },
    body,
    timestamp: Date.now(),
    schemaVersion: QUEUE_SCHEMA_VERSION,
    idempotencyKey,
    kind,
    owner: tokenOwner(findHeader(headers, "Authorization") ?? getAccessToken()),
  };
}

/** Stores the action at the end of the queue, replacing an older one with the same id. */
async function saveQueuedAction(action: QueuedAction) {
  try {
    const db = await openDB();
    const queued = await loadQueue(db);
    const lastSeq = queued.reduce((max, a) => Math.max(max, a.seq ?? 0), 0);
    action.seq = takeSeq(lastSeq + 1);
    await writeQueuedAction(db, action);
    console.log(`[OfflineQueue] Queued action ${action.id} (#${action.seq})`);
  } catch (err) {
    console.error("[OfflineQueue] Failed to save action to IndexedDB:", err);
  }
}

async function triggerBackgroundSync() {
  if (!("serviceWorker" in navigator)) return;
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

function apiBase(): string {
  return import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
}

export async function enqueueOfflineAction(
  url: string,
  method: string,
  headers: Record<string, string>,
  body: Record<string, any> | string,
  type: string,
  slugOrId: string,
): Promise<string> {
  const id = `${type}-${slugOrId}`;
  const finalUrl = url.startsWith("http") ? url : `${apiBase()}${url}`;

  const bodyStr = typeof body === "string" ? body : JSON.stringify(body);
  const bodyObj = typeof body === "string" ? parseBody(body) : body;

  const action = newQueuedAction(id, finalUrl, method, headers, bodyStr);

  // 1. Save to IndexedDB
  await saveQueuedAction(action);

  // 2. Mirror to localStorage
  replacePendingEntry({
    id,
    kind: action.kind,
    lesson_slug: bodyObj.lesson_slug || slugOrId,
    score: bodyObj.score ?? 100,
    completed: bodyObj.completed ?? true,
    timestamp: action.timestamp,
  });

  // 3. Trigger Service Worker background sync
  await triggerBackgroundSync();
  return id;
}

export async function queueProgressSync(data: {
  lesson_slug: string;
  score?: number;
  completed?: boolean;
  headers: Record<string, string>;
}) {
  const id = `progress-sync-${data.lesson_slug}`;
  const action = newQueuedAction(
    id,
    `${apiBase()}/progress/me/`,
    "POST",
    data.headers,
    JSON.stringify({
      lesson_slug: data.lesson_slug,
      score: data.score,
      completed: data.completed,
    }),
  );

  // 1. Save to IndexedDB
  await saveQueuedAction(action);

  // 2. Save/mirror to localStorage for synchronous UI queries
  try {
    const pending = readList<PendingSyncItem>(PENDING_KEY);
    const exists = pending.some((p) => p.lesson_slug === data.lesson_slug);
    if (!exists) {
      pending.push({
        id,
        kind: "progress",
        lesson_slug: data.lesson_slug,
        score: data.score ?? 100,
        completed: data.completed ?? true,
        timestamp: action.timestamp,
      });
      localStorage.setItem(PENDING_KEY, JSON.stringify(pending));
    }
  } catch (err) {
    console.error("[OfflineQueue] Failed to mirror to localStorage:", err);
  }

  // 3. Trigger Service Worker background sync
  await triggerBackgroundSync();
}

export const bookmarkActionId = (slug: string) => `bookmark-${slug}`;

/**
 * Queues a bookmark change made offline: `bookmarked` true saves the lesson,
 * false removes it. Flipping the same lesson back before the queue ran drops
 * the queued change instead, the server never saw it, so nothing is left to send.
 * `bookmarkId` is the server id of the bookmark being removed, when known.
 */
export async function queueBookmarkChange(
  slug: string,
  bookmarked: boolean,
  bookmarkId?: number,
): Promise<"queued" | "cancelled"> {
  const id = bookmarkActionId(slug);
  try {
    const db = await openDB();
    const queued = (await loadQueue(db)).find((a) => a.id === id);
    if (queued && (queued.method.toUpperCase() === "POST") !== bookmarked) {
      await deleteQueuedAction(db, id);
      updatePendingMirror((p) => p.id === id, null);
      return "cancelled";
    }
  } catch (err) {
    console.error("[OfflineQueue] Failed to read queued bookmark:", err);
  }

  const token = getAccessToken();
  const url = `${apiBase()}/progress/bookmarks/${slug}/`;
  const action = newQueuedAction(
    id,
    url,
    bookmarked ? "POST" : "DELETE",
    token ? { Authorization: `Bearer ${token}` } : {},
    "",
    "bookmark",
  );
  if (!bookmarked && typeof bookmarkId === "number") {
    // If the lesson was bookmarked again since (another tab or device) its id
    // changed, and the server answers 409 instead of deleting the newer one
    action.url = `${url}?expected_id=${bookmarkId}`;
  }

  await saveQueuedAction(action);
  replacePendingEntry({
    id,
    kind: "bookmark",
    lesson_slug: slug,
    bookmarked,
    timestamp: action.timestamp,
  });
  await triggerBackgroundSync();
  return "queued";
}

/** Drops a queued bookmark change, for when the same lesson is toggled online. */
export async function dropQueuedBookmark(slug: string) {
  const id = bookmarkActionId(slug);
  try {
    const db = await openDB();
    await deleteQueuedAction(db, id);
  } catch (err) {
    console.error("[OfflineQueue] Failed to drop queued bookmark:", err);
  }
  updatePendingMirror((p) => p.id === id, null);
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
  // By id; only old entries saved without one fall back to the lesson slug
  const matches = (p: PendingSyncItem) =>
    p.id !== undefined
      ? p.id === result.id
      : result.kind !== "bookmark" && p.lesson_slug === result.lesson_slug;

  if (result.status === "synced" || result.status === "duplicate") {
    updatePendingMirror(matches, null);
    recordSettledResult(result);
    // Emit sync success event instead of directly importing queryClient
    eventBus.emit("sync:success", {
      lesson_slug: result.lesson_slug,
      status: result.status,
      kind: result.kind,
    });
  } else if (result.status === "conflict") {
    updatePendingMirror(matches, {
      state: "conflict",
      serverData: result.serverData,
    });
    eventBus.emit("sync:conflict", {
      id: result.id,
      kind: result.kind,
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
      (p) => p.kind === "bookmark" || p.lesson_slug !== lesson_slug,
    );
    pending.push({
      id,
      kind: "progress",
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
  eventBus.emit("sync:conflict", {
    id,
    kind: "progress",
    lesson_slug,
    serverData,
    localData,
  });
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

/**
 * Headers for a replay. The Authorization saved at enqueue time may belong to
 * a token that was refreshed or revoked since, so the current one is sent.
 */
function replayHeaders(action: QueuedAction): Record<string, string> {
  const headers = withoutHeaders(action.headers, [
    "Authorization",
    "Idempotency-Key",
  ]);
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (action.idempotencyKey) headers["Idempotency-Key"] = action.idempotencyKey;
  return headers;
}

function actionSlug(
  action: QueuedAction,
  bodyObj: Record<string, any>,
): string {
  if (typeof bodyObj.lesson_slug === "string") return bodyObj.lesson_slug;
  return action.kind === "bookmark" ? slugFromId(action.id) : action.id;
}

/** Actions with the same key change the same server row and must land in order. */
function entityKey(action: QueuedAction, slug: string): string {
  return action.kind === "progress" || action.kind === "bookmark"
    ? `${action.kind}:${slug}`
    : action.id;
}

async function replayQueue(): Promise<SyncItemResult[]> {
  const db = await openDB();
  const actions = await loadQueue(db);

  const results: SyncItemResult[] = [];
  if (actions.length === 0) return results;

  console.log(
    `[OfflineQueue] Found ${actions.length} pending actions, starting sync...`,
  );

  const currentOwner = tokenOwner(getAccessToken());
  // Rows with an older action still waiting: a newer one must not overtake it.
  const blocked = new Set<string>();

  for (const action of actions) {
    const bodyObj = parseBody(action.body);
    const lesson_slug = actionSlug(action, bodyObj);
    const entity = entityKey(action, lesson_slug);
    const localData =
      action.kind === "bookmark"
        ? { lesson_slug, bookmarked: action.method.toUpperCase() === "POST" }
        : bodyObj;

    // Waiting for the user to pick a side, replaying would only 409 again.
    if (action.state === "conflict") {
      blocked.add(entity);
      continue;
    }
    if (blocked.has(entity)) continue;
    // Queued by another account on this browser: never send it as this one.
    if (action.owner && currentOwner && action.owner !== currentOwner) {
      blocked.add(entity);
      continue;
    }

    let response: Response;
    try {
      response = await fetch(action.url, {
        method: action.method,
        headers: replayHeaders(action),
        body: action.body || undefined,
      });
    } catch (err) {
      console.error(`[OfflineQueue] Error syncing action ${action.id}:`, err);
      const result: SyncItemResult = {
        id: action.id,
        lesson_slug,
        kind: action.kind,
        status: "failed",
        retryable: true,
      };
      results.push(result);
      settleResult(result);
      break; // Stop and retry later on network error
    }

    const responseBody =
      response.status === 409
        ? await response.json().catch(() => ({}))
        : undefined;
    const { status, retryable } = classifyQueuedReplay(
      action,
      response.status,
      responseBody,
    );
    const result: SyncItemResult = {
      id: action.id,
      lesson_slug,
      kind: action.kind,
      status,
      httpStatus: response.status,
    };
    if (status === "failed") {
      result.retryable = retryable;
      console.warn(
        `[OfflineQueue] Action ${action.id} returned status ${response.status}.`,
      );
    }
    if (status === "conflict") result.serverData = responseBody;

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
    settleResult(result, localData);
    if (status === "failed" && retryable) blocked.add(entity);
    // Signed out or the token is dead: everything after it would get a 401 too.
    if (response.status === 401) break;
  }

  if (results.length > 0) eventBus.emit("sync:results", results);
  return results;
}

/**
 * Replays the queue in enqueue order and returns one result per item it
 * attempted. Items that failed with a temporary error stay queued (call it
 * again to retry them), conflicts wait for the user and are skipped, and so is
 * anything queued after them for the same lesson.
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

/** What the service worker reported for one item, classified like a page replay. */
function swResult(
  data: Record<string, any>,
  forceFailed: boolean,
): SyncItemResult {
  const { id, status: httpStatus } = data;
  const kind: QueueKind | undefined = data.kind ?? kindFromId(id);
  const lesson_slug: string =
    data.lesson_slug ?? (typeof id === "string" ? slugFromId(id) : id);
  const classified =
    typeof httpStatus === "number"
      ? classifyQueuedReplay({ kind, method: data.method }, httpStatus)
      : { status: "synced" as SyncItemStatus, retryable: false };
  const result: SyncItemResult = {
    id,
    lesson_slug,
    kind,
    status: forceFailed ? "failed" : classified.status,
    httpStatus,
  };
  if (result.status === "failed") {
    result.retryable =
      typeof data.retryable === "boolean"
        ? data.retryable
        : classified.retryable;
  }
  return result;
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
        console.log(`[OfflineQueue] SW synced ${event.data.id}`);
        try {
          const result = swResult(event.data, false);
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
          {
            id,
            lesson_slug,
            kind: event.data.kind ?? kindFromId(id),
            status: "conflict",
            httpStatus: 409,
            serverData,
          },
          localData,
        );
        flagQueuedConflict(id);
      } else if (event.data && event.data.type === "SYNC_FAILED") {
        const result = swResult(event.data, true);
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
    await deleteQueuedAction(db, id);
    // By id, so resolving a bookmark does not drop queued progress for the
    // same lesson (or the other way round); old entries without one by slug
    updatePendingMirror(
      (p) => (p.id !== undefined ? p.id === id : p.lesson_slug === lessonSlug),
      null,
    );
    console.log(`[OfflineQueue] Successfully removed queued action ${id}`);
  } catch (err) {
    console.error("[OfflineQueue] Error removing queued action:", err);
  }
}
