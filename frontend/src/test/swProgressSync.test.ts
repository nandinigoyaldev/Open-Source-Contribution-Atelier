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

// In-memory stand-in for the sync-queue object store. Like real IndexedDB,
// getAll() is ordered by key and a transaction reports oncomplete once its
// requests were answered.
const store = new Map<string, any>();
const swListeners: Record<string, Listener[]> = {};
const clientMessages: any[] = [];
// What the store held at the moment each message reached a client
const storeAtMessage: Record<string, any>[] = [];

function fakeTransaction() {
  const tx: any = { oncomplete: null, onerror: null, onabort: null };
  let timer: ReturnType<typeof setTimeout> | undefined;
  const answer = (result: unknown) => {
    const req: any = { onsuccess: null, onerror: null, result };
    queueMicrotask(() => {
      req.onsuccess?.({ target: { result } });
      clearTimeout(timer);
      timer = setTimeout(() => tx.oncomplete?.(), 0);
    });
    return req;
  };
  tx.objectStore = () => ({
    getAll: () =>
      answer(
        [...store.entries()]
          .sort(([a], [b]) => (a < b ? -1 : 1))
          .map(([, v]) => v),
      ),
    get: (id: string) => answer(store.get(id)),
    put: (item: any) => {
      store.set(item.id, item);
      return answer(item.id);
    },
    delete: (id: string) => {
      store.delete(id);
      return answer(undefined);
    },
  });
  return tx;
}
const fakeDb = { transaction: () => fakeTransaction(), close: vi.fn() };

const API = "http://localhost:8000/api";
let seqCounter = 0;
function queue(
  id: string,
  kind: "progress" | "bookmark",
  extra: Record<string, unknown> = {},
) {
  const slug = id.replace(/^(progress-sync-|progress-|lesson-|bookmark-)/, "");
  const key = `key-${id}-${seqCounter}`;
  const record = {
    id,
    url:
      kind === "bookmark"
        ? `${API}/progress/bookmarks/${slug}/`
        : `${API}/progress/me/`,
    method: kind === "bookmark" ? "POST" : "POST",
    headers: { "Idempotency-Key": key },
    body: kind === "bookmark" ? "" : JSON.stringify({ lesson_slug: slug }),
    timestamp: seqCounter,
    schemaVersion: 2,
    seq: ++seqCounter,
    idempotencyKey: key,
    kind,
    ...extra,
  };
  store.set(id, record);
  return record;
}

async function runSyncEvent() {
  const waits: Promise<unknown>[] = [];
  for (const cb of swListeners["sync"] || []) {
    cb({
      tag: "sync-progress",
      waitUntil: (p: Promise<unknown>) => waits.push(p),
    });
  }
  return Promise.allSettled(waits);
}

async function runTriggerMessage() {
  const waits: Promise<unknown>[] = [];
  for (const cb of swListeners["message"] || []) {
    cb({
      data: { type: "TRIGGER_SYNC" },
      waitUntil: (p: Promise<unknown>) => waits.push(p),
    });
  }
  return Promise.allSettled(waits);
}

const reply = (status: number, body: unknown = {}) => ({
  ok: status >= 200 && status < 300,
  status,
  json: () => Promise.resolve(body),
  clone() {
    return this;
  },
});

describe("service worker offline progress replay", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    store.clear();
    seqCounter = 0;
    clientMessages.length = 0;
    storeAtMessage.length = 0;
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
          {
            postMessage: (m: unknown) => {
              clientMessages.push(m);
              storeAtMessage.push(Object.fromEntries(store));
            },
          },
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

  it("drops a write the server rejected for good and sends the next one for the lesson", async () => {
    queue("progress-sync-git-basics", "progress");
    queue("lesson-git-basics", "progress");
    fetchMock
      .mockResolvedValueOnce(reply(422))
      .mockResolvedValueOnce(reply(201));

    const [outcome] = await runSyncEvent();

    expect(outcome.status).toBe("fulfilled");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(store.size).toBe(0);
    expect(clientMessages[0]).toEqual(
      expect.objectContaining({
        type: "SYNC_FAILED",
        id: "progress-sync-git-basics",
        status: 422,
        retryable: false,
      }),
    );
  });

  it("drops a key the server will never accept, but keeps one that is still being processed", async () => {
    queue("progress-sync-a", "progress");
    queue("progress-sync-b", "progress");
    fetchMock
      .mockResolvedValueOnce(
        reply(409, {
          error: "Idempotency key already exists with a different request body",
          idempotency_key: "k",
        }),
      )
      .mockResolvedValueOnce(
        reply(409, {
          error:
            "A request with this idempotency key is currently being processed",
          idempotency_key: "k",
        }),
      );

    const [outcome] = await runSyncEvent();

    expect([...store.keys()]).toEqual(["progress-sync-b"]);
    expect(clientMessages.map((m) => m.retryable)).toEqual([false, true]);
    // b is still waiting on a temporary error, so the sync is tried again
    expect(outcome.status).toBe("rejected");
  });

  it("still counts a removal of a bookmark that is already gone as done", async () => {
    queue("bookmark-git-basics", "bookmark", { method: "DELETE" });
    fetchMock.mockResolvedValue(reply(404));

    await runSyncEvent();

    expect(store.size).toBe(0);
    expect(clientMessages[0]).toEqual(
      expect.objectContaining({ type: "SYNC_SUCCESS", status: 404 }),
    );
  });

  describe("asking the browser to try again", () => {
    it("rejects the sync event on a temporary server error and keeps the action", async () => {
      queue("progress-sync-git-basics", "progress");
      fetchMock.mockResolvedValue(reply(503));

      const [outcome] = await runSyncEvent();

      expect(outcome.status).toBe("rejected");
      expect(store.has("progress-sync-git-basics")).toBe(true);
    });

    it("rejects the sync event when the network is down", async () => {
      queue("progress-sync-git-basics", "progress");
      fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

      const [outcome] = await runSyncEvent();

      expect(outcome.status).toBe("rejected");
      expect(store.has("progress-sync-git-basics")).toBe(true);
    });

    it("does not ask for a retry when the token is dead, the page has to fix that", async () => {
      queue("progress-sync-git-basics", "progress");
      fetchMock.mockResolvedValue(reply(401));

      const [outcome] = await runSyncEvent();

      expect(outcome.status).toBe("fulfilled");
      expect(store.has("progress-sync-git-basics")).toBe(true);
    });

    it("does not reject a sync the page asked for", async () => {
      queue("progress-sync-git-basics", "progress");
      fetchMock.mockResolvedValue(reply(503));

      const [outcome] = await runTriggerMessage();

      expect(outcome.status).toBe("fulfilled");
    });

    it("is fine when everything went through", async () => {
      queue("progress-sync-git-basics", "progress");
      fetchMock.mockResolvedValue(reply(201));

      const [outcome] = await runSyncEvent();

      expect(outcome.status).toBe("fulfilled");
      expect(store.size).toBe(0);
    });
  });

  it("settles only the revision it sent", async () => {
    const sent = queue("progress-sync-x", "progress");
    fetchMock.mockImplementation(async () => {
      // The page replaced the action while the request was out
      store.set("progress-sync-x", {
        ...sent,
        idempotencyKey: "newer-key",
        headers: { "Idempotency-Key": "newer-key" },
      });
      return reply(201);
    });

    await runSyncEvent();

    expect(store.get("progress-sync-x").idempotencyKey).toBe("newer-key");
    expect(clientMessages[0]).toEqual(
      expect.objectContaining({
        type: "SYNC_SUCCESS",
        idempotencyKey: sent.idempotencyKey,
      }),
    );
  });

  it("stores a conflict with the server's answer before telling any page", async () => {
    queue("bookmark-git-basics", "bookmark", { method: "DELETE" });
    const serverData = { code: "bookmark_conflict", id: 9 };
    fetchMock.mockResolvedValue(reply(409, serverData));

    await runSyncEvent();

    expect(clientMessages[0].type).toBe("SYNC_CONFLICT");
    // already in the queue when the message went out, so closed tabs lose nothing
    expect(storeAtMessage[0]["bookmark-git-basics"]).toEqual(
      expect.objectContaining({ state: "conflict", serverData }),
    );
  });

  it("marks an action as sent before the request goes out", async () => {
    queue("progress-sync-git-basics", "progress");
    let markedWhenSent: unknown;
    fetchMock.mockImplementation(async () => {
      markedWhenSent = store.get("progress-sync-git-basics").dispatchedAt;
      return reply(503);
    });

    await runSyncEvent();

    expect(markedWhenSent).toEqual(expect.any(Number));
    expect(store.get("progress-sync-git-basics").dispatchedAt).toEqual(
      expect.any(Number),
    );
  });

  it("commits one key for a record from before keys existed and sends it", async () => {
    store.set("lesson-old", {
      id: "lesson-old",
      url: `${API}/progress/me/`,
      method: "POST",
      headers: { Authorization: "Bearer t" },
      body: JSON.stringify({ lesson_slug: "old" }),
      timestamp: 1,
    });
    fetchMock.mockResolvedValue(reply(503));

    await runSyncEvent();

    const stored = store.get("lesson-old");
    expect(stored.idempotencyKey).toEqual(expect.any(String));
    expect(stored.schemaVersion).toBe(2);
    expect(fetchMock.mock.calls[0][1].headers["Idempotency-Key"]).toBe(
      stored.idempotencyKey,
    );
  });

  it("leaves a record from a newer build alone", async () => {
    store.set("lesson-future", {
      id: "lesson-future",
      url: `${API}/progress/me/`,
      method: "POST",
      headers: {},
      body: "{}",
      timestamp: 1,
      schemaVersion: 3,
    });

    const [outcome] = await runSyncEvent();

    expect(outcome.status).toBe("fulfilled");
    expect(fetchMock).not.toHaveBeenCalled();
    expect(store.get("lesson-future").schemaVersion).toBe(3);
  });
});
