import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { Navigation } from "../components/layout/Navigation";
import { LessonSearchModal } from "../components/Search/LessonSearchModal";
import { GitTerminal } from "../components/ui/GitTerminal";
import { ThemeProvider } from "../context/ThemeContext";
import * as lessonSearchHook from "../hooks/useLessonSearch";
import { resetAllShortcuts, setShortcut } from "../features/shortcuts/store";

vi.mock("../features/auth/AuthContext", () => ({
  useAuth: () => ({ user: null }),
}));

function CurrentPath() {
  return <div data-testid="path">{useLocation().pathname}</div>;
}

beforeEach(() => {
  resetAllShortcuts();
  Element.prototype.scrollIntoView = vi.fn();
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
});
afterEach(() => cleanup());

describe("remapped shortcuts trigger the existing handlers", () => {
  it("goes to the dashboard with the new key only", () => {
    setShortcut("nav.dashboard", ["Alt+G"]);
    setShortcut("help.toggle", ["F2"]);
    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={["/profile"]}>
          <Navigation />
          <CurrentPath />
        </MemoryRouter>
      </ThemeProvider>,
    );

    expect(
      screen.getByRole("button", { name: "Keyboard shortcuts (F2)" }),
    ).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "/" });
    expect(screen.getByTestId("path")).toHaveTextContent("/profile");

    fireEvent.keyDown(window, { key: "g", altKey: true });
    expect(screen.getByTestId("path")).toHaveTextContent("/dashboard");
  });

  it("closes lesson search with the new key only", () => {
    vi.spyOn(lessonSearchHook, "useLessonSearch").mockReturnValue({
      search: vi.fn().mockReturnValue([]),
      loading: false,
      lessons: [],
      error: null,
    });
    setShortcut("search.toggle", ["Alt+J"]);
    const onClose = vi.fn();
    render(
      <MemoryRouter>
        <LessonSearchModal isOpen onClose={onClose} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("combobox")).toHaveAttribute(
      "placeholder",
      expect.stringContaining("(Alt J)"),
    );
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.keyDown(window, { key: "j", altKey: true });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("clears the terminal with the new key only", () => {
    setShortcut("terminal.clear", ["Ctrl+K"]);
    render(
      <MemoryRouter>
        <GitTerminal />
      </MemoryRouter>,
    );
    const input = screen.getByLabelText(
      "Git terminal input",
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "git status" } });

    fireEvent.keyDown(input, { key: "l", ctrlKey: true });
    expect(input.value).toBe("git status");

    fireEvent.keyDown(input, { key: "k", ctrlKey: true });
    expect(input.value).toBe("");
  });
});
