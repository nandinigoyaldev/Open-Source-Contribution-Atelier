import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useLessonNote } from "../hooks/useLessonNote";
import { fetchApi } from "../lib/api";
import React from "react";
import { vi, describe, it, beforeEach, expect } from "vitest";

// Mock fetchApi
vi.mock("../lib/api", () => ({
  fetchApi: vi.fn(),
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

describe("useLessonNote", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches note correctly", async () => {
    const mockNote = { content: "Test note" };
    vi.mocked(fetchApi).mockResolvedValueOnce(mockNote);

    const { result } = renderHook(() => useLessonNote("test-lesson"), {
      wrapper: createWrapper(),
    });

    // Wait for the query to be fulfilled (not loading anymore)
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.note).toEqual(mockNote);
    expect(fetchApi).toHaveBeenCalledWith("/progress/notes/test-lesson/");
  });

  it("saves note correctly", async () => {
    vi.mocked(fetchApi).mockResolvedValueOnce({ content: "" }); // initial fetch
    const { result } = renderHook(() => useLessonNote("test-lesson"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    vi.mocked(fetchApi).mockResolvedValueOnce({ content: "Updated note" }); // mutation response

    result.current.saveNote("Updated note");

    await waitFor(() => expect(result.current.isSaving).toBe(false));

    expect(fetchApi).toHaveBeenCalledWith("/progress/notes/test-lesson/", {
      method: "POST",
      body: JSON.stringify({ content: "Updated note" }),
    });
  });
});
