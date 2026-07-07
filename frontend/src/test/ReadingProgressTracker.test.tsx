import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, cleanup, waitFor, act } from "@testing-library/react";
import { ReadingProgressTracker } from "../components/ui/ReadingProgressTracker";
import { fetchApi } from "../lib/api";

// Mock the API fetch
vi.mock("../lib/api", () => ({
  fetchApi: vi.fn(),
}));

describe("ReadingProgressTracker", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // Setup a mock IntersectionObserver
    const mockIntersectionObserver = vi.fn();
    mockIntersectionObserver.mockReturnValue({
      observe: () => null,
      unobserve: () => null,
      disconnect: () => null,
    });
    window.IntersectionObserver = mockIntersectionObserver as any;
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
    cleanup();
  });

  it("should fetch initial progress on mount", async () => {
    (fetchApi as any).mockResolvedValueOnce({ progress: 50 });

    render(<ReadingProgressTracker lessonSlug="test-lesson" />);
    
    await act(async () => {
      vi.runAllTimers();
    });
    
    expect(fetchApi).toHaveBeenCalledWith("/api/progress/reading-position/?lesson=test-lesson");
  });

  it("should render progress bar if progress > 0", async () => {
    (fetchApi as any).mockResolvedValueOnce({ progress: 75 });
    
    const { container } = render(<ReadingProgressTracker lessonSlug="test-lesson" />);
    
    await waitFor(() => {
      expect(fetchApi).toHaveBeenCalled();
    });
    
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    
    // The progress bar div with width style
    const bar = container.querySelector(".bg-emerald-500");
    expect(bar).toBeInTheDocument();
    expect(bar).toHaveStyle("width: 75%");
  });

  it("should attempt to scroll to position if initial progress > 0", async () => {
    (fetchApi as any).mockResolvedValueOnce({ progress: 50 });
    
    // Mock the container and children
    const mockChild = { scrollIntoView: vi.fn() };
    const mockContainer = { children: [mockChild, mockChild, mockChild, mockChild] };
    vi.spyOn(document, 'querySelector').mockReturnValue(mockContainer as any);
    
    render(<ReadingProgressTracker lessonSlug="test-lesson" />);
    
    await waitFor(() => {
      expect(fetchApi).toHaveBeenCalled();
    });

    // Fast forward the 1500ms init delay + 1000ms scroll delay
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    
    expect(document.querySelector).toHaveBeenCalledWith(".markdown-body");
    // Should have called scrollIntoView on the correct child (50% of 4 children = index 2)
    expect(mockChild.scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "start" });
  });
});
