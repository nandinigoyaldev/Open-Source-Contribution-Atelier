import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  classifyReplayStatus,
  enqueueOfflineAction,
  getSyncResults,
  reportProgressConflict,
  syncOfflineQueue,
} from "../lib/offlineQueue";
import { queryClient } from "../lib/queryClient";
import { eventBus } from "../core/events";

interface MockIDBRequest {
  onsuccess: ((event: Event) => void) | null;
  onerror: ((event: Event) => void) | null;
  result?: unknown;
  error?: unknown;
}

// Mock IndexedDB
const mockStore = new Map();
const mockIDBDatabase = {
  transaction: vi.fn().mockReturnValue({
    objectStore: vi.fn().mockReturnValue({
      put: vi.fn().mockImplementation((item) => {
        mockStore.set(item.id, item);
        const req: MockIDBRequest = {
          onsuccess: null,
          onerror: null,
          result: item.id,
        };
        setTimeout(() => {
          if (req.onsuccess)
            req.onsuccess({ target: { result: item.id } } as unknown as Event);
        }, 0);
        return req;
      }),
      getAll: vi.fn().mockImplementation(() => {
        const resultVal = Array.from(mockStore.values());
        const req: MockIDBRequest = {
          onsuccess: null,
          onerror: null,
          result: resultVal,
        };
        setTimeout(() => {
          if (req.onsuccess)
            req.onsuccess({
              target: { result: resultVal },
            } as unknown as Event);
        }, 0);
        return req;
      }),
      delete: vi.fn().mockImplementation((id) => {
        mockStore.delete(id);
        const req: MockIDBRequest = {
          onsuccess: null,
          onerror: null,
          result: undefined,
        };
        setTimeout(() => {
          if (req.onsuccess)
            req.onsuccess({
              target: { result: undefined },
            } as unknown as Event);
        }, 0);
        return req;
      }),
    }),
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
});
