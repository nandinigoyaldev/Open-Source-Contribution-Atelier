import { describe, it, expect, vi, beforeEach } from "vitest";
import { queueProgressSync, syncOfflineQueue } from "../lib/offlineQueue";
import { queryClient } from "../lib/queryClient";

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

    await queueProgressSync({
      lesson_slug: "git-basics",
      score: 20,
      completed: true,
      headers: { Authorization: "Bearer test-token" },
    });

    // Check localStorage
    const pendingLocal = JSON.parse(
      localStorage.getItem("atelier_pending_sync") || "[]",
    );
    expect(pendingLocal).toHaveLength(1);
    expect(pendingLocal[0].lesson_slug).toBe("git-basics");
    expect(pendingLocal[0].score).toBe(20);
    expect(pendingLocal[0].completed).toBe(true);

    // Wait a brief tick for IndexedDB microtask
    await new Promise((resolve) => setTimeout(resolve, 10));

    // Check IndexedDB store
    expect(mockStore.has("progress-sync-git-basics")).toBe(true);
    const action = mockStore.get("progress-sync-git-basics");
    expect(action.method).toBe("POST");
    expect(action.headers.Authorization).toBe("Bearer test-token");
    expect(JSON.parse(action.body).lesson_slug).toBe("git-basics");
  });

  it("should replay queued requests and clean up stores on successful sync", async () => {
    // 1. Manually populate queue
    await queueProgressSync({
      lesson_slug: "git-merge",
      score: 15,
      completed: true,
      headers: { Authorization: "Bearer test-token" },
    });

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
  });

  it("should retain request in queue if replay fails with a network error", async () => {
    await queueProgressSync({
      lesson_slug: "git-rebase",
      score: 30,
      completed: true,
      headers: { Authorization: "Bearer test-token" },
    });

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
  });
});
