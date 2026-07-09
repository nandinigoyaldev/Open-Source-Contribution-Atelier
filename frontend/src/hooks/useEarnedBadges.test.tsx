import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useEarnedBadges } from "./useEarnedBadges";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fetchLessonsApi } from "../lib/lessons";
import React from "react";
import { useAuth } from "../features/auth/AuthContext";
import { useUserProgress } from "./useUserProgress";

vi.mock("../lib/lessons", () => ({
  fetchLessonsApi: vi.fn(),
  buildModulesFromLessons: vi.fn((lessons) => [
    {
      id: "mod-1",
      title: "Module 1",
      lessons: lessons.slice(0, 2),
    },
  ]),
}));

vi.mock("../features/auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("./useUserProgress", () => ({
  useUserProgress: vi.fn(),
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

describe("useEarnedBadges", () => {
  const mockLessons = [
    { slug: "lesson-1", title: "Lesson 1" },
    { slug: "lesson-2", title: "Lesson 2" },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    
    vi.mocked(useAuth).mockReturnValue({
      user: { id: 1, username: "testuser", is_staff: false },
      isLoading: false,
      checkUser: vi.fn(),
    } as any);
    
    vi.mocked(fetchLessonsApi).mockResolvedValue(mockLessons as unknown as import("../lib/lessons").Lesson[]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calculates zero progress when no lessons are completed", async () => {
    vi.mocked(useUserProgress).mockReturnValue({
      isLessonCompleted: () => false,
    } as unknown as ReturnType<typeof useUserProgress>);

    const { result } = renderHook(() => useEarnedBadges(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLessonsLoading).toBe(false);
    });

    expect(result.current.completionPercentage).toBe(0);
    expect(result.current.earnedBadges).toEqual([]);
    expect(result.current.completedLessonsCount).toBe(0);
  });

  it("awards module badge and grad badge when all lessons completed", async () => {
    vi.mocked(useUserProgress).mockReturnValue({
      isLessonCompleted: (slug: string) => ["lesson-1", "lesson-2"].includes(slug),
    } as unknown as ReturnType<typeof useUserProgress>);

    const { result } = renderHook(() => useEarnedBadges(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLessonsLoading).toBe(false);
    });

    expect(result.current.completionPercentage).toBe(100);
    expect(result.current.completedLessonsCount).toBe(2);
    // Based on the logic, 'mod-1' is pushed, and if percentage is 100, 'grad' is pushed.
    expect(result.current.earnedBadges).toContain("mod-1");
    expect(result.current.earnedBadges).toContain("grad");
  });
});
