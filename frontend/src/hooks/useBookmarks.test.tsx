import { renderHook, waitFor, act, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useBookmarks, BookmarkEntry } from "./useBookmarks";
import {
  QueryClient,
  QueryClientProvider,
  onlineManager,
} from "@tanstack/react-query";
import { fetchApi } from "../lib/api";
import { createApiError } from "../lib/apiErrors";
import {
  dropQueuedBookmark,
  getPendingBookmarkChanges,
  queueBookmarkChange,
  restoreQueuedBookmark,
} from "../lib/offlineQueue";
import React from "react";

vi.mock("../lib/api", () => ({
  fetchApi: vi.fn(),
}));

vi.mock("../lib/offlineQueue", () => ({
  queueBookmarkChange: vi.fn().mockResolvedValue({ outcome: "queued" }),
  dropQueuedBookmark: vi.fn().mockResolvedValue(undefined),
  restoreQueuedBookmark: vi.fn().mockResolvedValue(undefined),
  getPendingBookmarkChanges: vi.fn().mockReturnValue(new Map()),
}));

const mockAddToast = vi.fn();
vi.mock("../features/ui/ToastContext", () => ({
  useToast: () => ({
    addToast: mockAddToast,
  }),
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

const sampleBookmark: BookmarkEntry = {
  id: 1,
  lesson: 101,
  lesson_slug: "git-basics",
  lesson_title: "Git Basics",
  lesson_difficulty: "beginner",
  lesson_category: "Git",
  lesson_estimated_minutes: 15,
  lesson_summary: "Learn git basics",
  created_at: "2026-01-01T00:00:00Z",
};

const sampleBookmark2: BookmarkEntry = {
  id: 2,
  lesson: 102,
  lesson_slug: "docker-guide",
  lesson_title: "Docker Guide",
  lesson_difficulty: "intermediate",
  lesson_category: "DevOps",
  lesson_estimated_minutes: 20,
  lesson_summary: "Learn docker",
  created_at: "2026-01-01T00:00:00Z",
};

describe("useBookmarks", () => {
  beforeEach(() => {
    // eslint-disable-next-line no-restricted-syntax
    vi.useRealTimers();
    vi.clearAllMocks();
    localStorage.clear();
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: true,
      writable: true,
    });
    // restoreAllMocks() in afterEach drops the factory implementations
    vi.mocked(queueBookmarkChange).mockResolvedValue({ outcome: "queued" });
    vi.mocked(dropQueuedBookmark).mockResolvedValue(undefined);
    vi.mocked(restoreQueuedBookmark).mockResolvedValue(undefined);
    vi.mocked(getPendingBookmarkChanges).mockReturnValue(new Map());
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    onlineManager.setOnline(true);
  });

  it("loads cached bookmarks from localStorage on initial render / refresh", async () => {
    localStorage.setItem("atelier_bookmarks", JSON.stringify([sampleBookmark]));
    vi.mocked(fetchApi).mockResolvedValueOnce([sampleBookmark]);

    const { result } = renderHook(() => useBookmarks(), {
      wrapper: createWrapper(),
    });

    // Should immediately have cached bookmarks without waiting for network response
    expect(result.current.bookmarks).toHaveLength(1);
    expect(result.current.bookmarks[0].lesson_slug).toBe("git-basics");
    expect(result.current.isBookmarked("git-basics")).toBe(true);
  });

  it("filters out null and corrupted non-object entries from localStorage cache without throwing", async () => {
    localStorage.setItem(
      "atelier_bookmarks",
      JSON.stringify([null, "corrupted", 123, sampleBookmark, {}]),
    );
    vi.mocked(fetchApi).mockResolvedValueOnce([sampleBookmark]);

    const { result } = renderHook(() => useBookmarks(), {
      wrapper: createWrapper(),
    });

    // Should safely filter corrupted entries and keep only valid BookmarkEntry
    expect(result.current.bookmarks).toHaveLength(1);
    expect(result.current.bookmarks[0].lesson_slug).toBe("git-basics");
    expect(result.current.isBookmarked("git-basics")).toBe(true);
  });

  it("adds a bookmark optimistically before network responds, and persists on server confirmation", async () => {
    let resolvePost: (v: any) => void = () => {};
    const postPromise = new Promise((resolve) => {
      resolvePost = resolve;
    });

    let serverBookmarks: BookmarkEntry[] = [];

    vi.mocked(fetchApi).mockImplementation(async (url: string) => {
      if (url === "/progress/bookmarks/") return serverBookmarks;
      if (url === "/progress/bookmarks/intro-open-source/") {
        return postPromise;
      }
      return [];
    });

    const { result } = renderHook(() => useBookmarks(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isBookmarked("intro-open-source")).toBe(false);

    // Trigger save bookmark
    act(() => {
      result.current.toggleBookmark.mutate({
        slug: "intro-open-source",
        isBookmarked: false,
        lesson: {
          title: "Intro to Open Source",
          difficulty: "beginner",
          category: "Community",
        },
      });
    });

    // Instantly updated in memory optimistically WHILE network is still pending!
    await waitFor(() => {
      expect(result.current.isBookmarked("intro-open-source")).toBe(true);
    });
    expect(
      result.current.bookmarks.some(
        (b) => b.lesson_slug === "intro-open-source",
      ),
    ).toBe(true);

    // Simulate backend confirming the bookmark
    serverBookmarks = [
      {
        id: 3,
        lesson: 103,
        lesson_slug: "intro-open-source",
        lesson_title: "Intro to Open Source",
        lesson_difficulty: "beginner",
        lesson_category: "Community",
        lesson_estimated_minutes: 10,
        lesson_summary: "",
        created_at: new Date().toISOString(),
      },
    ];

    // Network resolves
    await act(async () => {
      resolvePost({ action: "added" });
    });

    // Remains bookmarked, persists confirmed state, and announces success
    await waitFor(() => {
      expect(result.current.announcement).toEqual({
        type: "success",
        message: "Saved to Read Later",
      });
    });
    expect(result.current.isBookmarked("intro-open-source")).toBe(true);

    const stored = JSON.parse(
      localStorage.getItem("atelier_bookmarks") || "[]",
    );
    expect(stored.some((b: any) => b.lesson_slug === "intro-open-source")).toBe(
      true,
    );
  });

  it("removes a bookmark optimistically before network responds, and announces removal", async () => {
    let resolveDelete: (v: any) => void = () => {};
    const deletePromise = new Promise((resolve) => {
      resolveDelete = resolve;
    });

    let serverBookmarks: BookmarkEntry[] = [sampleBookmark];

    vi.mocked(fetchApi).mockImplementation(async (url: string) => {
      if (url === "/progress/bookmarks/") return serverBookmarks;
      if (url === "/progress/bookmarks/git-basics/") {
        return deletePromise;
      }
      return [];
    });

    const { result } = renderHook(() => useBookmarks(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.bookmarks).toHaveLength(1));
    expect(result.current.isBookmarked("git-basics")).toBe(true);

    // Trigger remove bookmark
    act(() => {
      result.current.toggleBookmark.mutate({
        slug: "git-basics",
        isBookmarked: true,
      });
    });

    // Immediately removed in memory optimistically WHILE network is still pending!
    await waitFor(() => {
      expect(result.current.isBookmarked("git-basics")).toBe(false);
    });
    expect(result.current.bookmarks).toHaveLength(0);

    // Simulate server removing bookmark
    serverBookmarks = [];

    // Network resolves
    await act(async () => {
      resolveDelete({ action: "removed" });
    });

    await waitFor(() => {
      expect(result.current.announcement).toEqual({
        type: "success",
        message: "Removed from Read Later",
      });
    });
    expect(result.current.isBookmarked("git-basics")).toBe(false);
  });

  it("reverts only the failed slug when network request fails, preserving concurrent updates", async () => {
    vi.mocked(fetchApi).mockImplementation(async (url: string) => {
      if (url === "/progress/bookmarks/")
        return [sampleBookmark, sampleBookmark2];
      if (url.includes("/progress/bookmarks/git-basics/")) {
        throw new Error("Network failure");
      }
      return [];
    });

    const { result } = renderHook(() => useBookmarks(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.bookmarks).toHaveLength(2));

    // Try removing git-basics (which will fail)
    act(() => {
      result.current.toggleBookmark.mutate({
        slug: "git-basics",
        isBookmarked: true,
      });
    });

    // Should rollback git-basics while sampleBookmark2 remains
    await waitFor(() => {
      expect(result.current.isBookmarked("git-basics")).toBe(true);
      expect(result.current.isBookmarked("docker-guide")).toBe(true);
      expect(result.current.bookmarks).toHaveLength(2);
    });

    // Error announced
    await waitFor(() => {
      expect(result.current.announcement).toEqual({
        type: "error",
        message:
          "Could not update bookmark. Your bookmark was restored. Please try again.",
      });
    });
    expect(mockAddToast).toHaveBeenCalledWith(
      "Failed to update bookmark.",
      "error",
    );
  });

  it("shares in-flight pending status across separate hook instances sharing the query client", async () => {
    let resolveNetwork: (v: any) => void = () => {};
    const pendingPromise = new Promise((resolve) => {
      resolveNetwork = resolve;
    });

    vi.mocked(fetchApi).mockImplementation(async (url: string) => {
      if (url === "/progress/bookmarks/") return [];
      if (url.includes("/progress/bookmarks/shared-slug/")) {
        return pendingPromise;
      }
      return [];
    });

    const wrapper = createWrapper();
    const { result: instance1 } = renderHook(() => useBookmarks(), { wrapper });
    const { result: instance2 } = renderHook(() => useBookmarks(), { wrapper });

    await waitFor(() => expect(instance1.current.isLoading).toBe(false));

    // Trigger from instance 1
    act(() => {
      instance1.current.toggleBookmark.mutate({
        slug: "shared-slug",
        isBookmarked: false,
      });
    });

    // Instance 2 should also see shared-slug as pending!
    await waitFor(() => {
      expect(instance2.current.isPendingSlug("shared-slug")).toBe(true);
    });

    // Settle promise
    await act(async () => {
      resolveNetwork({});
    });

    await waitFor(() => {
      expect(instance2.current.isPendingSlug("shared-slug")).toBe(false);
    });
  });

  it("prevents double submissions while a request for the same slug is in flight", async () => {
    let resolveNetwork: (v: any) => void = () => {};
    const pendingPromise = new Promise((resolve) => {
      resolveNetwork = resolve;
    });

    let callsCount = 0;
    vi.mocked(fetchApi).mockImplementation(async (url: string) => {
      if (url === "/progress/bookmarks/") return [];
      if (url.includes("/progress/bookmarks/rapid-click/")) {
        callsCount++;
        return pendingPromise;
      }
      return [];
    });

    const { result } = renderHook(() => useBookmarks(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    // Rapid double click
    act(() => {
      result.current.toggleBookmark.mutate({
        slug: "rapid-click",
        isBookmarked: false,
      });
      result.current.toggleBookmark.mutate({
        slug: "rapid-click",
        isBookmarked: false,
      });
    });

    // Check that pending state was set
    expect(result.current.isPendingSlug("rapid-click")).toBe(true);

    // Settle promise
    await act(async () => {
      resolveNetwork({});
    });

    await waitFor(() => {
      expect(result.current.isPendingSlug("rapid-click")).toBe(false);
    });

    // Only one network call was triggered for the slug
    expect(callsCount).toBe(1);
  });

  describe("offline (#3328)", () => {
    const serverList = (list: BookmarkEntry[]) =>
      vi.mocked(fetchApi).mockImplementation(async (url: string) => {
        if (url === "/progress/bookmarks/") return list;
        throw new TypeError("Failed to fetch");
      });

    it("queues an add made offline and keeps it on screen", async () => {
      serverList([]);
      const { result } = renderHook(() => useBookmarks(), {
        wrapper: createWrapper(),
      });
      await waitFor(() => expect(result.current.isLoading).toBe(false));
      // What the browser's offline event does: a default mutation would now
      // sit paused in memory and be lost on reload
      onlineManager.setOnline(false);
      Object.defineProperty(navigator, "onLine", { value: false });

      act(() => {
        result.current.toggleBookmark.mutate({
          slug: "git-basics",
          isBookmarked: false,
        });
      });

      await waitFor(() => {
        expect(result.current.announcement).toEqual({
          type: "success",
          message:
            "Saved to Read Later. It will sync when you are back online.",
        });
      });
      expect(queueBookmarkChange).toHaveBeenCalledWith(
        "git-basics",
        true,
        undefined,
      );
      expect(fetchApi).not.toHaveBeenCalledWith(
        "/progress/bookmarks/git-basics/",
        expect.anything(),
      );
      expect(result.current.isBookmarked("git-basics")).toBe(true);
      expect(mockAddToast).not.toHaveBeenCalledWith(
        "Failed to update bookmark.",
        "error",
      );
    });

    it("queues a removal when the request dies on the network instead of restoring it", async () => {
      serverList([sampleBookmark]);
      const { result } = renderHook(() => useBookmarks(), {
        wrapper: createWrapper(),
      });
      await waitFor(() => expect(result.current.bookmarks).toHaveLength(1));

      act(() => {
        result.current.toggleBookmark.mutate({
          slug: "git-basics",
          isBookmarked: true,
        });
      });

      // with the id the server gave that bookmark, for the conflict check
      await waitFor(() => {
        expect(queueBookmarkChange).toHaveBeenCalledWith(
          "git-basics",
          false,
          sampleBookmark.id,
        );
      });
      await waitFor(() => {
        expect(result.current.announcement?.type).toBe("success");
      });
      expect(result.current.isBookmarked("git-basics")).toBe(false);
    });

    it("drops a change still queued from offline before toggling online", async () => {
      vi.mocked(fetchApi).mockImplementation(async (url: string) =>
        url === "/progress/bookmarks/" ? [] : {},
      );
      const { result } = renderHook(() => useBookmarks(), {
        wrapper: createWrapper(),
      });
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await act(async () => {
        result.current.toggleBookmark.mutate({
          slug: "git-basics",
          isBookmarked: false,
        });
      });

      await waitFor(() =>
        expect(result.current.announcement?.message).toBe(
          "Saved to Read Later",
        ),
      );
      expect(dropQueuedBookmark).toHaveBeenCalledWith("git-basics");
      expect(queueBookmarkChange).not.toHaveBeenCalled();
    });

    it("counts a 404 on removal as removed", async () => {
      vi.mocked(fetchApi).mockImplementation(async (url: string) => {
        if (url === "/progress/bookmarks/") return [sampleBookmark];
        throw createApiError({ status: 404 });
      });
      const { result } = renderHook(() => useBookmarks(), {
        wrapper: createWrapper(),
      });
      await waitFor(() => expect(result.current.bookmarks).toHaveLength(1));

      act(() => {
        result.current.toggleBookmark.mutate({
          slug: "git-basics",
          isBookmarked: true,
        });
      });

      await waitFor(() =>
        expect(result.current.announcement).toEqual({
          type: "success",
          message: "Removed from Read Later",
        }),
      );
    });

    it("puts the queued change back when the online request fails for good", async () => {
      const dropped = {
        action: { id: "bookmark-git-basics" },
      } as unknown as Awaited<ReturnType<typeof dropQueuedBookmark>>;
      vi.mocked(dropQueuedBookmark).mockResolvedValue(dropped);
      vi.mocked(fetchApi).mockImplementation(async (url: string) => {
        if (url === "/progress/bookmarks/") return [sampleBookmark];
        throw createApiError({ status: 500 });
      });
      const { result } = renderHook(() => useBookmarks(), {
        wrapper: createWrapper(),
      });
      await waitFor(() => expect(result.current.bookmarks).toHaveLength(1));

      act(() => {
        result.current.toggleBookmark.mutate({
          slug: "git-basics",
          isBookmarked: true,
        });
      });

      await waitFor(() =>
        expect(mockAddToast).toHaveBeenCalledWith(
          "Failed to update bookmark.",
          "error",
        ),
      );
      expect(restoreQueuedBookmark).toHaveBeenCalledWith(dropped);
      expect(result.current.isBookmarked("git-basics")).toBe(true);
    });

    it("does not bring the queued change back when the removal went through", async () => {
      vi.mocked(dropQueuedBookmark).mockResolvedValue({
        action: { id: "bookmark-git-basics" },
      } as unknown as Awaited<ReturnType<typeof dropQueuedBookmark>>);
      vi.mocked(fetchApi).mockImplementation(async (url: string) =>
        url === "/progress/bookmarks/" ? [sampleBookmark] : {},
      );
      const { result } = renderHook(() => useBookmarks(), {
        wrapper: createWrapper(),
      });
      await waitFor(() => expect(result.current.bookmarks).toHaveLength(1));

      act(() => {
        result.current.toggleBookmark.mutate({
          slug: "git-basics",
          isBookmarked: true,
        });
      });

      await waitFor(() =>
        expect(result.current.announcement?.type).toBe("success"),
      );
      expect(restoreQueuedBookmark).not.toHaveBeenCalled();
    });

    it("keeps the server id of a bookmark whose queued removal was undone", async () => {
      serverList([]);
      vi.mocked(queueBookmarkChange).mockResolvedValue({
        outcome: "cancelled",
        restoredId: 5,
      });
      const { result } = renderHook(() => useBookmarks(), {
        wrapper: createWrapper(),
      });
      await waitFor(() => expect(result.current.isLoading).toBe(false));
      onlineManager.setOnline(false);
      Object.defineProperty(navigator, "onLine", { value: false });

      act(() => {
        result.current.toggleBookmark.mutate({
          slug: "git-basics",
          isBookmarked: false,
        });
      });

      await waitFor(() =>
        expect(result.current.announcement?.type).toBe("success"),
      );
      // A later removal sends this id, so it cannot delete a replacement
      // bookmark saved from another device
      const entry = result.current.bookmarks.find(
        (b) => b.lesson_slug === "git-basics",
      );
      expect(entry).toEqual(
        expect.objectContaining({ id: 5, optimistic: false }),
      );
    });

    it("keeps a queued add in the list when the list is fetched again", async () => {
      vi.mocked(getPendingBookmarkChanges).mockReturnValue(
        new Map([
          ["git-basics", true],
          ["docker-guide", false],
        ]),
      );
      localStorage.setItem(
        "atelier_bookmarks",
        JSON.stringify([{ ...sampleBookmark, optimistic: true }]),
      );
      serverList([sampleBookmark2]);

      const { result } = renderHook(() => useBookmarks(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => expect(result.current.isLoading).toBe(false));
      await waitFor(() =>
        expect(result.current.bookmarks.map((b) => b.lesson_slug)).toEqual([
          "git-basics",
        ]),
      );
      // what is saved for the next visit has the queued changes in it too
      expect(
        JSON.parse(localStorage.getItem("atelier_bookmarks") || "[]").map(
          (b: BookmarkEntry) => b.lesson_slug,
        ),
      ).toEqual(["git-basics"]);
    });
  });
});
