import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import React from "react";
import { KeyboardShortcutsModal } from "../components/KeyboardShortcutsModal";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

describe("KeyboardShortcutsModal", () => {
  afterEach(() => {
    cleanup();
  });

  it("opens modal when '?' key is pressed", () => {
    render(<KeyboardShortcutsModal />);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    fireEvent.keyDown(window, { key: "?" });

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Navigate to next lesson in current pathway")).toBeInTheDocument();
    expect(screen.getByText("Navigate to previous lesson in current pathway")).toBeInTheDocument();
  });

  it("opens modal when custom event 'toggle-keyboard-shortcuts' is dispatched", () => {
    render(<KeyboardShortcutsModal />);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    fireEvent(window, new CustomEvent("toggle-keyboard-shortcuts"));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("closes modal when 'Esc' key is pressed", () => {
    render(<KeyboardShortcutsModal />);

    fireEvent(window, new CustomEvent("toggle-keyboard-shortcuts"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
