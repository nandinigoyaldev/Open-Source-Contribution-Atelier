import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { LessonPage } from "../pages/LessonPage";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import * as useUserProgressModule from "../hooks/useUserProgress";
import * as lessonsModule from "../lib/lessons";

// Mock TextToSpeechControls and GitGraph so they don't break
vi.mock("../components/ui/TextToSpeechControls", () => ({
  TextToSpeechControls: () => <div data-testid="tts" />
}));
vi.mock("../components/ui/GitGraph", () => ({
  GitGraph: () => <div data-testid="git-graph" />
}));
vi.mock("../lib/gitSimulator", () => ({
  createInitialRepo: vi.fn(() => ({})),
  parseGitCommand: vi.fn(() => ({ error: null, output: "Mock success", newState: {} }))
}));

// Provide our own mock data
const customLesson = {
  slug: "test-lesson-hint",
  title: "Hint Testing Lesson",
  description: "Testing the hint gamification",
  explanation: "Some content",
  expected: "git commit -m \"fix\"",
  hint: "Use git commit",
  points: 40,
  exercises: [],
  quizzes: []
};

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/lessons/test-lesson-hint"]}>
        <Routes>
          <Route path="/lessons/:slug" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("LessonPage Gamified Hint Module", () => {
  const mockSyncProgress = vi.fn();

  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    
    vi.spyOn(useUserProgressModule, "useUserProgress").mockReturnValue({
      syncProgress: mockSyncProgress,
      isLessonCompleted: () => false,
      isLoading: false,
    } as any);

    vi.spyOn(lessonsModule, "fetchLessonsApi").mockResolvedValue([customLesson]);
    vi.spyOn(lessonsModule, "fetchLessonContent").mockResolvedValue("Mock markdown");
  });

  it("handles the gamified hint decryption flow with custom data", async () => {
    renderWithProviders(<LessonPage />);

    // 1. Verify initial badge displays full points
    expect(await screen.findByText(/XP Bounties: 40/)).toBeInTheDocument();

    // 2. Locate the "Decrypt Hint" button and verify the cost badge is 50%
    const decryptBtn = await screen.findByRole("button", { name: /Decrypt Hint/i });
    expect(decryptBtn).toBeInTheDocument();
    expect(decryptBtn).toHaveTextContent("-20 XP");

    // 3. Click the button, expecting the confirmation dialogue
    fireEvent.click(decryptBtn);
    expect(await screen.findByText("Confirm Decryption?")).toBeInTheDocument();

    // 4. Click Cancel - should revert back
    const cancelBtn = screen.getByRole("button", { name: /Cancel/i });
    fireEvent.click(cancelBtn);
    expect(screen.queryByText("Confirm Decryption?")).not.toBeInTheDocument();
    
    // 5. Click again, then Pay
    fireEvent.click(screen.getByRole("button", { name: /Decrypt Hint/i }));
    const payBtn = await screen.findByRole("button", { name: /Pay 20 XP/i });
    fireEvent.click(payBtn);

    // 6. Verify hint is revealed
    expect(await screen.findByText("Decrypted Transmission")).toBeInTheDocument();
    expect(screen.getByText("Use git commit")).toBeInTheDocument();

    // 7. Verify XP badge reflects penalty
    expect(screen.getByText(/XP Bounties: 20/)).toBeInTheDocument();
    expect(screen.getByText(/\(-50%\)/)).toBeInTheDocument();

    // 8. Submit a correct command and verify the penalised score is sent to the backend
    const input = screen.getByPlaceholderText("Use git commit");
    fireEvent.change(input, { target: { value: 'git commit -m "fix"' } });
    fireEvent.keyDown(input, { key: "Enter", metaKey: true }); // triggers submit
    
    // It should sync with 20 points
    await waitFor(() => {
      expect(mockSyncProgress).toHaveBeenCalledWith({
        lesson_slug: "test-lesson-hint",
        score: 20, // Reduced from 40
        completed: true
      });
    });
  });
});
