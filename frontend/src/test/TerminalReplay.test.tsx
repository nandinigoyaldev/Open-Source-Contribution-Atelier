import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act, cleanup } from "@testing-library/react";
import { TerminalReplay, ReplayCommand } from "../components/ui/TerminalReplay";

describe("TerminalReplay", () => {
  const mockCommands: ReplayCommand[] = [
    { command: "echo 'hello'", output: "hello\n", typingDelayMs: 10, executionDelayMs: 10 },
    { command: "ls", output: "file1.txt", typingDelayMs: 10, executionDelayMs: 10 },
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
    render(<TerminalReplay sessionName="Test Session" commands={mockCommands} />);
    expect(screen.getByText("Test Session")).toBeInTheDocument();
  });

  it("should type out command and render output automatically", () => {
    render(<TerminalReplay sessionName="Test Session" commands={mockCommands} />);
    
    // Fast forward enough for the first command to be typed and executed
    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  it("should skip to the end when skip button is clicked", () => {
    render(<TerminalReplay sessionName="Test Session" commands={mockCommands} />);
    
    const skipButton = screen.getByTitle("Skip to End");
    
    act(() => {
      fireEvent.click(skipButton);
    });

    // All outputs should be instantly visible
    expect(screen.getByText("hello")).toBeInTheDocument();
    expect(screen.getByText("file1.txt")).toBeInTheDocument();
  });

  it("should pause and resume when play/pause button is toggled", () => {
    render(<TerminalReplay sessionName="Test Session" commands={mockCommands} />);
    
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
    
    const outputElement = screen.queryByText("hello");
    expect(outputElement).not.toBeInTheDocument();

    // Resume
    const playButton = screen.getByTitle("Play");
    act(() => {
      fireEvent.click(playButton);
    });
    
    expect(screen.getByTitle("Pause")).toBeInTheDocument();
    
    act(() => {
      vi.advanceTimersByTime(500);
    });
    
    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  it("should cycle playback speed when speed button is clicked", () => {
    render(<TerminalReplay sessionName="Test Session" commands={mockCommands} />);
    
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
