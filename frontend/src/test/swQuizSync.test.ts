import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("workbox-precaching", () => ({
  precacheAndRoute: vi.fn(),
  cleanupOutdatedCaches: vi.fn(),
}));
vi.mock("workbox-routing", () => ({ registerRoute: vi.fn() }));
vi.mock("workbox-strategies", () => ({
  CacheFirst: class {},
  NetworkFirst: class {},
  StaleWhileRevalidate: class {},
}));
vi.mock("workbox-expiration", () => ({ ExpirationPlugin: class {} }));

type Listener = (event: any) => void;
interface Submission {
  id: string;
  url: string;
  method: string;
  headers: Record<string, string>;
  body: string;
  question_id: string;
  queuedAt: number;
}

// In-memory stand-in for the pending_quiz_sync object store. Like real
// IndexedDB, getAll() returns records ordered by primary key.
const store = new Map<string, Submission>();
const swListeners: Record<string, Listener[]> = {};
const clientMessages: any[] = [];

function idbRequest<T>(result: T) {
  const req: any = { onsuccess: null, onerror: null, result };
  queueMicrotask(() => req.onsuccess?.({ target: { result } }));
  return req;
}

const fakeDb = {
  transaction: () => ({
    objectStore: () => ({
      getAll: () =>
        idbRequest([...store.values()].sort((a, b) => (a.id < b.id ? -1 : 1))),
      delete: (id: string) => {
        store.delete(id);
        return idbRequest(undefined);
      },
    }),
  }),
};

function queue(id: string, questionId: string): Submission {
  const sub: Submission = {
    id,
    url: "http://localhost:8000/api/progress/quiz-attempts/",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_id: questionId, nonce: id }),
    question_id: questionId,
    queuedAt: store.size,
  };
  store.set(id, sub);
  return sub;
}

// Fire a TRIGGER_QUIZ_SYNC message at the service worker and wait for it.
async function triggerSync() {
  const waits: Promise<unknown>[] = [];
  for (const cb of swListeners["message"] || []) {
    cb({
      data: { type: "TRIGGER_QUIZ_SYNC" },
      waitUntil: (p: Promise<unknown>) => waits.push(p),
    });
  }
  await Promise.all(waits);
}

// Fire a Background Sync "sync" event for the quiz tag and wait for it.
async function triggerSyncEvent() {
  const waits: Promise<unknown>[] = [];
  for (const cb of swListeners["sync"] || []) {
    cb({
      tag: "sync-quiz-progress",
      waitUntil: (p: Promise<unknown>) => waits.push(p),
    });
  }
  await Promise.all(waits);
}

const okResponse = { ok: true, status: 200 };
const status = (code: number) => ({ ok: false, status: code });

function postedNonces(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls.map(
    ([, init]) => JSON.parse((init as RequestInit).body as string).nonce,
  );
}

describe("service worker offline quiz replay", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    store.clear();
    clientMessages.length = 0;
    for (const key of Object.keys(swListeners)) delete swListeners[key];
    vi.spyOn(console, "log").mockImplementation(() => {});
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});

    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("indexedDB", {
      open: () => {
        const req: any = { onsuccess: null, onerror: null };
        queueMicrotask(() => req.onsuccess?.({ target: { result: fakeDb } }));
        return req;
      },
    });
    vi.stubGlobal("self", {
      __WB_MANIFEST: [],
      addEventListener: (type: string, cb: Listener) => {
        (swListeners[type] ||= []).push(cb);
      },
      skipWaiting: vi.fn(),
      clients: {
        claim: vi.fn(),
        matchAll: async () => [
          { postMessage: (m: unknown) => clientMessages.push(m) },
        ],
      },
    });

    vi.resetModules();
    await import("../sw.js");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("replays queued submissions in queue order and empties the store", async () => {
    queue("quiz-sync-q1-100", "q1");
    queue("quiz-sync-q2-200", "q2");
    queue("quiz-sync-q3-300", "q3");
    fetchMock.mockResolvedValue(okResponse);

    await triggerSync();

    expect(postedNonces(fetchMock)).toEqual([
      "quiz-sync-q1-100",
      "quiz-sync-q2-200",
      "quiz-sync-q3-300",
    ]);
    expect(store.size).toBe(0);
    expect(clientMessages.map((m) => [m.type, m.id])).toEqual([
      ["QUIZ_SYNC_SUCCESS", "quiz-sync-q1-100"],
      ["QUIZ_SYNC_SUCCESS", "quiz-sync-q2-200"],
      ["QUIZ_SYNC_SUCCESS", "quiz-sync-q3-300"],
    ]);
  });

  it("replays in primary-key (id) order, not queuedAt order", async () => {
    // Queued first, but its id sorts last. sw.js does not sort: it sends the
    // records in the order getAll() returns them (key order in real IDB), so
    // the earlier submission is sent second. This pins the current behaviour;
    // strict queue-time order would need a sort on queuedAt in sw.js.
    const first = queue("quiz-sync-q9-100", "q9");
    const second = queue("quiz-sync-q1-200", "q1");
    expect(first.queuedAt).toBeLessThan(second.queuedAt);
    fetchMock.mockResolvedValue(okResponse);

    await triggerSync();

    expect(postedNonces(fetchMock)).toEqual([
      "quiz-sync-q1-200",
      "quiz-sync-q9-100",
    ]);
  });

  it("keeps every item queued while the network is still down", async () => {
    queue("quiz-sync-q1-100", "q1");
    queue("quiz-sync-q2-200", "q2");
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    await triggerSync();

    expect([...store.keys()]).toEqual(["quiz-sync-q1-100", "quiz-sync-q2-200"]);
    expect(clientMessages).toHaveLength(0);
  });

  it("does not lose an item when a replay fails with a transient error", async () => {
    queue("quiz-sync-q1-100", "q1");
    queue("quiz-sync-q2-200", "q2");
    queue("quiz-sync-q3-300", "q3");
    fetchMock.mockImplementation(async (_url, init) =>
      JSON.parse((init as RequestInit).body as string).question_id === "q2"
        ? status(503)
        : okResponse,
    );

    await triggerSync();

    // Only the 503 item stays; the others are synced and reported.
    expect([...store.keys()]).toEqual(["quiz-sync-q2-200"]);
    expect(clientMessages.map((m) => m.type)).toEqual([
      "QUIZ_SYNC_SUCCESS",
      "QUIZ_SYNC_SUCCESS",
    ]);
  });

  it("keeps an item after a 401 so it can be retried with a fresh token", async () => {
    queue("quiz-sync-q1-100", "q1");
    fetchMock.mockResolvedValue(status(401));

    await triggerSync();

    expect(store.has("quiz-sync-q1-100")).toBe(true);
    expect(clientMessages).toHaveLength(0);
  });

  it("reports a permanently rejected item instead of dropping it silently", async () => {
    queue("quiz-sync-q1-100", "q1");
    fetchMock.mockResolvedValue(status(403));

    await triggerSync();

    expect(store.size).toBe(0);
    expect(clientMessages).toEqual([
      {
        type: "QUIZ_SYNC_FAILED",
        id: "quiz-sync-q1-100",
        question_id: "q1",
        status: 403,
      },
    ]);
  });

  it("retries a failed item on later reconnects and sends it successfully only once", async () => {
    queue("quiz-sync-q1-100", "q1");
    queue("quiz-sync-q2-200", "q2");

    // First reconnect: q1 goes through, q2 hits a server error.
    fetchMock.mockImplementation(async (_url, init) =>
      JSON.parse((init as RequestInit).body as string).question_id === "q2"
        ? status(500)
        : okResponse,
    );
    await triggerSync();
    expect([...store.keys()]).toEqual(["quiz-sync-q2-200"]);

    // Connection drops again: q2 stays queued.
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    await triggerSync();
    expect([...store.keys()]).toEqual(["quiz-sync-q2-200"]);

    // Next reconnect succeeds.
    fetchMock.mockResolvedValue(okResponse);
    await triggerSync();
    expect(store.size).toBe(0);

    // A further reconnect with an empty queue sends nothing.
    await triggerSync();

    expect(postedNonces(fetchMock)).toEqual([
      "quiz-sync-q1-100",
      "quiz-sync-q2-200",
      "quiz-sync-q2-200",
      "quiz-sync-q2-200",
    ]);
    const successes = clientMessages.filter(
      (m) => m.type === "QUIZ_SYNC_SUCCESS",
    );
    expect(successes.map((m) => m.id)).toEqual([
      "quiz-sync-q1-100",
      "quiz-sync-q2-200",
    ]);
  });

  it("does not send a submission twice when a sync event and a page message overlap", async () => {
    queue("quiz-sync-q1-100", "q1");
    queue("quiz-sync-q2-200", "q2");
    fetchMock.mockResolvedValue(okResponse);

    // Background Sync event and the page's TRIGGER_QUIZ_SYNC message arriving
    // together after a reconnect.
    await Promise.all([triggerSyncEvent(), triggerSync()]);

    expect(postedNonces(fetchMock)).toEqual([
      "quiz-sync-q1-100",
      "quiz-sync-q2-200",
    ]);
    expect(store.size).toBe(0);
  });

  it("does not send a submission twice when two page messages overlap", async () => {
    queue("quiz-sync-q1-100", "q1");
    queue("quiz-sync-q2-200", "q2");
    fetchMock.mockResolvedValue(okResponse);

    await Promise.all([triggerSync(), triggerSync()]);

    expect(postedNonces(fetchMock)).toEqual([
      "quiz-sync-q1-100",
      "quiz-sync-q2-200",
    ]);
    expect(store.size).toBe(0);
  });

  // Known limit, not asserted: a trigger that arrives mid-run joins that run,
  // so items queued after the run's getAll() are sent on the next trigger.
});
