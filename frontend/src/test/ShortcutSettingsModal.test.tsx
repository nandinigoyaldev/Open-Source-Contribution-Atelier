import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  within,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ShortcutSettingsModal } from "../features/shortcuts/ShortcutSettingsModal";
import {
  getShortcutBindings,
  matchesShortcut,
  resetAllShortcuts,
  setShortcut,
} from "../features/shortcuts/store";
import { DEFAULT_BINDINGS } from "../features/shortcuts/registry";
import { KeyboardShortcutsModal } from "../components/KeyboardShortcutsModal";
import { ProfileSettingsPage } from "../pages/ProfileSettingsPage";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));
vi.mock("../features/auth/ProfileSettingsForm", () => ({
  ProfileSettingsForm: () => <div />,
}));

const NOTES = "Toggle user notes panel";

const row = (id: string) => within(screen.getByTestId(`shortcut-row-${id}`));
const record = (description: string) =>
  fireEvent.click(
    screen.getByRole("button", { name: `Change shortcut: ${description}` }),
  );

function upload(contents: string) {
  fireEvent.change(screen.getByLabelText("Shortcuts JSON file"), {
    target: {
      files: [new File([contents], "keys.json", { type: "application/json" })],
    },
  });
}

beforeEach(() => resetAllShortcuts());
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ShortcutSettingsModal", () => {
  const open = (onClose = vi.fn()) =>
    render(<ShortcutSettingsModal isOpen onClose={onClose} />);

  it("renders nothing while closed", () => {
    render(<ShortcutSettingsModal isOpen={false} onClose={vi.fn()} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("records a pressed combination and saves it", () => {
    open();
    record(NOTES);
    // A modifier on its own is not a combination yet.
    fireEvent.keyDown(window, { key: "Alt", altKey: true });
    fireEvent.keyDown(window, { key: "j", altKey: true });

    expect(getShortcutBindings()["lesson.toggleNotes"]).toEqual(["Alt+J"]);
    expect(row("lesson.toggleNotes").getByText("Alt J")).toBeInTheDocument();
    expect(screen.getByText("Shortcut saved.")).toBeInTheDocument();
  });

  it("keeps recorded keys away from other listeners", () => {
    const outside = vi.fn();
    window.addEventListener("keydown", outside);
    open();
    record(NOTES);
    fireEvent.keyDown(document.body, { key: "j", altKey: true });
    window.removeEventListener("keydown", outside);

    expect(outside).not.toHaveBeenCalled();
  });

  it("asks before saving a combination that clashes", () => {
    open();
    record(NOTES);
    fireEvent.keyDown(window, { key: "h", altKey: true });

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Toggle mentor support request panel",
    );
    expect(getShortcutBindings()["lesson.toggleNotes"]).toEqual(["Alt+C"]);

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(getShortcutBindings()["lesson.toggleNotes"]).toEqual(["Alt+C"]);

    record(NOTES);
    fireEvent.keyDown(window, { key: "h", altKey: true });
    fireEvent.click(screen.getByRole("button", { name: "Save anyway" }));

    expect(getShortcutBindings()["lesson.toggleNotes"]).toEqual(["Alt+H"]);
    // Both rows keep showing the clash after it is saved.
    expect(
      row("lesson.toggleHelp").getByText(/already used by/),
    ).toBeInTheDocument();
    expect(
      row("lesson.toggleNotes").getByText(/already used by/),
    ).toBeInTheDocument();
  });

  it("warns about a browser shortcut", () => {
    open();
    record(NOTES);
    fireEvent.keyDown(window, { key: "t", ctrlKey: true });
    expect(screen.getByRole("alert")).toHaveTextContent(/new tab/);
  });

  it("explains why a key is refused and keeps recording", () => {
    open();
    record("Clear the sandbox terminal");
    fireEvent.keyDown(window, { key: "j" });
    expect(screen.getByRole("alert")).toHaveTextContent(/while you type/);

    fireEvent.keyDown(window, { key: "j", altKey: true });
    expect(getShortcutBindings()["terminal.clear"]).toEqual(["Alt+J"]);
  });

  it("cancels recording with Escape and closes on the next one", () => {
    const onClose = vi.fn();
    open(onClose);
    record(NOTES);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.queryByText(/Press the new key/)).not.toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("stops recording on Tab", () => {
    open();
    record(NOTES);
    fireEvent.keyDown(window, { key: "Tab" });
    expect(screen.queryByText(/Press the new key/)).not.toBeInTheDocument();
  });

  it("suspends shortcuts only while it is open", () => {
    const key = { key: "h", altKey: true };
    const view = open();
    expect(matchesShortcut(key, "lesson.toggleHelp")).toBe(false);
    view.unmount();
    expect(matchesShortcut(key, "lesson.toggleHelp")).toBe(true);
  });

  it("resets one shortcut or all of them", () => {
    setShortcut("lesson.toggleNotes", ["Alt+J"]);
    setShortcut("lesson.next", ["Alt+K"]);
    open();

    fireEvent.click(
      screen.getByRole("button", { name: `Reset shortcut: ${NOTES}` }),
    );
    expect(getShortcutBindings()["lesson.toggleNotes"]).toEqual(["Alt+C"]);
    expect(getShortcutBindings()["lesson.next"]).toEqual(["Alt+K"]);

    fireEvent.click(screen.getByRole("button", { name: "Reset to Defaults" }));
    expect(getShortcutBindings()).toEqual(DEFAULT_BINDINGS);
  });

  it("exports the shortcuts as a JSON file", async () => {
    setShortcut("lesson.next", ["Alt+K"]);
    let blob: Blob | undefined;
    URL.createObjectURL = vi.fn((value) => {
      blob = value as Blob;
      return "blob:shortcuts";
    });
    URL.revokeObjectURL = vi.fn();
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});
    open();

    fireEvent.click(screen.getByRole("button", { name: "Export JSON" }));

    expect(click).toHaveBeenCalledTimes(1);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:shortcuts");
    const text = await new Promise<string>((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.readAsText(blob!);
    });
    expect(JSON.parse(text).shortcuts["lesson.next"]).toEqual(["Alt+K"]);
  });

  it("imports a valid file", async () => {
    open();
    upload('{"version":1,"shortcuts":{"lesson.next":["Alt+K"]}}');

    expect(await screen.findByText("Shortcuts imported.")).toBeInTheDocument();
    expect(getShortcutBindings()["lesson.next"]).toEqual(["Alt+K"]);
  });

  it("shows why a file was rejected", async () => {
    open();
    upload('{"version":1,"shortcuts":{"nope":["Alt+K"]}}');

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        'Unknown shortcut "nope"',
      ),
    );
    expect(getShortcutBindings()).toEqual(DEFAULT_BINDINGS);
  });
});

describe("where shortcuts are shown and edited", () => {
  it("lists the saved keys in the cheat sheet", () => {
    setShortcut("lesson.toggleNotes", ["Alt+J"]);
    setShortcut("help.toggle", ["F2"]);
    render(<KeyboardShortcutsModal />);

    fireEvent.keyDown(window, { key: "?" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    fireEvent.keyDown(window, { key: "F2" });
    const dialog = within(screen.getByRole("dialog"));
    expect(dialog.getByText("Alt J")).toBeInTheDocument();
    expect(dialog.queryByText("Alt C")).not.toBeInTheDocument();
  });

  it("opens the editor from the cheat sheet", () => {
    render(<KeyboardShortcutsModal />);
    fireEvent.keyDown(window, { key: "?" });
    fireEvent.click(
      screen.getByRole("button", { name: "Customize shortcuts" }),
    );

    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    expect(
      screen.getByRole("dialog", { name: "Customize shortcuts" }),
    ).toBeInTheDocument();
  });

  it("opens the editor from profile settings", () => {
    render(
      <MemoryRouter>
        <ProfileSettingsPage />
      </MemoryRouter>,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Customize shortcuts" }),
    );
    expect(
      screen.getByRole("dialog", { name: "Customize shortcuts" }),
    ).toBeInTheDocument();
  });
});
