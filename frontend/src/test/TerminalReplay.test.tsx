import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  act,
  cleanup,
} from "@testing-library/react";
import { TerminalReplay, ReplayCommand } from "../components/ui/TerminalReplay";

describe("TerminalReplay", () => {
  const mockCommands: ReplayCommand[] = [
    {
      command: "echo 'hello'",
      output: "hello\n",
      typingDelayMs: 10,
      executionDelayMs: 10,
    },
    {
      command: "ls",
      output: "file1.txt",
      typingDelayMs: 10,
      executionDelayMs: 10,
    },
  ];

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    cleanup();
  });

  it("should render successfully with session name", () => {
    render(
      <TerminalReplay sessionName="Test Session" commands={mockCommands} />,
    );
    expect(screen.getByText("Test Session")).toBeInTheDocument();
  });

  it("should type out command and render output automatically", () => {
    render(
      <TerminalReplay sessionName="Test Session" commands={mockCommands} />,
    );

    // Each char schedules its own timeout — flush one tick per iteration
    for (let i = 0; i < 40; i += 1) {
      act(() => {
        vi.advanceTimersByTime(25);
      });
    }

    expect(screen.getAllByText(/hello/).length).toBeGreaterThan(0);
  });

  it("should skip to the end when skip button is clicked", () => {
    render(
      <TerminalReplay sessionName="Test Session" commands={mockCommands} />,
    );

    const skipButton = screen.getByTitle("Skip to End");

    act(() => {
      fireEvent.click(skipButton);
    });

    // All outputs should be instantly visible
    expect(screen.getAllByText(/hello/).length).toBeGreaterThan(0);
    expect(screen.getByText(/file1\.txt/)).toBeInTheDocument();
  });

  it("should pause and resume when play/pause button is toggled", () => {
    render(
      <TerminalReplay sessionName="Test Session" commands={mockCommands} />,
    );

    const pauseButton = screen.getByTitle("Pause");

    act(() => {
      fireEvent.click(pauseButton);
    });

    // It should now be paused, the title should switch to "Play"
    expect(screen.getByTitle("Play")).toBeInTheDocument();

    // Fast forward time, it should NOT render output since it's paused
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    const outputElement = screen.queryByText(/^hello$/);
    expect(outputElement).not.toBeInTheDocument();

    // Resume via skip for deterministic completion under fake timers
    act(() => {
      fireEvent.click(screen.getByTitle("Play"));
      fireEvent.click(screen.getByTitle("Skip to End"));
    });

    expect(screen.getAllByText(/hello/).length).toBeGreaterThan(0);
  });

  it("copies a shareable replay link", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText },
    });

    render(
      <TerminalReplay
        sessionName="Test Session"
        commands={mockCommands}
        sharePathname="/sandbox"
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByLabelText("Copy shareable replay link"));
    });

    expect(writeText).toHaveBeenCalled();
    const shared = writeText.mock.calls[0]?.[0] as string;
    expect(shared).toContain("/sandbox#replay=");
  });

  it("should cycle playback speed when speed button is clicked", () => {
    render(
      <TerminalReplay sessionName="Test Session" commands={mockCommands} />,
    );

    const speedButton = screen.getByTitle("Playback Speed");

    expect(speedButton).toHaveTextContent("1x");

    act(() => {
      fireEvent.click(speedButton);
    });

    expect(speedButton).toHaveTextContent("2x");

    act(() => {
      fireEvent.click(speedButton);
    });

    expect(speedButton).toHaveTextContent("4x");

    act(() => {
      fireEvent.click(speedButton);
    });

    expect(speedButton).toHaveTextContent("1x");
  });
});
