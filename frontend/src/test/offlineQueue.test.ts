import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  classifyQueuedReplay,
  classifyReplayStatus,
  dropQueuedBookmark,
  enqueueOfflineAction,
  getPendingBookmarkChanges,
  getSyncResults,
  QUEUE_SCHEMA_VERSION,
  QueueRecordLockedError,
  queueBookmarkChange,
  queueProgressSync,
  removeQueuedAction,
  restoreQueuedBookmark,
  reportProgressConflict,
  syncOfflineQueue,
  tokenOwner,
} from "../lib/offlineQueue";
import { queryClient } from "../lib/queryClient";
import { eventBus } from "../core/events";

interface MockIDBRequest {
  onsuccess: ((event: Event) => void) | null;
  onerror: ((event: Event) => void) | null;
  result?: unknown;
  error?: unknown;
}

// Mock IndexedDB. Every transaction is its own object: it reports oncomplete
// once its requests have been answered, like a real one that committed.
const mockStore = new Map();
const mockFail = { put: false, delete: false };
// Lets a test have get() answer with a record another writer just stored
const mockGetOverride = new Map();
const mockIDBDatabase = {
  transaction: vi.fn().mockImplementation(() => {
    const tx: {
      oncomplete: (() => void) | null;
      onerror: (() => void) | null;
      onabort: (() => void) | null;
      error?: unknown;
      abort: () => void;
      objectStore: () => unknown;
    } = {
      oncomplete: null,
      onerror: null,
      onabort: null,
      abort: () => {},
      objectStore: () => store,
    };
    let completeTimer: ReturnType<typeof setTimeout> | undefined;
    const answer = (result: unknown, fail = false) => {
      const req: MockIDBRequest = {
        onsuccess: null,
        onerror: null,
        result,
      };
      setTimeout(() => {
        if (fail) {
          tx.error = new Error("QuotaExceededError");
          tx.onabort?.();
          return;
        }
        req.onsuccess?.({ target: { result } } as unknown as Event);
        // Writes made by the handler land before the commit is reported
        clearTimeout(completeTimer);
        completeTimer = setTimeout(() => tx.oncomplete?.(), 0);
      }, 0);
      return req;
    };
    const store = {
      put: vi.fn().mockImplementation((item) => {
        if (mockFail.put) return answer(undefined, true);
        mockStore.set(item.id, item);
        return answer(item.id);
      }),
      get: vi
        .fn()
        .mockImplementation((id) =>
          answer(mockGetOverride.get(id) ?? mockStore.get(id)),
        ),
      getAll: vi.fn().mockImplementation(() => {
        // Like a real object store: records come back in key order
        const resultVal = Array.from(mockStore.keys())
          .sort()
          .map((key) => mockStore.get(key));
        return answer(resultVal);
      }),
      delete: vi.fn().mockImplementation((id) => {
        if (mockFail.delete) return answer(undefined, true);
        mockStore.delete(id);
        return answer(undefined);
      }),
    };
    return tx;
  }),
};

globalThis.indexedDB = {
  open: vi.fn().mockReturnValue({
    onsuccess: null,
    onerror: null,
    onupgradeneeded: null,
    get result() {
      return mockIDBDatabase;
    },
  }),
} as unknown as typeof globalThis.indexedDB;

// Mock queryClient invalidation
vi.spyOn(queryClient, "invalidateQueries").mockImplementation(async () => {});

describe("Offline Progress Queue", () => {
  beforeEach(() => {
    // The fake IndexedDB answers through setTimeout, which setup.ts's fake
    // timers would never fire
    // eslint-disable-next-line no-restricted-syntax -- the IDB mock needs real timers
    vi.useRealTimers();
    mockStore.clear();
    mockFail.put = false;
    mockFail.delete = false;
    mockGetOverride.clear();
    localStorage.clear();
    vi.clearAllMocks();

    // Mock global fetch
    globalThis.fetch = vi.fn();

    // Mock navigator online
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: true,
      writable: true,
    });

    // Setup indexedDB open mock success trigger
    const openReq: MockIDBRequest = {
      onsuccess: null,
      onerror: null,
    };
    (globalThis.indexedDB.open as ReturnType<typeof vi.fn>).mockImplementation(
      () => {
        setTimeout(() => {
          if (openReq.onsuccess)
            openReq.onsuccess({
              target: { result: mockIDBDatabase },
            } as unknown as Event);
        }, 0);
        return openReq;
      },
    );
  });

  it("should queue a progress update in IndexedDB and localStorage when offline", async () => {
    Object.defineProperty(navigator, "onLine", {
      value: false,
      writable: true,
    });

    await enqueueOfflineAction(
      "/progress/me/",
      "POST",
      { Authorization: "Bearer test-token" },
      { lesson_slug: "git-basics", score: 20, completed: true },
      "lesson",
      "git-basics",
    );

    // Check localStorage
    const pendingLocal = JSON.parse(
      localStorage.getItem("atelier_pending_sync") || "[]",
    );
    expect(pendingLocal).toHaveLength(1);
    expect(pendingLocal[0].id).toBe("lesson-git-basics");
    expect(pendingLocal[0].score).toBe(20);
    expect(pendingLocal[0].completed).toBe(true);

    // Wait a brief tick for IndexedDB microtask
    await new Promise((resolve) => setTimeout(resolve, 10));

    // Check IndexedDB store
    expect(mockStore.has("lesson-git-basics")).toBe(true);
    const action = mockStore.get("lesson-git-basics");
    expect(action.method).toBe("POST");
    expect(action.headers.Authorization).toBe("Bearer test-token");
    expect(JSON.parse(action.body).lesson_slug).toBe("git-basics");
  }, 15000);

  it("should replay queued requests and clean up stores on successful sync", async () => {
    // 1. Manually populate queue
    await enqueueOfflineAction(
      "/progress/me/",
      "POST",
      { Authorization: "Bearer test-token" },
      { lesson_slug: "git-merge", score: 15, completed: true },
      "lesson",
      "git-merge",
    );

    await new Promise((resolve) => setTimeout(resolve, 10));

    // Verify queued
    expect(mockStore.size).toBe(1);
    expect(
      JSON.parse(localStorage.getItem("atelier_pending_sync") || "[]"),
    ).toHaveLength(1);

    // Mock successful fetch replay
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ success: true }),
    });

    // 2. Run sync
    await syncOfflineQueue();

    // Wait a brief tick for IndexedDB microtask
    await new Promise((resolve) => setTimeout(resolve, 15));

    // Verify queue is empty now
    expect(mockStore.size).toBe(0);
    expect(
      JSON.parse(localStorage.getItem("atelier_pending_sync") || "[]"),
    ).toHaveLength(0);
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["userProgress"],
    });
  }, 15000);

  it("should retain request in queue if replay fails with a network error", async () => {
    await enqueueOfflineAction(
      "/progress/me/",
      "POST",
      { Authorization: "Bearer test-token" },
      { lesson_slug: "git-rebase", score: 30, completed: true },
      "lesson",
      "git-rebase",
    );

    await new Promise((resolve) => setTimeout(resolve, 10));

    // Mock fetch error (network failure)
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(
      new TypeError("Failed to fetch"),
    );

    await syncOfflineQueue();

    await new Promise((resolve) => setTimeout(resolve, 15));

    // Verify it is still in queue
    expect(mockStore.size).toBe(1);
    expect(
      JSON.parse(localStorage.getItem("atelier_pending_sync") || "[]"),
    ).toHaveLength(1);
  }, 15000);

  describe("per-item replay results", () => {
    const queueLesson = async (slug: string) => {
      await enqueueOfflineAction(
        "/progress/me/",
        "POST",
        { Authorization: "Bearer test-token" },
        { lesson_slug: slug, score: 20, completed: true },
        "lesson",
        slug,
      );
      await new Promise((resolve) => setTimeout(resolve, 10));
    };
    const reply = (status: number, body: unknown = {}) => ({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body),
    });
    const mockFetch = () => globalThis.fetch as ReturnType<typeof vi.fn>;
    const pending = () =>
      JSON.parse(localStorage.getItem("atelier_pending_sync") || "[]");

    it("reports a fresh save as synced after reconnecting", async () => {
      await queueLesson("git-basics");
      mockFetch().mockResolvedValue(reply(201));

      const results = await syncOfflineQueue();

      expect(results).toEqual([
        expect.objectContaining({
          lesson_slug: "git-basics",
          status: "synced",
          httpStatus: 201,
        }),
      ]);
      expect(mockStore.size).toBe(0);
      expect(pending()).toHaveLength(0);
      expect(getSyncResults().map((r) => r.status)).toEqual(["synced"]);
    });

    it("reports a lesson the server already has as duplicate, not as a fresh save", async () => {
      await queueLesson("git-basics");
      mockFetch().mockResolvedValue(reply(200));
      const onSuccess = vi.fn();
      eventBus.on("sync:success", onSuccess);

      const results = await syncOfflineQueue();
      eventBus.off("sync:success", onSuccess);

      expect(results.map((r) => r.status)).toEqual(["duplicate"]);
      expect(mockStore.size).toBe(0);
      expect(pending()).toHaveLength(0);
      expect(onSuccess).toHaveBeenCalledWith({
        lesson_slug: "git-basics",
        status: "duplicate",
        kind: "progress",
      });
    });

    it("keeps a 409 as a conflict, tells the UI, and does not replay it again", async () => {
      await queueLesson("git-merge");
      const serverData = { score: 5, completed: false };
      mockFetch().mockResolvedValue(reply(409, serverData));
      const onConflict = vi.fn();
      eventBus.on("sync:conflict", onConflict);

      const first = await syncOfflineQueue();
      eventBus.off("sync:conflict", onConflict);

      expect(first).toEqual([
        expect.objectContaining({ status: "conflict", serverData }),
      ]);
      expect(onConflict).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "lesson-git-merge",
          lesson_slug: "git-merge",
          serverData,
          localData: expect.objectContaining({ lesson_slug: "git-merge" }),
        }),
      );
      expect(mockStore.get("lesson-git-merge").state).toBe("conflict");
      expect(pending()[0].state).toBe("conflict");

      mockFetch().mockClear();
      const second = await syncOfflineQueue();
      expect(second).toEqual([]);
      expect(mockFetch()).not.toHaveBeenCalled();
      expect(mockStore.size).toBe(1);
    });

    it("marks a temporary 503 as retryable and succeeds on the retry", async () => {
      await queueLesson("git-rebase");
      mockFetch().mockResolvedValue(reply(503));

      const first = await syncOfflineQueue();

      expect(first).toEqual([
        expect.objectContaining({ status: "failed", retryable: true }),
      ]);
      expect(mockStore.size).toBe(1);
      expect(pending()[0].state).toBe("failed");
      expect(getSyncResults()).toHaveLength(0);

      mockFetch().mockResolvedValue(reply(201));
      const retry = await syncOfflineQueue();

      expect(retry.map((r) => r.status)).toEqual(["synced"]);
      expect(mockStore.size).toBe(0);
      expect(pending()).toHaveLength(0);
    });

    it("retries only the failed item, not a conflicting one", async () => {
      await queueLesson("conflicting");
      await queueLesson("flaky");
      mockFetch().mockImplementation(async (_url: string, init: RequestInit) =>
        JSON.parse(init.body as string).lesson_slug === "conflicting"
          ? reply(409, { score: 1 })
          : reply(500),
      );
      await syncOfflineQueue();
      expect(mockStore.size).toBe(2);

      mockFetch().mockClear();
      mockFetch().mockResolvedValue(reply(201));
      const retry = await syncOfflineQueue();

      expect(mockFetch()).toHaveBeenCalledTimes(1);
      expect(retry.map((r) => [r.lesson_slug, r.status])).toEqual([
        ["flaky", "synced"],
      ]);
      expect(mockStore.has("lesson-conflicting")).toBe(true);
    });

    it("drops an item the server rejected for good and reports it as not retryable", async () => {
      await queueLesson("bad-slug");
      mockFetch().mockResolvedValue(reply(404));

      const results = await syncOfflineQueue();

      expect(results).toEqual([
        expect.objectContaining({ status: "failed", retryable: false }),
      ]);
      expect(mockStore.size).toBe(0);
      expect(pending()).toHaveLength(0);
      expect(getSyncResults().map((r) => r.status)).toEqual(["failed"]);
    });

    it("does not start a second replay while one is running", async () => {
      await queueLesson("git-basics");
      mockFetch().mockResolvedValue(reply(201));

      const [a, b] = await Promise.all([
        syncOfflineQueue(),
        syncOfflineQueue(),
      ]);

      expect(mockFetch()).toHaveBeenCalledTimes(1);
      expect(a).toBe(b);
    });
  });

  describe("reportProgressConflict", () => {
    const pending = () =>
      JSON.parse(localStorage.getItem("atelier_pending_sync") || "[]");

    it("replaces a waiting entry for the lesson with a conflict", () => {
      localStorage.setItem(
        "atelier_pending_sync",
        JSON.stringify([
          { lesson_slug: "l1", score: 1, timestamp: 1 },
          { lesson_slug: "l2", score: 2, timestamp: 2 },
        ]),
      );

      reportProgressConflict(
        { lesson_slug: "l1" },
        { score: 10, completed: true },
      );

      expect(pending()).toEqual([
        expect.objectContaining({ lesson_slug: "l2" }),
        expect.objectContaining({
          id: "progress-sync-l1",
          lesson_slug: "l1",
          score: 10,
          state: "conflict",
          serverData: { lesson_slug: "l1" },
        }),
      ]);
    });

    it("lists every conflict of a batch so none get lost behind the prompt", () => {
      const onConflict = vi.fn();
      eventBus.on("sync:conflict", onConflict);

      reportProgressConflict({ lesson_slug: "l1" });
      reportProgressConflict({ lesson_slug: "l2" });

      expect(pending().map((p: { state: string }) => p.state)).toEqual([
        "conflict",
        "conflict",
      ]);
      expect(onConflict).toHaveBeenCalledTimes(2);
      eventBus.off("sync:conflict", onConflict);
    });
  });

  describe("classifyReplayStatus", () => {
    it("separates fresh saves, duplicates, conflicts and failures", () => {
      expect(classifyReplayStatus(201).status).toBe("synced");
      expect(classifyReplayStatus(202).status).toBe("synced");
      expect(classifyReplayStatus(200).status).toBe("duplicate");
      expect(classifyReplayStatus(200, false).status).toBe("synced");
      expect(classifyReplayStatus(409).status).toBe("conflict");
    });

    it("only treats temporary errors as retryable", () => {
      for (const code of [401, 408, 429, 500, 502, 503]) {
        expect(classifyReplayStatus(code)).toEqual({
          status: "failed",
          retryable: true,
        });
      }
      for (const code of [400, 404, 422]) {
        expect(classifyReplayStatus(code)).toEqual({
          status: "failed",
          retryable: false,
        });
      }
    });
  });

  describe("order, idempotency keys and schema upgrades (#3328)", () => {
    const API = "http://localhost:8000/api";
    const reply = (status: number, body: unknown = {}) => ({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body),
    });
    const mockFetch = () => globalThis.fetch as ReturnType<typeof vi.fn>;
    const sentSlugs = () =>
      mockFetch().mock.calls.map(
        ([, init]) => JSON.parse(init.body as string).lesson_slug,
      );
    const sentHeaders = (call = 0) =>
      mockFetch().mock.calls[call][1].headers as Record<string, string>;
    const queueLesson = (
      slug: string,
      type = "lesson",
      headers: Record<string, string> = { Authorization: "Bearer test-token" },
    ) =>
      enqueueOfflineAction(
        "/progress/me/",
        "POST",
        headers,
        { lesson_slug: slug, score: 20, completed: true },
        type,
        slug,
      );
    // Unsigned, only the payload matters to the queue
    const jwt = (claims: object) =>
      `x.${btoa(JSON.stringify(claims)).replace(/=+$/, "")}.y`;
    const v1Record = (id: string, slug: string, timestamp: number) => ({
      id,
      url: `${API}/progress/me/`,
      method: "POST",
      headers: { Authorization: "Bearer test-token" },
      body: JSON.stringify({ lesson_slug: slug, score: 10, completed: true }),
      timestamp,
    });

    it("replays in enqueue order, not in IndexedDB key order", async () => {
      await queueLesson("zeta");
      await queueLesson("alpha");
      await queueLesson("mid");
      mockFetch().mockResolvedValue(reply(201));

      await syncOfflineQueue();

      // getAll() alone would have sent alpha, mid, zeta
      expect(sentSlugs()).toEqual(["zeta", "alpha", "mid"]);
      expect(mockStore.size).toBe(0);
    });

    it("keeps counting from the stored cursor after the queue empties", async () => {
      await queueLesson("first");
      await queueLesson("second");
      expect(mockStore.get("lesson-second").seq).toBe(2);
      mockFetch().mockResolvedValue(reply(201));
      await syncOfflineQueue();

      await queueLesson("third");

      expect(mockStore.get("lesson-third").seq).toBe(3);
      expect(
        JSON.parse(localStorage.getItem("atelier_sync_cursor") || "{}"),
      ).toEqual({ version: QUEUE_SCHEMA_VERSION, nextSeq: 4 });
    });

    it("never hands out a position behind a queued action when the cursor is lost", async () => {
      await queueLesson("first");
      await queueLesson("second");
      localStorage.removeItem("atelier_sync_cursor");

      await queueLesson("third");

      expect(mockStore.get("lesson-third").seq).toBe(3);
    });

    it("sends one Idempotency-Key per action and the same one on every retry", async () => {
      await queueLesson("flaky");
      await queueLesson("other");
      mockFetch().mockResolvedValue(reply(503));
      await syncOfflineQueue();
      mockFetch().mockResolvedValue(reply(201));
      await syncOfflineQueue();

      const keys = mockFetch().mock.calls.map(
        ([, init]) =>
          (init.headers as Record<string, string>)["Idempotency-Key"],
      );
      expect(keys).toHaveLength(4);
      expect(keys[0]).toBeTruthy();
      expect(keys[0]).not.toBe(keys[1]);
      // the retry sent the same keys again
      expect(keys.slice(2)).toEqual(keys.slice(0, 2));
    });

    it("sends the current access token, not the one saved at enqueue time", async () => {
      await queueLesson("git-basics", "lesson", {
        authorization: "Bearer old-token",
        "content-type": "application/json",
      });
      localStorage.setItem("accessToken", "new-token");
      mockFetch().mockResolvedValue(reply(201));

      await syncOfflineQueue();

      const headers = sentHeaders();
      expect(headers.Authorization).toBe("Bearer new-token");
      expect(headers.authorization).toBeUndefined();
      expect(headers["content-type"]).toBe("application/json");
    });

    it("stops at a 401 instead of sending the rest with no valid token", async () => {
      await queueLesson("one");
      await queueLesson("two");
      mockFetch().mockResolvedValue(reply(401));

      const results = await syncOfflineQueue();

      expect(mockFetch()).toHaveBeenCalledTimes(1);
      expect(sentHeaders().Authorization).toBeUndefined();
      expect(results).toEqual([
        expect.objectContaining({ status: "failed", retryable: true }),
      ]);
      expect(mockStore.size).toBe(2);
    });

    it("holds an action queued by another account on this browser", async () => {
      await queueLesson("git-basics", "lesson", {
        Authorization: `Bearer ${jwt({ user_id: 1 })}`,
      });
      localStorage.setItem("accessToken", jwt({ user_id: 2 }));
      mockFetch().mockResolvedValue(reply(201));

      const results = await syncOfflineQueue();

      expect(results).toEqual([]);
      expect(mockFetch()).not.toHaveBeenCalled();
      expect(mockStore.has("lesson-git-basics")).toBe(true);
    });

    it("does not let a newer write for a lesson overtake an older one still waiting", async () => {
      // progress-x sorts after lesson-x by key, but was queued first
      await queueLesson("x", "progress");
      await queueLesson("x", "lesson");
      await queueLesson("y", "lesson");
      mockFetch().mockImplementation(async (_url: string, init: RequestInit) =>
        JSON.parse(init.body as string).lesson_slug === "x"
          ? reply(503)
          : reply(201),
      );

      const first = await syncOfflineQueue();

      expect(first.map((r) => [r.id, r.status])).toEqual([
        ["progress-x", "failed"],
        ["lesson-y", "synced"],
      ]);
      expect(mockStore.has("lesson-x")).toBe(true);

      mockFetch().mockClear();
      mockFetch().mockResolvedValue(reply(201));
      const retry = await syncOfflineQueue();
      expect(retry.map((r) => r.id)).toEqual(["progress-x", "lesson-x"]);
    });

    it("treats a 409 about the key itself as a retry, not a conflict", async () => {
      await queueLesson("git-basics");
      mockFetch().mockResolvedValue(
        reply(409, {
          error:
            "A request with this idempotency key is currently being processed",
          idempotency_key: "k",
        }),
      );
      const onConflict = vi.fn();
      eventBus.on("sync:conflict", onConflict);

      const results = await syncOfflineQueue();
      eventBus.off("sync:conflict", onConflict);

      expect(results).toEqual([
        expect.objectContaining({ status: "failed", retryable: true }),
      ]);
      expect(onConflict).not.toHaveBeenCalled();
      expect(mockStore.get("lesson-git-basics").state).toBeUndefined();
    });

    it("upgrades a record queued before the schema version existed and replays it first", async () => {
      await queueLesson("new");
      mockStore.set("lesson-old", v1Record("lesson-old", "old", 5));
      mockFetch().mockResolvedValue(reply(503));

      await syncOfflineQueue();

      const upgraded = mockStore.get("lesson-old");
      expect(upgraded).toEqual(
        expect.objectContaining({
          schemaVersion: QUEUE_SCHEMA_VERSION,
          seq: 0,
          kind: "progress",
          idempotencyKey: expect.any(String),
        }),
      );
      expect(sentSlugs()[0]).toBe("old");
      expect(sentHeaders()["Idempotency-Key"]).toBe(upgraded.idempotencyKey);

      // The key was stored with the upgrade, so the retry sends the same one
      mockFetch().mockClear();
      mockFetch().mockResolvedValue(reply(201));
      await syncOfflineQueue();
      expect(sentSlugs()).toEqual(["old", "new"]);
      expect(sentHeaders()["Idempotency-Key"]).toBe(upgraded.idempotencyKey);
    });

    it("leaves a record from a newer queue version alone", async () => {
      mockStore.set("lesson-future", {
        ...v1Record("lesson-future", "future", 1),
        schemaVersion: QUEUE_SCHEMA_VERSION + 1,
      });
      mockFetch().mockResolvedValue(reply(201));

      const results = await syncOfflineQueue();

      expect(results).toEqual([]);
      expect(mockFetch()).not.toHaveBeenCalled();
      expect(mockStore.get("lesson-future").schemaVersion).toBe(
        QUEUE_SCHEMA_VERSION + 1,
      );
    });

    it("reads the user id out of a token", () => {
      expect(tokenOwner(`Bearer ${jwt({ user_id: 42 })}`)).toBe("42");
      expect(tokenOwner("test-token")).toBeUndefined();
      expect(tokenOwner(null)).toBeUndefined();
    });
  });

  describe("bookmarks in the queue (#3328)", () => {
    const reply = (status: number, body: unknown = {}) => ({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body),
    });
    const mockFetch = () => globalThis.fetch as ReturnType<typeof vi.fn>;
    const pending = () =>
      JSON.parse(localStorage.getItem("atelier_pending_sync") || "[]");

    it("queues a removal of the bookmark it saw and replays it once", async () => {
      localStorage.setItem("accessToken", "token");
      await queueBookmarkChange("git-basics", false, 5);

      const queued = mockStore.get("bookmark-git-basics");
      expect(queued.method).toBe("DELETE");
      expect(queued.url).toBe(
        "http://localhost:8000/api/progress/bookmarks/git-basics/?expected_id=5",
      );
      expect(pending()).toEqual([
        expect.objectContaining({
          id: "bookmark-git-basics",
          kind: "bookmark",
          bookmarked: false,
        }),
      ]);

      mockFetch().mockResolvedValue(reply(204));
      const onSuccess = vi.fn();
      eventBus.on("sync:success", onSuccess);
      const results = await syncOfflineQueue();
      eventBus.off("sync:success", onSuccess);

      expect(mockFetch()).toHaveBeenCalledTimes(1);
      const [, init] = mockFetch().mock.calls[0];
      expect(init.body).toBeUndefined();
      expect(init.headers["Idempotency-Key"]).toBe(queued.idempotencyKey);
      expect(results).toEqual([
        expect.objectContaining({
          lesson_slug: "git-basics",
          kind: "bookmark",
          status: "synced",
        }),
      ]);
      expect(onSuccess).toHaveBeenCalledWith(
        expect.objectContaining({ kind: "bookmark" }),
      );
      expect(mockStore.size).toBe(0);
      expect(pending()).toEqual([]);
    });

    it("drops the queued change when the lesson is toggled back before the replay", async () => {
      await queueBookmarkChange("git-basics", true);

      expect(await queueBookmarkChange("git-basics", false)).toEqual({
        outcome: "cancelled",
        restoredId: undefined,
      });

      expect(mockStore.size).toBe(0);
      expect(pending()).toEqual([]);
      await syncOfflineQueue();
      expect(mockFetch()).not.toHaveBeenCalled();
    });

    it("counts a removal that 404s as already removed, not rejected", async () => {
      await queueBookmarkChange("git-basics", false);
      mockFetch().mockResolvedValue(reply(404));

      const results = await syncOfflineQueue();

      expect(results.map((r) => r.status)).toEqual(["duplicate"]);
      expect(mockStore.size).toBe(0);
    });

    it("sends a refused removal to the conflict prompt and keeps it queued", async () => {
      await queueBookmarkChange("git-basics", false, 5);
      const serverData = {
        code: "bookmark_conflict",
        lesson_slug: "git-basics",
        bookmarked: true,
        id: 7,
        created_at: "2026-11-20T10:00:00Z",
      };
      mockFetch().mockResolvedValue(reply(409, serverData));
      const onConflict = vi.fn();
      eventBus.on("sync:conflict", onConflict);

      await syncOfflineQueue();
      eventBus.off("sync:conflict", onConflict);

      expect(onConflict).toHaveBeenCalledWith({
        id: "bookmark-git-basics",
        kind: "bookmark",
        lesson_slug: "git-basics",
        serverData,
        localData: { lesson_slug: "git-basics", bookmarked: false },
      });
      expect(mockStore.get("bookmark-git-basics").state).toBe("conflict");
      expect(pending()[0].state).toBe("conflict");
    });

    it("resolving a bookmark leaves queued progress for the same lesson alone", async () => {
      await queueBookmarkChange("git-basics", false);
      await enqueueOfflineAction(
        "/progress/me/",
        "POST",
        {},
        { lesson_slug: "git-basics", score: 20, completed: true },
        "lesson",
        "git-basics",
      );

      await removeQueuedAction("bookmark-git-basics", "git-basics");

      expect(pending().map((p: { id: string }) => p.id)).toEqual([
        "lesson-git-basics",
      ]);
      expect(mockStore.has("lesson-git-basics")).toBe(true);
    });

    it("classifies bookmark replies by method", () => {
      const add = { kind: "bookmark" as const, method: "POST" };
      const remove = { kind: "bookmark" as const, method: "DELETE" };
      expect(classifyQueuedReplay(add, 201).status).toBe("synced");
      expect(classifyQueuedReplay(add, 200).status).toBe("duplicate");
      expect(classifyQueuedReplay(add, 404)).toEqual({
        status: "failed",
        retryable: false,
      });
      expect(classifyQueuedReplay(remove, 204).status).toBe("synced");
      expect(classifyQueuedReplay(remove, 404).status).toBe("duplicate");
    });
  });
  describe("review follow-ups (#3489)", () => {
    const reply = (status: number, body: unknown = {}) => ({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body),
    });
    const mockFetch = () => globalThis.fetch as ReturnType<typeof vi.fn>;
    const pending = () =>
      JSON.parse(localStorage.getItem("atelier_pending_sync") || "[]");
    const jwt = (claims: object) =>
      `x.${btoa(JSON.stringify(claims)).replace(/=+$/, "")}.y`;
    const queueLesson = (slug: string, token = "test-token") =>
      enqueueOfflineAction(
        "/progress/me/",
        "POST",
        { Authorization: `Bearer ${token}` },
        { lesson_slug: slug, score: 20, completed: true },
        "lesson",
        slug,
      );

    const API = "http://localhost:8000/api";

    beforeEach(() => {
      vi.spyOn(console, "error").mockImplementation(() => {});
    });

    describe("account owner of the token that is sent", () => {
      it("holds the next action when the active account changed during the previous request", async () => {
        const tokenA = jwt({ user_id: 1 });
        localStorage.setItem("accessToken", tokenA);
        await queueLesson("first", tokenA);
        await queueLesson("second", tokenA);
        mockFetch().mockImplementation(async () => {
          // Account B signs in while A's first request is pending
          localStorage.setItem("accessToken", jwt({ user_id: 2 }));
          return reply(201);
        });

        const results = await syncOfflineQueue();

        expect(mockFetch()).toHaveBeenCalledTimes(1);
        expect(results.map((r) => r.id)).toEqual(["lesson-first"]);
        expect(mockStore.has("lesson-second")).toBe(true);
      });

      it("holds an action of a known owner when the owner of the token cannot be told", async () => {
        await queueLesson("git-basics", jwt({ user_id: 1 }));
        localStorage.setItem("accessToken", "opaque-token");
        mockFetch().mockResolvedValue(reply(201));

        await syncOfflineQueue();

        expect(mockFetch()).not.toHaveBeenCalled();
        expect(mockStore.has("lesson-git-basics")).toBe(true);
      });
    });

    describe("settling only the revision that was sent", () => {
      it("keeps a newer write that replaced the sent one when the old one succeeds", async () => {
        await queueLesson("x");
        const sentKey = mockStore.get("lesson-x").idempotencyKey;
        mockFetch().mockImplementation(async () => {
          // The user finishes the lesson again while the first request is out
          await queueLesson("x");
          return reply(201);
        });

        await syncOfflineQueue();

        const kept = mockStore.get("lesson-x");
        expect(kept).toBeDefined();
        expect(kept.idempotencyKey).not.toBe(sentKey);
        expect(pending()).toEqual([
          expect.objectContaining({ id: "lesson-x" }),
        ]);
      });

      it("does not flag the newer write as conflicting when the old one got a 409", async () => {
        await queueLesson("x");
        mockFetch().mockImplementation(async () => {
          await queueLesson("x");
          return reply(409, { code: "progress_conflict", score: 90 });
        });
        const onConflict = vi.fn();
        eventBus.on("sync:conflict", onConflict);

        await syncOfflineQueue();
        eventBus.off("sync:conflict", onConflict);

        expect(mockStore.get("lesson-x").state).toBeUndefined();
        expect(pending()[0].state).toBeUndefined();
        expect(onConflict).not.toHaveBeenCalled();
      });

      it("ignores a service worker answer about a revision that was replaced", async () => {
        await queueLesson("x");
        await queueLesson("x");
        const current = mockStore.get("lesson-x");
        const sw = new EventTarget();
        Object.defineProperty(navigator, "serviceWorker", {
          configurable: true,
          value: sw,
        });
        vi.resetModules();
        const fresh = await import("../lib/offlineQueue");
        void fresh;

        sw.dispatchEvent(
          new MessageEvent("message", {
            data: {
              type: "SYNC_SUCCESS",
              id: "lesson-x",
              status: 201,
              idempotencyKey: `not-${current.idempotencyKey}`,
            },
          }),
        );
        await new Promise((resolve) => setTimeout(resolve, 20));

        expect(pending()).toEqual([
          expect.objectContaining({ id: "lesson-x" }),
        ]);
      });
    });

    describe("storing a change", () => {
      it("rejects, and shows nothing as queued, when IndexedDB refuses the write", async () => {
        mockFail.put = true;

        await expect(queueBookmarkChange("git-basics", true)).rejects.toThrow();
        await expect(queueLesson("git-basics")).rejects.toThrow();

        expect(mockStore.size).toBe(0);
        expect(pending()).toEqual([]);
      });

      it("does not overwrite a record a newer build left under the same id", async () => {
        const future = {
          id: "bookmark-git-basics",
          url: `${API}/progress/bookmarks/git-basics/`,
          method: "POST",
          headers: {},
          body: "",
          timestamp: 1,
          schemaVersion: QUEUE_SCHEMA_VERSION + 1,
        };
        mockStore.set("bookmark-git-basics", future);

        await expect(queueBookmarkChange("git-basics", true)).rejects.toThrow(
          QueueRecordLockedError,
        );
        expect(await dropQueuedBookmark("git-basics")).toBeUndefined();

        expect(mockStore.get("bookmark-git-basics")).toBe(future);
      });
    });

    describe("bookmark changes that were already sent", () => {
      it("returns the id of a removal it cancels so the bookmark can be restored", async () => {
        await queueBookmarkChange("git-basics", false, 5);

        const result = await queueBookmarkChange("git-basics", true);

        expect(result).toEqual({ outcome: "cancelled", restoredId: 5 });
        expect(mockStore.size).toBe(0);
      });

      it("queues the opposite change instead of cancelling one whose answer was lost", async () => {
        await queueBookmarkChange("git-basics", true);
        const added = mockStore.get("bookmark-git-basics");
        mockFetch().mockRejectedValue(new TypeError("Failed to fetch"));
        await syncOfflineQueue();
        expect(mockStore.get("bookmark-git-basics").dispatchedAt).toEqual(
          expect.any(Number),
        );

        const result = await queueBookmarkChange("git-basics", false);

        // The POST may have reached the server: a DELETE has to follow it
        expect(result.outcome).toBe("queued");
        const queued = mockStore.get("bookmark-git-basics");
        expect(queued.method).toBe("DELETE");
        expect(queued.idempotencyKey).not.toBe(added.idempotencyKey);
        expect(queued.dispatchedAt).toBeUndefined();
        expect(pending()).toEqual([
          expect.objectContaining({
            id: "bookmark-git-basics",
            bookmarked: false,
          }),
        ]);
      });
    });

    describe("taking a queued bookmark change out for an online request", () => {
      it("puts it back, with its entry, when the online request does not go through", async () => {
        await queueBookmarkChange("git-basics", true);
        const before = mockStore.get("bookmark-git-basics");

        const dropped = await dropQueuedBookmark("git-basics");
        expect(mockStore.size).toBe(0);
        expect(pending()).toEqual([]);

        await restoreQueuedBookmark(dropped);

        expect(mockStore.get("bookmark-git-basics")).toEqual(before);
        expect(pending()).toEqual([
          expect.objectContaining({
            id: "bookmark-git-basics",
            bookmarked: true,
          }),
        ]);
      });

      it("does not put it back over a change queued in the meantime", async () => {
        await queueBookmarkChange("git-basics", true);
        const dropped = await dropQueuedBookmark("git-basics");
        await queueBookmarkChange("git-basics", false);

        await restoreQueuedBookmark(dropped);

        expect(mockStore.get("bookmark-git-basics").method).toBe("DELETE");
      });

      it("lists the bookmark changes that are still waiting", async () => {
        await queueBookmarkChange("saved", true);
        await queueBookmarkChange("removed", false, 3);

        expect([...getPendingBookmarkChanges()]).toEqual([
          ["saved", true],
          ["removed", false],
        ]);
      });
    });

    describe("legacy records", () => {
      it("does not send a record whose new key could not be stored", async () => {
        mockStore.set("lesson-old", {
          id: "lesson-old",
          url: `${API}/progress/me/`,
          method: "POST",
          headers: { Authorization: "Bearer test-token" },
          body: JSON.stringify({ lesson_slug: "old", completed: true }),
          timestamp: 5,
        });
        mockFail.put = true;
        mockFetch().mockResolvedValue(reply(201));

        await syncOfflineQueue();

        expect(mockFetch()).not.toHaveBeenCalled();
        expect(mockStore.get("lesson-old").idempotencyKey).toBeUndefined();
      });

      it("sends the key another writer committed first, not its own", async () => {
        const v1 = {
          id: "lesson-old",
          url: `${API}/progress/me/`,
          method: "POST",
          headers: { Authorization: "Bearer test-token" },
          body: JSON.stringify({ lesson_slug: "old", completed: true }),
          timestamp: 5,
        };
        mockStore.set("lesson-old", v1);
        // The service worker upgraded it between this page's read and its write
        mockGetOverride.set("lesson-old", {
          ...v1,
          schemaVersion: QUEUE_SCHEMA_VERSION,
          seq: 0,
          idempotencyKey: "committed-by-sw",
          kind: "progress",
        });
        mockFetch().mockResolvedValue(reply(201));

        await syncOfflineQueue();

        expect(mockFetch().mock.calls[0][1].headers["Idempotency-Key"]).toBe(
          "committed-by-sw",
        );
      });
    });

    describe("pending list", () => {
      it("keeps a progress entry next to a bookmark entry of the same lesson", async () => {
        await queueBookmarkChange("git-basics", true);

        await queueProgressSync({
          lesson_slug: "git-basics",
          score: 50,
          completed: true,
          headers: {},
        });

        expect(pending().map((p: { id: string }) => p.id)).toEqual([
          "bookmark-git-basics",
          "progress-sync-git-basics",
        ]);
      });

      it("shows a retryable failure on the progress entry, not only on the bookmark", async () => {
        await queueBookmarkChange("git-basics", true);
        await queueProgressSync({
          lesson_slug: "git-basics",
          completed: true,
          headers: {},
        });
        mockFetch().mockResolvedValue(reply(503));

        await syncOfflineQueue();

        const entry = pending().find(
          (p: { id: string }) => p.id === "progress-sync-git-basics",
        );
        expect(entry.state).toBe("failed");
      });

      it("keeps an old progress entry without an id when a bookmark conflict is resolved", async () => {
        localStorage.setItem(
          "atelier_pending_sync",
          JSON.stringify([{ lesson_slug: "git-basics", timestamp: 1 }]),
        );

        await removeQueuedAction("bookmark-git-basics", "git-basics");

        expect(pending()).toEqual([
          expect.objectContaining({ lesson_slug: "git-basics" }),
        ]);
      });
    });

    describe("resolving a conflict", () => {
      it("rejects, and keeps the entry, when the queued item cannot be removed", async () => {
        await queueBookmarkChange("git-basics", false, 5);
        mockFail.delete = true;

        await expect(
          removeQueuedAction("bookmark-git-basics", "git-basics"),
        ).rejects.toThrow();

        expect(mockStore.has("bookmark-git-basics")).toBe(true);
        expect(pending()).toHaveLength(1);
      });

      it("shows a conflict the service worker stored, without sending the request again", async () => {
        await queueBookmarkChange("git-basics", false, 5);
        const serverData = { code: "bookmark_conflict", id: 7 };
        mockStore.set("bookmark-git-basics", {
          ...mockStore.get("bookmark-git-basics"),
          state: "conflict",
          serverData,
        });
        // A page opened with an empty list: nothing told it about the conflict
        localStorage.setItem("atelier_pending_sync", "[]");
        const onConflict = vi.fn();
        eventBus.on("sync:conflict", onConflict);

        await syncOfflineQueue();
        await syncOfflineQueue();
        eventBus.off("sync:conflict", onConflict);

        expect(mockFetch()).not.toHaveBeenCalled();
        expect(onConflict).toHaveBeenCalledTimes(1);
        expect(onConflict).toHaveBeenCalledWith(
          expect.objectContaining({
            id: "bookmark-git-basics",
            kind: "bookmark",
            serverData,
          }),
        );
        expect(pending()).toEqual([
          expect.objectContaining({
            id: "bookmark-git-basics",
            state: "conflict",
          }),
        ]);
      });
    });
  });
});
