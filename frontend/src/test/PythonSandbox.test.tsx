import React from "react";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { PythonSandbox } from "../components/ui/PythonSandbox";
import { usePythonSandbox } from "../hooks/usePythonSandbox";

// Mock the hook
vi.mock("../hooks/usePythonSandbox", () => ({
  usePythonSandbox: vi.fn(),
}));

describe("PythonSandbox UI", () => {
  const mockOnSuccess = vi.fn();
  const defaultExercise = {
    prompt: "Print hello",
    starterCode: "print('hi')",
    testCode: "assert True",
    hint: "Use print",
  };

  const mockRunPythonCode = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    (usePythonSandbox as any).mockReturnValue({
      isReady: true,
      isExecuting: false,
      runPythonCode: mockRunPythonCode,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("renders correctly with starter code", () => {
    render(
      <PythonSandbox exercise={defaultExercise} onSuccess={mockOnSuccess} />,
    );
    expect(screen.getByText("Print hello")).toBeInTheDocument();
    expect(screen.getByText("Run")).toBeInTheDocument();
  });

  it("keeps edited code when the same exercise rerenders", () => {
    const props = { exercise: defaultExercise, onSuccess: mockOnSuccess };
    const { rerender } = render(<PythonSandbox {...props} />);
    const editor = screen.getByRole("textbox");
    fireEvent.change(editor, { target: { value: "print('edited')" } });
    rerender(<PythonSandbox {...props} />);
    expect(editor).toHaveValue("print('edited')");
  });

  it("displays execution output", async () => {
    mockRunPythonCode.mockResolvedValueOnce({ output: "hello", error: null });

    render(
      <PythonSandbox exercise={defaultExercise} onSuccess={mockOnSuccess} />,
    );

    fireEvent.click(screen.getByText("Run"));

    await waitFor(() => {
      expect(screen.getByText("hello")).toBeInTheDocument();
    });
  });

  it("displays syntax errors properly", async () => {
    mockRunPythonCode.mockResolvedValueOnce({
      output: "",
      error: "SyntaxError: invalid syntax",
    });

    render(
      <PythonSandbox exercise={defaultExercise} onSuccess={mockOnSuccess} />,
    );

    fireEvent.click(screen.getByText("Run"));

    await waitFor(() => {
      expect(
        screen.getByText("SyntaxError: invalid syntax"),
      ).toBeInTheDocument();
    });
  });

  it("handles testCode assertions and calls onSuccess", async () => {
    // Both user code and test code succeed
    mockRunPythonCode.mockResolvedValueOnce({
      output: "tests passed",
      error: null,
    });

    render(
      <PythonSandbox exercise={defaultExercise} onSuccess={mockOnSuccess} />,
    );

    fireEvent.click(screen.getByText("Run"));

    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalled();
    });
  });
});

describe("PythonSandbox output display controls (#2714)", () => {
  const mockOnSuccess = vi.fn();
  const exercise = {
    prompt: "Print hello",
    starterCode: "print('hi')",
    testCode: "assert True",
    hint: "Use print",
  };
  const mockRunPythonCode = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    (usePythonSandbox as any).mockReturnValue({
      isReady: true,
      isExecuting: false,
      runPythonCode: mockRunPythonCode,
    });
  });

  afterEach(() => {
    cleanup();
  });

  function renderSandbox() {
    return render(
      <PythonSandbox exercise={exercise} onSuccess={mockOnSuccess} />,
    );
  }

  it("renders a font-size selector and a word-wrap toggle", () => {
    renderSandbox();
    expect(screen.getByLabelText("Font")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Wrap:/ })).toBeInTheDocument();
  });

  it("defaults to 14px with wrap enabled", () => {
    renderSandbox();
    expect(screen.getByLabelText("Font")).toHaveValue("14");
    const toggle = screen.getByRole("button", { name: /Wrap:/ });
    expect(toggle).toHaveTextContent("Wrap: On");
    expect(toggle).toHaveAttribute("aria-pressed", "true");
  });

  it("persists the chosen font size to localStorage and applies it", () => {
    renderSandbox();
    fireEvent.change(screen.getByLabelText("Font"), {
      target: { value: "16" },
    });

    expect(localStorage.getItem("pythonSandbox.output.fontSize")).toBe("16");
    expect(screen.getByText("No output...")).toHaveStyle({ fontSize: "16px" });
  });

  it("toggles word wrap, updates the label, persists the choice and swaps the class", async () => {
    mockRunPythonCode.mockResolvedValueOnce({
      output: "a very long line",
      error: null,
    });
    renderSandbox();
    fireEvent.click(screen.getByText("Run"));
    const outputEl = await screen.findByText("a very long line");
    expect(outputEl).toHaveClass("whitespace-pre-wrap");

    fireEvent.click(screen.getByRole("button", { name: /Wrap:/ }));

    expect(screen.getByRole("button", { name: /Wrap:/ })).toHaveTextContent(
      "Wrap: Off",
    );
    expect(localStorage.getItem("pythonSandbox.output.wordWrap")).toBe("false");
    expect(screen.getByText("a very long line")).toHaveClass("whitespace-pre");
  });

  it("restores a previously stored font size on mount", () => {
    localStorage.setItem("pythonSandbox.output.fontSize", "12");
    renderSandbox();
    expect(screen.getByLabelText("Font")).toHaveValue("12");
  });

  it("ignores an invalid stored font size and falls back to 14px", () => {
    localStorage.setItem("pythonSandbox.output.fontSize", "999");
    renderSandbox();
    expect(screen.getByLabelText("Font")).toHaveValue("14");
  });
});
