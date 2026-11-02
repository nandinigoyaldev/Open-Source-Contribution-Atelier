import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useUserProgress } from "./useUserProgress";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";
import React from "react";

vi.mock("../lib/api", () => ({
  fetchApi: vi.fn(),
}));

// Mock useLocalSync since it relies on window events and localStorage sync logic
vi.mock("./useLocalSync", () => ({
  useLocalSync: vi.fn(),
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe("useUserProgress", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("fetches user progress successfully", async () => {
    const mockProgress = [
      {
        id: 1,
        lesson: 1,
        lesson_slug: "test-lesson",
        completed: true,
        score: 100,
        updated_at: new Date().toISOString(),
      },
    ];

    vi.mocked(fetchApi).mockResolvedValueOnce(mockProgress);

    const { result } = renderHook(() => useUserProgress(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.progress).toEqual(mockProgress);
    expect(result.current.isLessonCompleted("test-lesson")).toBe(true);
    expect(result.current.totalXP).toBe(100);
  });

  it("syncs progress to backend successfully", async () => {
    vi.mocked(fetchApi).mockResolvedValueOnce([]); // initial fetch
    vi.mocked(fetchApi).mockResolvedValueOnce({}); // mutation response

    const mockProgress = [
      {
        id: 1,
        lesson: 1,
        lesson_slug: "new-lesson",
        completed: true,
        score: 50,
        updated_at: new Date().toISOString(),
      },
    ];
    vi.mocked(fetchApi).mockResolvedValueOnce(mockProgress); // refetch after invalidation

    // Start with real timers for initial load
    const { result } = renderHook(() => useUserProgress(), {
      wrapper: createWrapper(),
    });

    // Wait for initial load
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Switch to fake timers for debouncing
    vi.useFakeTimers();

    act(() => {
      result.current.syncProgress({
        lesson_slug: "new-lesson",
        score: 50,
        completed: true,
      });
    });

    // Advance timers to trigger the debounced sync (3 seconds)
    await act(async () => {
      vi.advanceTimersByTime(3000);
    });

    // Flush promises so mutation fetchApi runs
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const bulkCall = vi
      .mocked(fetchApi)
      .mock.calls.find((call) => call[0] === "/progress/bulk-update/");
    expect(bulkCall).toBeDefined();
    const body = JSON.parse(bulkCall![1]!.body as string);
    expect(body.lessons).toEqual([
      {
        lesson_slug: "new-lesson",
        score: 50,
        completed: true,
        client_timestamp: expect.any(Number),
      },
    ]);
    expect(body.metadata.timestamp).toEqual(expect.any(Number));

    // Restore real timers for invalidation/refetch query updates
    vi.useRealTimers();

    await waitFor(() => {
      expect(result.current.progress).toEqual(mockProgress);
    });
  });

  it("reads pending sync progress from localStorage for isLessonCompleted", async () => {
    vi.mocked(fetchApi).mockResolvedValueOnce([]); // no progress from backend

    // Simulate offline completion
    localStorage.setItem(
      "atelier_pending_sync",
      JSON.stringify([
        { lesson_slug: "offline-lesson", score: 10, completed: true },
      ]),
    );

    const { result } = renderHook(() => useUserProgress(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isLessonCompleted("offline-lesson")).toBe(true);
    expect(result.current.totalXP).toBe(10);
  });

  describe("completion announcements", () => {
    const run = async (bulk: () => Promise<unknown>, clicks: number) => {
      vi.mocked(fetchApi).mockImplementation(((url: string) =>
        url === "/progress/bulk-update/"
          ? bulk()
          : Promise.resolve([])) as never);
      const { result } = renderHook(() => useUserProgress(), {
        wrapper: createWrapper(),
      });
      // Fake timers are installed globally in test/setup.ts
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
      expect(result.current.isLoading).toBe(false);
      for (let i = 0; i < clicks; i++) {
        await act(async () => {
          await result.current.syncProgress({
            lesson_slug: "l1",
            score: 10,
            completed: true,
          });
        });
      }
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3000);
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });
      return result;
    };

    it("announces success once for a debounced batch of clicks", async () => {
      const bulk = vi.fn(() => Promise.resolve({}));
      const result = await run(bulk, 3);
      expect(bulk).toHaveBeenCalledTimes(1);
      expect(result.current.announcement).toEqual({
        type: "success",
        message: "Lesson completion saved.",
      });
    });

    it("announces an error when the sync fails", async () => {
      const result = await run(() => Promise.reject(new Error("boom")), 1);
      expect(result.current.announcement?.type).toBe("error");
    });
  });

  it("keeps optimistic totals when an earlier batch settles while a later one is queued", async () => {
    let releaseFirst: (v: unknown) => void = () => {};
    let bulkCalls = 0;
    let meCalls = 0;
    vi.mocked(fetchApi).mockImplementation((url: string) => {
      if (url === "/progress/bulk-update/") {
        bulkCalls += 1;
        return bulkCalls === 1
          ? new Promise((r) => {
              releaseFirst = r;
            })
          : Promise.resolve({});
      }
      meCalls += 1;
      return Promise.resolve([]);
    });

    const { result } = renderHook(() => useUserProgress(), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(meCalls).toBe(1);

    vi.useFakeTimers();
    act(() => {
      result.current.syncProgress({
        lesson_slug: "a",
        score: 10,
        completed: true,
      });
    });
    await act(async () => {
      vi.advanceTimersByTime(3000);
    });
    expect(bulkCalls).toBe(1);

    // second completion lands while the first request is still in flight
    act(() => {
      result.current.syncProgress({
        lesson_slug: "b",
        score: 20,
        completed: true,
      });
    });

    await act(async () => {
      releaseFirst({});
      await Promise.resolve();
      await Promise.resolve();
    });

    // no refetch yet, so the stale server list cannot overwrite the cache
    expect(meCalls).toBe(1);
    expect(result.current.totalXP).toBe(30);

    await act(async () => {
      vi.advanceTimersByTime(3000);
    });
    vi.useRealTimers();
    await waitFor(() => expect(bulkCalls).toBe(2));
    await waitFor(() => expect(meCalls).toBe(2));
  });
});
