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
});
