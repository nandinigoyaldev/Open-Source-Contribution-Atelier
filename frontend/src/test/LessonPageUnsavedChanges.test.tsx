import {
  act,
  render,
  screen,
  fireEvent,
  cleanup,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { LessonPage } from "../pages/LessonPage";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import * as useUserProgressModule from "../hooks/useUserProgress";
import * as lessonsModule from "../lib/lessons";
import type { Lesson } from "../lib/lessons";

// Mock TextToSpeechControls and GitGraph so they don't break
vi.mock("../components/ui/TextToSpeechControls", () => ({
  TextToSpeechControls: () => <div data-testid="tts" />,
}));
vi.mock("../components/ui/GitGraph", () => ({
  GitGraph: () => <div data-testid="git-graph" />,
}));
vi.mock("../lib/gitSimulator", () => ({
  createInitialRepo: vi.fn(() => ({ conflicts: [] })),
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

vi.mock("../features/notifications/NotificationContext", () => ({
  useNotifications: () => ({
    triggerConfetti: vi.fn(),
    notifications: [],
    unreadCount: 0,
  }),
}));

// Mock Monaco editor and its CSS imports
vi.mock("@monaco-editor/react", () => ({
  __esModule: true,
  default: () => <div data-testid="monaco-editor" />,
  useMonaco: () => null,
}));

// Mock InteractiveDebugger to avoid Monaco dependency
vi.mock("../components/ui/InteractiveDebugger", () => ({
  InteractiveDebugger: () => <div data-testid="interactive-debugger" />,
}));

// Mock CollabPythonSandbox and JSSandbox to avoid heavy deps
vi.mock("../components/ui/CollabPythonSandbox", () => ({
  CollabPythonSandbox: () => <div data-testid="collab-python-sandbox" />,
}));
vi.mock("../components/ui/JSSandbox", () => ({
  JSSandbox: () => <div data-testid="js-sandbox" />,
}));
vi.mock("../components/ui/PythonSandbox", () => ({
  PythonSandbox: () => <div data-testid="python-sandbox" />,
}));
vi.mock("../components/ui/RichTextEditor", () => ({
  RichTextEditor: () => <div data-testid="rich-text-editor" />,
}));
vi.mock("../components/ui/NotePanel", () => ({
  NotePanel: () => <div data-testid="note-panel" />,
}));

const baseLesson = {
  id: 0,
  title: "Unsaved Work Lesson",
  description: "Testing the leave warning",
  explanation: "Some content",
  expected: 'git commit -m "fix"',
  hint: "Use git commit",
  points: 40,
  exercises: [],
  quizzes: [],
};
const currentLesson = { ...baseLesson, id: 1, slug: "lesson-b" };
const prevLesson = {
  ...baseLesson,
  id: 0,
  slug: "lesson-a",
  title: "Lesson A",
};
const nextLesson = {
  ...baseLesson,
  id: 2,
  slug: "lesson-c",
  title: "Lesson C",
};

function CurrentPath() {
  return <div data-testid="path">{useLocation().pathname}</div>;
}

function renderLesson() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/lessons/lesson-b"]}>
        <CurrentPath />
        <Routes>
          <Route path="/lessons/:slug" element={<LessonPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function fireBeforeUnload() {
  const event = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(event);
  return event.defaultPrevented;
}

describe("LessonPage unsaved work warning", () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    // setup.ts installs fake timers; the page and findBy* need real ones
    // eslint-disable-next-line no-restricted-syntax -- page effects and findBy* need real timers
    vi.useRealTimers();

    vi.spyOn(useUserProgressModule, "useUserProgress").mockReturnValue({
      syncProgress: vi.fn(),
      isLessonCompleted: () => true,
      isLoading: false,
    } as any);
    vi.spyOn(lessonsModule, "fetchLessonsApiResult").mockResolvedValue({
      lessons: [prevLesson, currentLesson, nextLesson] as unknown as Lesson[],
      fromApi: true,
    });
    vi.spyOn(lessonsModule, "fetchLessonContent").mockResolvedValue(
      "Mock markdown",
    );
  });

  async function findTerminalInput() {
    const input = (await screen.findByPlaceholderText(
      /Use git commit/i,
    )) as HTMLInputElement;
    // The page resets the typed command when its offline-ready state first
    // settles, so let that happen before the tests type anything.
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 200));
    });
    return input;
  }

  it("does not warn or block when nothing was typed", async () => {
    renderLesson();
    await findTerminalInput();

    expect(fireBeforeUnload()).toBe(false);

    fireEvent.click(
      await screen.findByRole("link", { name: /Next: Lesson C/i }),
    );
    expect(screen.getByTestId("path")).toHaveTextContent("/lessons/lesson-c");
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("warns on browser unload while a command is typed", async () => {
    renderLesson();
    const input = await findTerminalInput();

    fireEvent.change(input, { target: { value: "git comm" } });

    expect(fireBeforeUnload()).toBe(true);

    fireEvent.change(input, { target: { value: "" } });
    expect(fireBeforeUnload()).toBe(false);
  });

  it("asks before the Next link leaves, and Stay keeps the lesson and the text", async () => {
    renderLesson();
    const input = await findTerminalInput();
    fireEvent.change(input, { target: { value: "git comm" } });

    fireEvent.click(screen.getByRole("link", { name: /Next: Lesson C/i }));

    expect(await screen.findByRole("alertdialog")).toBeInTheDocument();
    expect(screen.getByTestId("path")).toHaveTextContent("/lessons/lesson-b");

    fireEvent.click(screen.getByRole("button", { name: /stay here/i }));

    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(screen.getByTestId("path")).toHaveTextContent("/lessons/lesson-b");
    expect(input.value).toBe("git comm");
  });

  it("leaves for the clicked lesson after Discard", async () => {
    renderLesson();
    const input = await findTerminalInput();
    fireEvent.change(input, { target: { value: "git comm" } });

    fireEvent.click(screen.getByRole("link", { name: /Prev: Lesson A/i }));
    fireEvent.click(
      await screen.findByRole("button", { name: /discard changes/i }),
    );

    expect(screen.getByTestId("path")).toHaveTextContent("/lessons/lesson-a");
  });

  it("asks before the Alt+ArrowRight shortcut leaves", async () => {
    renderLesson();
    const input = await findTerminalInput();
    fireEvent.change(input, { target: { value: "git comm" } });
    input.blur();

    fireEvent.keyDown(window, { key: "ArrowRight", altKey: true });

    expect(await screen.findByRole("alertdialog")).toBeInTheDocument();
    expect(screen.getByTestId("path")).toHaveTextContent("/lessons/lesson-b");
  });
});
