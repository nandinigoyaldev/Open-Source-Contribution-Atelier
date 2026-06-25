import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  act,
  renderHook,
  cleanup,
  fireEvent,
} from "@testing-library/react";
import { ToastProvider, useToast } from "./ToastContext";

// Mock framer-motion to avoid animation delays in tests
vi.mock("framer-motion", async () => {
  const actual = await vi.importActual("framer-motion");
  return {
    ...actual,
    AnimatePresence: ({ children }: { children: React.ReactNode }) => (
      <>{children}</>
    ),
    motion: {
      div: ({
        children,
        className,
      }: {
        children: React.ReactNode;
        className?: string;
      }) => <div className={className}>{children}</div>,
    },
  };
});

// A simple test component to trigger toasts
const TestComponent = ({
  duration,
  type = "success",
}: {
  duration?: number;
  type?: "success" | "error" | "info" | "warning";
}) => {
  const { addToast } = useToast();

  return (
    <button onClick={() => addToast("Test Message", type, duration)}>
      Trigger Toast
    </button>
  );
};

describe("ToastContext Edge Cases", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    cleanup();
  });

  it("throws an error if useToast is used outside of ToastProvider", () => {
    // Suppress console.error for expected thrown error
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => renderHook(() => useToast())).toThrow(
      "useToast must be used within a ToastProvider",
    );

    consoleSpy.mockRestore();
  });

  it("adds a toast to the screen when triggered", async () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>,
    );

    const button = screen.getByText("Trigger Toast");
    fireEvent.click(button);

    expect(screen.getByText("Test Message")).toBeInTheDocument();
  });

  it("auto-dismisses the toast after the default 5000ms duration", async () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>,
    );

    const button = screen.getByText("Trigger Toast");
    fireEvent.click(button);

    expect(screen.getByText("Test Message")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(4999);
    });
    // Still there
    expect(screen.getByText("Test Message")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    // Should be gone
    expect(screen.queryByText("Test Message")).not.toBeInTheDocument();
  });

  it("auto-dismisses after a custom duration", async () => {
    render(
      <ToastProvider>
        <TestComponent duration={2000} />
      </ToastProvider>,
    );

    const button = screen.getByText("Trigger Toast");
    fireEvent.click(button);

    expect(screen.getByText("Test Message")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(screen.queryByText("Test Message")).not.toBeInTheDocument();
  });

  it("does not auto-dismiss if duration is 0", async () => {
    render(
      <ToastProvider>
        <TestComponent duration={0} />
      </ToastProvider>,
    );

    const button = screen.getByText("Trigger Toast");
    fireEvent.click(button);

    expect(screen.getByText("Test Message")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(100000); // Wait a long time
    });

    // Still there
    expect(screen.getByText("Test Message")).toBeInTheDocument();
  });

  it("manually dismisses the toast when the close button is clicked", async () => {
    render(
      <ToastProvider>
        <TestComponent duration={0} />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByText("Trigger Toast"));
    expect(screen.getByText("Test Message")).toBeInTheDocument();

    const closeButton = screen.getByRole("button", {
      name: /Close notification/i,
    });
    fireEvent.click(closeButton);

    expect(screen.queryByText("Test Message")).not.toBeInTheDocument();
  });

  it("handles multiple toasts correctly (stacking)", async () => {
    const MultiToastComponent = () => {
      const { addToast } = useToast();
      return (
        <button
          onClick={() => {
            addToast("Toast 1", "success", 0);
            addToast("Toast 2", "error", 0);
            addToast("Toast 3", "info", 0);
          }}
        >
          Trigger Multiple
        </button>
      );
    };

    render(
      <ToastProvider>
        <MultiToastComponent />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByText("Trigger Multiple"));

    expect(screen.getByText("Toast 1")).toBeInTheDocument();
    expect(screen.getByText("Toast 2")).toBeInTheDocument();
    expect(screen.getByText("Toast 3")).toBeInTheDocument();

    // Close Toast 2
    const closeButtons = screen.getAllByRole("button", {
      name: /Close notification/i,
    });
    fireEvent.click(closeButtons[1]); // Assuming order is kept

    expect(screen.getByText("Toast 1")).toBeInTheDocument();
    expect(screen.queryByText("Toast 2")).not.toBeInTheDocument();
    expect(screen.getByText("Toast 3")).toBeInTheDocument();
  });
});
