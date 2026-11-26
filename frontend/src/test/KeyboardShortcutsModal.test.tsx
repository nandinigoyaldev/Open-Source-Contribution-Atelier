import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
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

  describe("Open & Close behavior", () => {
    it("opens modal when '?' key is pressed", () => {
      render(<KeyboardShortcutsModal />);

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

      fireEvent.keyDown(window, { key: "?" });

      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByText("Keyboard Shortcuts")).toBeInTheDocument();
      expect(
        screen.getByText("Toggle this Keyboard Shortcuts Cheat Sheet modal"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Navigate to next lesson in current pathway"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Navigate to previous lesson in current pathway"),
      ).toBeInTheDocument();
    });

    it("opens modal when custom event 'toggle-keyboard-shortcuts' is dispatched", () => {
      render(<KeyboardShortcutsModal />);

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

      fireEvent(window, new CustomEvent("toggle-keyboard-shortcuts"));

      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    it("opens modal when custom event 'open-keyboard-shortcuts' is dispatched", () => {
      render(<KeyboardShortcutsModal />);

      fireEvent(window, new CustomEvent("open-keyboard-shortcuts"));

      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    it("toggles modal closed when '?' key is pressed again", () => {
      render(<KeyboardShortcutsModal />);

      fireEvent.keyDown(window, { key: "?" });
      expect(screen.getByRole("dialog")).toBeInTheDocument();

      fireEvent.keyDown(window, { key: "?" });
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("closes modal when 'Escape' key is pressed", () => {
      render(<KeyboardShortcutsModal />);

      fireEvent(window, new CustomEvent("open-keyboard-shortcuts"));
      expect(screen.getByRole("dialog")).toBeInTheDocument();

      fireEvent.keyDown(window, { key: "Escape" });
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("closes modal when close button is clicked", () => {
      render(<KeyboardShortcutsModal />);

      fireEvent(window, new CustomEvent("open-keyboard-shortcuts"));
      expect(screen.getByRole("dialog")).toBeInTheDocument();

      const closeButton = screen.getByTestId("close-shortcuts-button");
      fireEvent.click(closeButton);
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("closes modal when backdrop is clicked", () => {
      render(<KeyboardShortcutsModal />);

      fireEvent(window, new CustomEvent("open-keyboard-shortcuts"));
      expect(screen.getByRole("dialog")).toBeInTheDocument();

      const backdrop = screen.getByTestId("shortcuts-backdrop");
      fireEvent.click(backdrop);
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  describe("Focus management", () => {
    it("moves focus into the dialog on open", () => {
      render(<KeyboardShortcutsModal />);

      fireEvent(window, new CustomEvent("open-keyboard-shortcuts"));

      const closeButton = screen.getByTestId("close-shortcuts-button");
      expect(document.activeElement).toBe(closeButton);
    });

    it("restores focus to the trigger element when closed", () => {
      const button = document.createElement("button");
      button.textContent = "Open Shortcuts";
      document.body.appendChild(button);
      button.focus();
      expect(document.activeElement).toBe(button);

      render(<KeyboardShortcutsModal />);

      // Dispatch custom event while button is active
      fireEvent(window, new CustomEvent("open-keyboard-shortcuts"));
      expect(screen.getByRole("dialog")).toBeInTheDocument();

      // Close modal
      const closeButton = screen.getByTestId("close-shortcuts-button");
      fireEvent.click(closeButton);

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(document.activeElement).toBe(button);

      document.body.removeChild(button);
    });
  });

  describe("Typing behavior (inputs and textareas are never hijacked)", () => {
    it("does not open modal when '?' is typed in an <input>", () => {
      render(
        <div>
          <input data-testid="test-input" type="text" />
          <KeyboardShortcutsModal />
        </div>,
      );

      const input = screen.getByTestId("test-input");
      input.focus();

      fireEvent.keyDown(input, { key: "?" });

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("does not open modal when '?' is typed in a <textarea>", () => {
      render(
        <div>
          <textarea data-testid="test-textarea" />
          <KeyboardShortcutsModal />
        </div>,
      );

      const textarea = screen.getByTestId("test-textarea");
      textarea.focus();

      fireEvent.keyDown(textarea, { key: "?" });

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("does not open modal when '?' is typed in a contenteditable element", () => {
      render(
        <div>
          <div data-testid="test-contenteditable" contentEditable={true} />
          <KeyboardShortcutsModal />
        </div>,
      );

      const editable = screen.getByTestId("test-contenteditable");
      editable.focus();

      fireEvent.keyDown(editable, { key: "?" });

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("does not open modal when '?' is pressed in a role='textbox' element", () => {
      render(
        <div>
          <div data-testid="test-textbox" role="textbox" tabIndex={0} />
          <KeyboardShortcutsModal />
        </div>,
      );

      const textbox = screen.getByTestId("test-textbox");
      textbox.focus();

      fireEvent.keyDown(textbox, { key: "?" });

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("does not trigger shortcut when modified by Ctrl or Meta keys", () => {
      render(<KeyboardShortcutsModal />);

      fireEvent.keyDown(window, { key: "?", ctrlKey: true });
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

      fireEvent.keyDown(window, { key: "?", metaKey: true });
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });
});
