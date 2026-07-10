import { renderHook, waitFor } from "@testing-library/react";
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

    const { result } = renderHook(() => useUserProgress(), {
      wrapper: createWrapper(),
    });

    result.current.syncProgress({
      lesson_slug: "new-lesson",
      score: 50,
      completed: true,
    });

    await waitFor(() => {
      expect(fetchApi).toHaveBeenCalledWith(
        "/progress/me/",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            lesson_slug: "new-lesson",
            score: 50,
            completed: true,
          }),
        }),
      );
    });

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
