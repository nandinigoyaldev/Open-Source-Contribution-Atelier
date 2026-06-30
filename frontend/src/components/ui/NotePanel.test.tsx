import React from "react";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import { NotePanel } from "./NotePanel";
import * as useLessonNoteHook from "../../hooks/useLessonNote";

// Mock the hook
vi.mock("../../hooks/useLessonNote", () => ({
  useLessonNote: vi.fn(),
}));

describe("NotePanel", () => {
  const mockOnClose = vi.fn();
  const mockSaveNote = vi.fn();

  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(useLessonNoteHook.useLessonNote).mockReturnValue({
      note: { content: "Initial content" },
      isLoading: false,
      saveNote: mockSaveNote,
      isSaving: false,
      isError: false,
      isSuccess: true,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);
  });

  it("renders correctly with initial content", () => {
    render(<NotePanel lessonSlug="test-lesson" onClose={mockOnClose} />);

    expect(screen.getByText(/Private Notes/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue("Initial content")).toBeInTheDocument();
  });

  it("calls onClose when close button is clicked", () => {
    render(<NotePanel lessonSlug="test-lesson" onClose={mockOnClose} />);

    const closeButtons = screen.getAllByRole("button");
    // The close button is the only button rendered currently (with an X icon)
    fireEvent.click(closeButtons[0]);

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it("debounces saveNote when typing", async () => {
    vi.useFakeTimers();

    render(<NotePanel lessonSlug="test-lesson" onClose={mockOnClose} />);

    const textarea = screen.getByDisplayValue("Initial content");

    fireEvent.change(textarea, { target: { value: "New content" } });

    // Should not save immediately
    expect(mockSaveNote).not.toHaveBeenCalled();

    // Fast forward 500ms
    vi.advanceTimersByTime(500);
    expect(mockSaveNote).not.toHaveBeenCalled();

    // Fast forward remaining 500ms
    vi.advanceTimersByTime(500);

    expect(mockSaveNote).toHaveBeenCalledWith("New content");

    vi.useRealTimers();
  });

  it("displays loading state correctly", () => {
    vi.mocked(useLessonNoteHook.useLessonNote).mockReturnValue({
      note: undefined,
      isLoading: true,
      saveNote: mockSaveNote,
      isSaving: false,
      isError: false,
      isSuccess: false,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    render(<NotePanel lessonSlug="test-lesson" onClose={mockOnClose} />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();

    const textarea = screen.getByPlaceholderText(/Jot down your thoughts/i);
    expect(textarea).toBeDisabled();
  });

  it("displays saving state correctly", () => {
    vi.mocked(useLessonNoteHook.useLessonNote).mockReturnValue({
      note: { content: "" },
      isLoading: false,
      saveNote: mockSaveNote,
      isSaving: true,
      isError: false,
      isSuccess: false,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    render(<NotePanel lessonSlug="test-lesson" onClose={mockOnClose} />);
    expect(screen.getByText("Saving...")).toBeInTheDocument();
  });
});
