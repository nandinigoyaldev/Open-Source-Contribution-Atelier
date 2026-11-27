import { openDB } from "./offlineDB";
import { eventBus } from "../core/events";
import { getAccessToken } from "./authToken";
import {
  crdtSyncEngine,
  type SyncState,
  type CRDTDeltaOperation,
} from "./crdtSyncEngine";

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
  /** What the server answered with when it flagged the conflict, so a reload can show it again. */
  serverData?: unknown;
  /**
   * Set right before the first send. From then on the server may have applied
   * the action without the answer reaching us, so it can no longer be treated
   * as "never sent".
   */
  dispatchedAt?: number;
  /** Timestamped CRDT delta operation recorded while offline. */
  delta?: CRDTDeltaOperation;
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

export interface PendingSyncItem {
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

/** A stored record that a newer build wrote: this build must leave it alone. */
export class QueueRecordLockedError extends Error {
  constructor(id: string) {
    super(`Queued item ${id} was written by a newer version of the app`);
    this.name = "QueueRecordLockedError";
  }
}

type QueueEdit = { put: QueuedAction } | { remove: true } | null;

/**
 * Reads the record with `id`, lets `decide` look at it and applies what it
 * returns, all in one IndexedDB transaction, so a check on the stored
 * revision cannot be overtaken by another write. Resolves once the transaction
 * has committed: `changed` says whether `decide` asked for a write, `record`
 * is what is stored now (undefined when absent or removed).
 */
function editQueued(
  db: IDBDatabase,
  id: string,
  decide: (stored: QueuedAction | undefined) => QueueEdit,
): Promise<{ changed: boolean; record: QueuedAction | undefined }> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction("sync-queue", "readwrite");
    const store = tx.objectStore("sync-queue");
    let changed = false;
    let record: QueuedAction | undefined;
    tx.oncomplete = () => resolve({ changed, record });
    tx.onerror = () => reject(tx.error ?? new Error("IndexedDB write failed"));
    tx.onabort = () => reject(tx.error ?? new Error("IndexedDB write aborted"));
    const read = store.get(id);
    read.onerror = () => reject(read.error);
    read.onsuccess = () => {
      const stored = read.result as QueuedAction | undefined;
      record = stored;
      try {
        if (stored && (stored.schemaVersion ?? 1) > QUEUE_SCHEMA_VERSION) {
          throw new QueueRecordLockedError(id);
        }
        const edit = decide(stored);
        if (!edit) return;
        changed = true;
        if ("put" in edit) {
          record = edit.put;
          store.put(edit.put);
        } else {
          record = undefined;
          store.delete(id);
        }
      } catch (err) {
        reject(err);
        try {
          tx.abort();
        } catch {
          // already finished
        }
      }
    };
  });
}

/** True when `stored` is the same revision (same idempotency key) as `action`. */
const sameRevision = (stored: QueuedAction | undefined, action: QueuedAction) =>
  !!stored && stored.idempotencyKey === action.idempotencyKey;

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
      (p) =>
        p.id !== entry.id &&
        !(
          p.id === undefined &&
          p.kind !== "bookmark" &&
          entry.kind !== "bookmark" &&
          p.lesson_slug === entry.lesson_slug
        ),
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
      // Committed before anything is sent, and only if nobody else upgraded the
      // record first (a second tab, the service worker): everyone then sends
      // the one key that is stored. If it cannot be stored the action stays
      // queued and is not sent now, a retry with another key could double-apply.
      try {
        const { record: committed } = await editQueued(
          db,
          action.id,
          (stored) =>
            stored && (stored.schemaVersion ?? 1) < QUEUE_SCHEMA_VERSION
              ? { put: action }
              : null,
        );
        if (committed) actions.push(committed);
      } catch (err) {
        console.error(`[OfflineQueue] Failed to upgrade ${action.id}:`, err);
      }
      continue;
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
  delta?: CRDTDeltaOperation,
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
    delta,
  };
}

/**
 * Stores the action at the end of the queue, replacing an older one with the
 * same id. Rejects when it could not be stored (IndexedDB failed, or a newer
 * build's record sits under the same id): callers must not report the action
 * as queued then.
 */
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
    throw err;
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

  let delta: CRDTDeltaOperation | undefined;
  try {
    delta = await crdtSyncEngine.recordDelta(
      id,
      [type || "action", slugOrId],
      bodyObj,
      "set",
      typeof bodyObj === "object" ? bodyObj : undefined,
    );
  } catch (err) {
    console.warn("[OfflineQueue] Failed to record CRDT delta operation:", err);
  }

  const action = newQueuedAction(
    id,
    finalUrl,
    method,
    headers,
    bodyStr,
    undefined,
    delta,
  );

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

  crdtSyncEngine.recalculateSyncState();

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
  let delta: CRDTDeltaOperation | undefined;
  try {
    delta = await crdtSyncEngine.recordDelta(
      id,
      ["progress", data.lesson_slug],
      {
        lesson_slug: data.lesson_slug,
        score: data.score,
        completed: data.completed,
      },
      "merge",
      { score: data.score, completed: data.completed },
    );
  } catch (err) {
    console.warn("[OfflineQueue] Failed to record CRDT progress delta:", err);
  }

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
    "progress",
    delta,
  );

  // 1. Save to IndexedDB
  await saveQueuedAction(action);

  // 2. Mirror to localStorage for synchronous UI queries. By action id, so a
  // bookmark entry for the same lesson does not hide it; an old entry saved
  // without an id for this lesson is replaced rather than shown twice.
  replacePendingEntry({
    id,
    kind: "progress",
    lesson_slug: data.lesson_slug,
    score: data.score ?? 100,
    completed: data.completed ?? true,
    timestamp: action.timestamp,
  });

  crdtSyncEngine.recalculateSyncState();

  // 3. Trigger Service Worker background sync
  await triggerBackgroundSync();
}

export const bookmarkActionId = (slug: string) => `bookmark-${slug}`;

export interface BookmarkQueueResult {
  /** "queued": waiting for the replay. "cancelled": it undid a queued change that was never sent. */
  outcome: "queued" | "cancelled";
  /** On "cancelled": the server id the undone removal carried, so the caller can restore that bookmark. */
  restoredId?: number;
}

function expectedIdOf(action: QueuedAction): number | undefined {
  const match = /[?&]expected_id=(\d+)(?:&|$)/.exec(action.url);
  return match ? Number(match[1]) : undefined;
}

/**
 * Queues a bookmark change made offline: `bookmarked` true saves the lesson,
 * false removes it. Flipping the same lesson back before the queue ran drops
 * the queued change instead, the server never saw it, so nothing is left to send.
 * If a replay already started sending the queued change its outcome is not
 * known (the server may have applied it and the answer got lost), so it is
 * replaced by the opposite change instead of cancelled: the replay then ends
 * with the state the user asked for either way.
 * `bookmarkId` is the server id of the bookmark being removed, when known.
 * Rejects when the change could not be stored.
 */
export async function queueBookmarkChange(
  slug: string,
  bookmarked: boolean,
  bookmarkId?: number,
): Promise<BookmarkQueueResult> {
  const id = bookmarkActionId(slug);
  let queued: QueuedAction | undefined;
  try {
    const db = await openDB();
    queued = (await loadQueue(db)).find((a) => a.id === id);
  } catch (err) {
    console.error("[OfflineQueue] Failed to read queued bookmark:", err);
  }

  if (
    queued &&
    !queued.dispatchedAt &&
    (queued.method.toUpperCase() === "POST") !== bookmarked
  ) {
    const db = await openDB();
    const target = queued;
    const { changed } = await editQueued(db, id, (stored) =>
      sameRevision(stored, target) && !stored?.dispatchedAt
        ? { remove: true }
        : null,
    );
    if (changed) {
      updatePendingMirror((p) => p.id === id, null);
      return { outcome: "cancelled", restoredId: expectedIdOf(target) };
    }
    // Sent or replaced in the meantime: queue the new change after it
  }

  const token = getAccessToken();
  const url = `${apiBase()}/progress/bookmarks/${slug}/`;

  let delta: CRDTDeltaOperation | undefined;
  try {
    delta = await crdtSyncEngine.recordDelta(
      id,
      ["bookmarks", slug],
      { bookmarked, bookmarkId },
      bookmarked ? "set" : "delete",
      { bookmarked, bookmarkId },
    );
  } catch (err) {
    console.warn("[OfflineQueue] Failed to record CRDT bookmark delta:", err);
  }

  const action = newQueuedAction(
    id,
    url,
    bookmarked ? "POST" : "DELETE",
    token ? { Authorization: `Bearer ${token}` } : {},
    "",
    "bookmark",
    delta,
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
  crdtSyncEngine.recalculateSyncState();
  await triggerBackgroundSync();
  return { outcome: "queued" };
}

/** A queued bookmark change taken out of the queue, kept so it can be put back. */
export interface DroppedBookmark {
  action: QueuedAction;
  mirror?: PendingSyncItem;
}

/**
 * Takes a queued bookmark change out of the queue, for when the same lesson is
 * toggled online. Hand the result to restoreQueuedBookmark() if that online
 * request does not go through, or the queued change is lost.
 */
export async function dropQueuedBookmark(
  slug: string,
): Promise<DroppedBookmark | undefined> {
  const id = bookmarkActionId(slug);
  let dropped: DroppedBookmark | undefined;
  try {
    const db = await openDB();
    const action = (await loadQueue(db)).find((a) => a.id === id);
    if (action && (await deleteQueuedAction(db, id, action))) {
      dropped = {
        action,
        mirror: readList<PendingSyncItem>(PENDING_KEY).find((p) => p.id === id),
      };
    }
  } catch (err) {
    // Includes a record from a newer build: it stays where it is
    console.error("[OfflineQueue] Failed to drop queued bookmark:", err);
    return undefined;
  }
  updatePendingMirror((p) => p.id === id, null);
  return dropped;
}

/** Puts back what dropQueuedBookmark() took out, unless a newer change was queued since. */
export async function restoreQueuedBookmark(dropped?: DroppedBookmark) {
  if (!dropped) return;
  try {
    const db = await openDB();
    const { changed } = await editQueued(db, dropped.action.id, (stored) =>
      stored ? null : { put: dropped.action },
    );
    if (changed && dropped.mirror) replacePendingEntry(dropped.mirror);
  } catch (err) {
    console.error("[OfflineQueue] Failed to restore queued bookmark:", err);
  }
}

/**
 * Bookmark changes still waiting in the queue, by lesson slug: true for a save,
 * false for a removal. A change that hit a conflict is left out, the server's
 * answer decides that one.
 */
export function getPendingBookmarkChanges(): Map<string, boolean> {
  const changes = new Map<string, boolean>();
  for (const p of readList<PendingSyncItem>(PENDING_KEY)) {
    if (
      p.kind === "bookmark" &&
      p.state !== "conflict" &&
      typeof p.bookmarked === "boolean"
    ) {
      changes.set(p.lesson_slug, p.bookmarked);
    }
  }
  return changes;
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

/** Conflicts the user has already been shown in this page, by action id. */
const announcedConflicts = new Set<string>();

/**
 * A conflict the service worker stored while no page was open is in the queue
 * with the server's answer. Shows it again when a page opens, without sending
 * the request again.
 */
function restoreStoredConflicts(actions: QueuedAction[]) {
  for (const action of actions) {
    if (
      action.state !== "conflict" ||
      action.serverData === undefined ||
      announcedConflicts.has(action.id)
    ) {
      continue;
    }
    announcedConflicts.add(action.id);
    const bodyObj = parseBody(action.body);
    const lesson_slug = actionSlug(action, bodyObj);
    const localData =
      action.kind === "bookmark"
        ? { lesson_slug, bookmarked: action.method.toUpperCase() === "POST" }
        : bodyObj;
    const patch = { state: "conflict" as const, serverData: action.serverData };
    if (
      readList<PendingSyncItem>(PENDING_KEY).some((p) => p.id === action.id)
    ) {
      updatePendingMirror((p) => p.id === action.id, patch);
    } else {
      replacePendingEntry({
        id: action.id,
        kind: action.kind,
        lesson_slug,
        ...(action.kind === "bookmark"
          ? { bookmarked: action.method.toUpperCase() === "POST" }
          : { score: bodyObj.score, completed: bodyObj.completed }),
        timestamp: action.timestamp,
        ...patch,
      });
    }
    eventBus.emit("sync:conflict", {
      id: action.id,
      kind: action.kind,
      lesson_slug,
      serverData: action.serverData,
      localData,
    });
  }
}

/** Applies one replay result to the local mirror, the results list and the event bus. */
function settleResult(
  result: SyncItemResult,
  localData?: unknown,
  /** The sent revision was replaced by a newer one: that one's entry stays. */
  superseded = false,
) {
  // By id; only old progress entries saved without one fall back to the lesson slug
  const matches = (p: PendingSyncItem) =>
    p.id !== undefined
      ? p.id === result.id
      : result.kind !== "bookmark" &&
        p.kind !== "bookmark" &&
        p.lesson_slug === result.lesson_slug;

  if (result.status === "synced" || result.status === "duplicate") {
    if (!superseded) updatePendingMirror(matches, null);
    recordSettledResult(result);
    // Emit sync success event instead of directly importing queryClient
    eventBus.emit("sync:success", {
      lesson_slug: result.lesson_slug,
      status: result.status,
      kind: result.kind,
    });
  } else if (result.status === "conflict") {
    announcedConflicts.add(result.id);
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

/** Stores `action` under its id. Refuses to overwrite a record a newer build wrote. */
async function writeQueuedAction(db: IDBDatabase, action: QueuedAction) {
  await editQueued(db, action.id, () => ({ put: action }));
}

/**
 * Removes the record with `id`. With `revision` (the action that was sent) it
 * only removes that revision: a newer write for the same id stays. Resolves
 * false when nothing was removed because the stored record is another revision.
 */
async function deleteQueuedAction(
  db: IDBDatabase,
  id: string,
  revision?: QueuedAction,
): Promise<boolean> {
  const { changed } = await editQueued(db, id, (stored) =>
    stored && (!revision || sameRevision(stored, revision))
      ? { remove: true }
      : null,
  );
  return changed;
}

/**
 * Headers for a replay. The Authorization saved at enqueue time may belong to
 * a token that was refreshed or revoked since, so the current one is sent: the
 * very `token` whose owner was checked for this dispatch.
 */
function replayHeaders(
  action: QueuedAction,
  token: string | null | undefined,
): Record<string, string> {
  const headers = withoutHeaders(action.headers, [
    "Authorization",
    "Idempotency-Key",
  ]);
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
  crdtSyncEngine.setSyncState("syncing");
  const db = await openDB();
  const actions = await loadQueue(db);

  const results: SyncItemResult[] = [];
  restoreStoredConflicts(actions);
  if (actions.length === 0) return results;

  console.log(
    `[OfflineQueue] Found ${actions.length} pending actions, starting sync...`,
  );

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
    // Read once per dispatch: the active account can change while an earlier
    // fetch is pending, and the owner check has to be about the token that is
    // actually sent. An action of a known owner is held when the owner of this
    // token cannot be told, and when it is another account: never send it as that one.
    const token = getAccessToken();
    if (action.owner && tokenOwner(token) !== action.owner) {
      blocked.add(entity);
      continue;
    }

    // Marked as sent before it goes out. If the answer is lost the server may
    // still have applied it, which a later opposite change has to know about.
    // Not sent at all when it was replaced since, or the mark cannot be stored.
    try {
      const { changed } = await editQueued(db, action.id, (stored) =>
        stored && sameRevision(stored, action)
          ? {
              put: {
                ...stored,
                dispatchedAt: stored.dispatchedAt ?? Date.now(),
              },
            }
          : null,
      );
      if (!changed) continue;
    } catch (err) {
      console.error(`[OfflineQueue] Failed to mark ${action.id} as sent:`, err);
      blocked.add(entity);
      continue;
    }

    let response: Response;
    try {
      response = await fetch(action.url, {
        method: action.method,
        headers: replayHeaders(action, token),
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
    let { status, retryable } = classifyQueuedReplay(
      action,
      response.status,
      responseBody,
    );

    // CRDT Automatic Three-Way Merge: attempt non-prompting reconciliation on 409 data conflicts
    if (
      status === "conflict" &&
      responseBody &&
      !isIdempotencyRejection(responseBody)
    ) {
      try {
        const baseData = await crdtSyncEngine.getBaseSnapshot(entity);
        const mergeResult = crdtSyncEngine.threeWayMerge(
          baseData,
          (localData || {}) as Record<string, any>,
          (responseBody || {}) as Record<string, any>,
        );

        if (!mergeResult.hasStructuralCollision) {
          console.log(
            `[OfflineQueue] Automatic 3-way merge succeeded without prompt for ${entity}:`,
            mergeResult.merged,
          );
          await crdtSyncEngine.saveBaseSnapshot(entity, mergeResult.merged);
          if (action.delta) {
            await crdtSyncEngine.markDeltasApplied([action.delta.id]);
          }
          status = "synced";
        } else {
          console.warn(
            `[OfflineQueue] Irreconcilable structural collision for ${entity}: ${mergeResult.collisionReason}`,
          );
        }
      } catch (mergeErr) {
        console.warn(
          `[OfflineQueue] Three-way merge error for ${entity}:`,
          mergeErr,
        );
      }
    }

    if (status === "synced" || status === "duplicate") {
      if (typeof localData === "object" && localData !== null) {
        crdtSyncEngine.saveBaseSnapshot(
          entity,
          localData as Record<string, any>,
        );
      }
      if (action.delta) {
        crdtSyncEngine.markDeltasApplied([action.delta.id]);
      }
    }

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

    // Only the revision that was sent is settled. If a newer write for the same
    // id replaced it while the request was out, that one stays queued and keeps
    // its own pending entry.
    let superseded = false;
    try {
      if (status === "conflict") {
        const { record } = await editQueued(db, action.id, (stored) =>
          stored && sameRevision(stored, action)
            ? {
                put: { ...stored, state: "conflict", serverData: responseBody },
              }
            : null,
        );
        superseded = !sameRevision(record, action);
      } else if (status !== "failed" || !retryable) {
        const { record } = await editQueued(db, action.id, (stored) =>
          sameRevision(stored, action) ? { remove: true } : null,
        );
        superseded = !!record && !sameRevision(record, action);
      } else {
        const { record } = await editQueued(db, action.id, () => null);
        superseded = !!record && !sameRevision(record, action);
      }
    } catch (err) {
      console.error(
        `[OfflineQueue] Failed to update action ${action.id}:`,
        err,
      );
    }

    if (superseded && (status === "conflict" || status === "failed")) {
      // Says nothing about the newer write: it is sent on the next run
      continue;
    }
    results.push(result);
    settleResult(result, localData, superseded);
    if (status === "failed" && retryable) blocked.add(entity);
    // Signed out or the token is dead: everything after it would get a 401 too.
    if (response.status === 401) break;
  }

  crdtSyncEngine.recalculateSyncState();
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
  if (!navigator.onLine) {
    crdtSyncEngine.setSyncState("offline-buffered");
    return [];
  }

  crdtSyncEngine.setSyncState("syncing");
  if (!syncInFlight) {
    syncInFlight = replayQueue()
      .catch((err) => {
        console.error("[OfflineQueue] Error during offline queue sync:", err);
        return [] as SyncItemResult[];
      })
      .finally(() => {
        syncInFlight = null;
        crdtSyncEngine.recalculateSyncState();
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
      const data = event.data;
      if (!data) return;
      const handle = (apply: (superseded: boolean) => void) => {
        // Without a revision to compare there is nothing to look up, apply it now
        if (typeof data.idempotencyKey !== "string") return apply(false);
        isSupersededRevision(data.id, data.idempotencyKey).then(apply);
      };
      if (data.type === "SYNC_SUCCESS") {
        console.log(`[OfflineQueue] SW synced ${data.id}`);
        handle((superseded) => {
          try {
            const result = swResult(data, false);
            settleResult(result, undefined, superseded);
            eventBus.emit("sync:results", [result]);
          } catch (e) {
            console.error(
              "[OfflineQueue] Error clearing sync'd item from localStorage",
              e,
            );
          }
        });
      } else if (data.type === "SYNC_CONFLICT") {
        const { id, serverData, localData } = data;
        // The SW only knows the slug for progress-sync-* ids
        const lesson_slug: string =
          data.lesson_slug ?? localData?.lesson_slug ?? serverData?.lesson_slug;
        handle((superseded) => {
          // Says nothing about the newer write that replaced it
          if (superseded) return;
          console.warn(
            `[OfflineQueue] Sync conflict detected for ${lesson_slug}`,
          );
          settleResult(
            {
              id,
              lesson_slug,
              kind: data.kind ?? kindFromId(id),
              status: "conflict",
              httpStatus: 409,
              serverData,
            },
            localData,
          );
          flagQueuedConflict(id, data.idempotencyKey, serverData);
        });
      } else if (data.type === "SYNC_FAILED") {
        handle((superseded) => {
          if (superseded) return;
          const result = swResult(data, true);
          settleResult(result);
          eventBus.emit("sync:results", [result]);
        });
      }
    });
  }
}

/** True when the queue holds another revision than the one a worker message is about. */
async function isSupersededRevision(
  id: unknown,
  key: string,
): Promise<boolean> {
  if (typeof id !== "string") return false;
  try {
    const db = await openDB();
    const { record } = await editQueued(db, id, () => null);
    return !!record && record.idempotencyKey !== key;
  } catch {
    return false;
  }
}

/** Keeps a conflicting item out of later replays until the user resolves it. */
async function flagQueuedConflict(
  id: string,
  key?: string,
  serverData?: unknown,
) {
  try {
    const db = await openDB();
    await editQueued(db, id, (stored) =>
      stored && (key === undefined || stored.idempotencyKey === key)
        ? { put: { ...stored, state: "conflict", serverData } }
        : null,
    );
  } catch (err) {
    console.error("[OfflineQueue] Failed to flag conflicting item:", err);
  }
}

/**
 * Removes a queued action once the user has resolved it. Rejects when the
 * record could not be removed: it is then still queued, so the caller must not
 * tell the user it is settled.
 */
export async function removeQueuedAction(id: string, lessonSlug: string) {
  try {
    const db = await openDB();
    await deleteQueuedAction(db, id);
  } catch (err) {
    console.error("[OfflineQueue] Error removing queued action:", err);
    throw err;
  }
  announcedConflicts.delete(id);
  // By id, so resolving a bookmark does not drop queued progress for the same
  // lesson (or the other way round); old progress entries without one go by
  // slug, but a bookmark resolution never takes those
  updatePendingMirror(
    (p) =>
      p.id !== undefined
        ? p.id === id
        : kindFromId(id) !== "bookmark" &&
          p.kind !== "bookmark" &&
          p.lesson_slug === lessonSlug,
    null,
  );
  console.log(`[OfflineQueue] Successfully removed queued action ${id}`);
}

export {
  crdtSyncEngine,
  type SyncState,
  type CRDTDeltaOperation,
} from "./crdtSyncEngine";

export function getSyncState(): SyncState {
  return crdtSyncEngine.getSyncState();
}
