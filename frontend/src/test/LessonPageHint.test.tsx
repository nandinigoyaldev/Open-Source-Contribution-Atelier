import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { LessonPage } from "../pages/LessonPage";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import * as useUserProgressModule from "../hooks/useUserProgress";
import * as lessonsModule from "../lib/lessons";

// Mock TextToSpeechControls and GitGraph so they don't break
vi.mock("../components/ui/TextToSpeechControls", () => ({
  TextToSpeechControls: () => <div data-testid="tts" />,
}));
vi.mock("../components/ui/GitGraph", () => ({
  GitGraph: () => <div data-testid="git-graph" />,
}));
vi.mock("../lib/gitSimulator", () => ({
  createInitialRepo: vi.fn(() => ({})),
  parseGitCommand: vi.fn(() => ({
    error: null,
    output: "Mock success",
    newState: {},
  })),
}));
vi.mock("../features/auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: 1, username: "testuser" },
    isAuthenticated: true,
  }),
}));
vi.mock("../features/ui/ToastContext", () => ({
  useToast: () => ({ addToast: vi.fn() }),
}));

// Provide our own mock data
const customLesson = {
  slug: "test-lesson-hint",
  title: "Hint Testing Lesson",
  description: "Testing the hint gamification",
  explanation: "Some content",
  expected: 'git commit -m "fix"',
  hint: "Use git commit",
  points: 40,
  exercises: [],
  quizzes: [],
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
    </QueryClientProvider>,
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
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.spyOn(lessonsModule, "fetchLessonsApi").mockResolvedValue([
      customLesson,
    ]);
    vi.spyOn(lessonsModule, "fetchLessonContent").mockResolvedValue(
      "Mock markdown",
    );
  });

  it("displays the hint when requested", async () => {
    renderWithProviders(<LessonPage />);

    // 1. Locate the "Need a hint?" button
    const hintToggleBtn = await screen.findByRole("button", {
      name: /Need a hint\?/i,
    });
    expect(hintToggleBtn).toBeInTheDocument();

    // 2. Click the button to reveal hint
    fireEvent.click(hintToggleBtn);

    // 3. Verify the hint text is displayed
    expect(await screen.findByText(/Use git commit/i)).toBeInTheDocument();
  });
});
