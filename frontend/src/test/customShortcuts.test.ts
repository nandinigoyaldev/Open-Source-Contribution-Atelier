import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import {
  comboFromEvent,
  comboLabels,
  combosOverlap,
  matchesCombo,
  parseCombo,
} from "../features/shortcuts/combo";
import {
  findCollisions,
  validateCombo,
} from "../features/shortcuts/collisions";
import { DEFAULT_BINDINGS } from "../features/shortcuts/registry";
import {
  SHORTCUTS_STORAGE_KEY,
  exportShortcuts,
  getShortcutBindings,
  importShortcuts,
  matchesShortcut,
  resetAllShortcuts,
  resetShortcut,
  setShortcut,
  suspendShortcuts,
} from "../features/shortcuts/store";
import { useCustomShortcuts } from "../features/shortcuts/useCustomShortcuts";

const press = (key: string, extra: Record<string, unknown> = {}) => ({
  key,
  ...extra,
});

beforeEach(() => {
  resetAllShortcuts();
  localStorage.clear();
});

describe("key combinations", () => {
  it("reads the combination from a key press", () => {
    expect(comboFromEvent(press("n", { altKey: true }))).toBe("Alt+N");
    expect(comboFromEvent(press("C", { ctrlKey: true, shiftKey: true }))).toBe(
      "Ctrl+Shift+C",
    );
    expect(comboFromEvent(press(" ", { ctrlKey: true }))).toBe("Ctrl+Space");
    expect(comboFromEvent(press("+", { ctrlKey: true }))).toBe("Ctrl+Plus");
  });

  it("ignores Shift for symbols, which depend on the layout", () => {
    expect(comboFromEvent(press("?", { shiftKey: true }))).toBe("?");
    expect(matchesCombo(press("?", { shiftKey: true }), "?")).toBe(true);
  });

  it("ignores modifiers pressed on their own and AltGr", () => {
    expect(comboFromEvent(press("Alt", { altKey: true }))).toBeNull();
    const altGr = press("@", {
      ctrlKey: true,
      altKey: true,
      getModifierState: (name: string) => name === "AltGraph",
    });
    expect(comboFromEvent(altGr)).toBeNull();
  });

  it("uses the physical key when Alt produces another character", () => {
    expect(comboFromEvent(press("˙", { altKey: true, code: "KeyH" }))).toBe(
      "Alt+H",
    );
    expect(comboFromEvent(press("Dead", { altKey: true, code: "KeyN" }))).toBe(
      "Alt+N",
    );
    // Without a modifier the typed character is what counts.
    expect(comboFromEvent(press("é", { code: "Digit2" }))).toBe("É");
  });

  it("matches the typed key before falling back to the physical key", () => {
    const file = { version: 1, shortcuts: { "search.toggle": ["Ctrl+É"] } };
    expect(importShortcuts(JSON.stringify(file))).toEqual({ ok: true });
    const typed = press("é", { ctrlKey: true, code: "Digit2" });
    expect(matchesShortcut(typed, "search.toggle")).toBe(true);
    expect(matchesCombo(typed, "Ctrl+2")).toBe(true);
    // Option on macOS still falls back to the physical key.
    expect(
      matchesCombo(press("˙", { altKey: true, code: "KeyH" }), "Alt+H"),
    ).toBe(true);
  });

  it("matches Mod with Ctrl or Command and needs exact modifiers", () => {
    expect(matchesCombo(press("k", { ctrlKey: true }), "Mod+K")).toBe(true);
    expect(matchesCombo(press("k", { metaKey: true }), "Mod+K")).toBe(true);
    expect(matchesCombo(press("k"), "Mod+K")).toBe(false);
    expect(
      matchesCombo(press("h", { altKey: true, ctrlKey: true }), "Alt+H"),
    ).toBe(false);
    expect(matchesCombo(press("l", { metaKey: true }), "Ctrl+L")).toBe(false);
    expect(combosOverlap("Ctrl+K", "Meta+K")).toBe(false);
    expect(combosOverlap("Mod+K", "Meta+K")).toBe(true);
  });

  it("rejects broken text and formats labels", () => {
    for (const bad of ["", "Alt+", "Foo+K", "Alt+Alt+K", "Mod+Ctrl+K", "ab"]) {
      expect(parseCombo(bad)).toBeNull();
    }
    expect(comboLabels("Mod+K")).toEqual(["⌘ K", "Ctrl K"]);
    expect(comboLabels("Alt+ArrowRight")).toEqual(["Alt →"]);
  });
});

describe("validation and collision detection", () => {
  const types = (...args: Parameters<typeof findCollisions>) =>
    findCollisions(...args).map((collision) => collision.type);

  it("warns about browser shortcuts", () => {
    const [warning] = findCollisions(
      "lesson.toggleNotes",
      "Ctrl+W",
      DEFAULT_BINDINGS,
    );
    expect(warning.type).toBe("browser");
    expect(warning.message).toMatch(/close tab.*may never receive it/);
    expect(types("lesson.toggleNotes", "Meta+T", DEFAULT_BINDINGS)).toEqual([
      "browser",
    ]);
  });

  it("warns when another action uses the keys", () => {
    const [warning] = findCollisions(
      "lesson.toggleNotes",
      "Alt+H",
      DEFAULT_BINDINGS,
    );
    expect(warning.type).toBe("action");
    expect(warning.message).toContain("Toggle mentor support request panel");
    expect(types("lesson.toggleNotes", "Ctrl+K", DEFAULT_BINDINGS)).toContain(
      "action",
    );
  });

  it("only compares shortcuts that can be active together", () => {
    // Lesson page and terminal sandbox are different pages.
    expect(types("terminal.copy", "Alt+H", DEFAULT_BINDINGS)).toEqual([]);
    // Global shortcuts also run on the stash page.
    expect(types("nav.dashboard", "Alt+P", DEFAULT_BINDINGS)).toContain(
      "fixed",
    );
    expect(types("lesson.toggleNotes", "Alt+C", DEFAULT_BINDINGS)).toEqual([]);
  });

  it("refuses keys that would break typing or the keyboard", () => {
    expect(validateCombo("lesson.next", "J")).toBeNull();
    expect(validateCombo("lesson.next", "Escape")).not.toBeNull();
    expect(validateCombo("lesson.next", "Shift+Tab")).not.toBeNull();
    expect(validateCombo("lesson.next", "Enter")).not.toBeNull();
    expect(validateCombo("terminal.clear", "J")).toMatch(/while you type/);
    expect(validateCombo("terminal.clear", "Shift+J")).not.toBeNull();
    expect(validateCombo("terminal.clear", "F8")).toBeNull();
  });
});

describe("persistence", () => {
  it("saves only the changed shortcuts", () => {
    expect(setShortcut("lesson.next", ["alt+j"])).toBeNull();
    expect(JSON.parse(localStorage.getItem(SHORTCUTS_STORAGE_KEY)!)).toEqual({
      version: 1,
      shortcuts: { "lesson.next": ["Alt+J"] },
    });

    resetShortcut("lesson.next");
    expect(localStorage.getItem(SHORTCUTS_STORAGE_KEY)).toBeNull();
    expect(getShortcutBindings()).toEqual(DEFAULT_BINDINGS);
  });

  it("does not save an invalid combination", () => {
    expect(setShortcut("terminal.clear", ["J"])).toMatch(/while you type/);
    expect(localStorage.getItem(SHORTCUTS_STORAGE_KEY)).toBeNull();
  });

  it("loads what an earlier visit saved and skips bad entries", () => {
    localStorage.setItem(
      SHORTCUTS_STORAGE_KEY,
      JSON.stringify({
        version: 1,
        shortcuts: {
          "lesson.next": ["Alt+J"],
          "lesson.previous": ["nonsense+x"],
          removed: ["Alt+Q"],
        },
      }),
    );
    expect(getShortcutBindings()["lesson.next"]).toEqual(["Alt+J"]);
    expect(getShortcutBindings()["lesson.previous"]).toEqual(
      DEFAULT_BINDINGS["lesson.previous"],
    );
  });

  it("falls back to the defaults when the saved value is corrupt", () => {
    localStorage.setItem(SHORTCUTS_STORAGE_KEY, "{oops");
    expect(getShortcutBindings()).toEqual(DEFAULT_BINDINGS);
  });

  it("keeps working when storage cannot be written", () => {
    const spy = vi.spyOn(localStorage, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    expect(setShortcut("lesson.next", ["Alt+J"])).toBeNull();
    expect(matchesShortcut(press("j", { altKey: true }), "lesson.next")).toBe(
      true,
    );
    spy.mockRestore();
  });
});

describe("export and import", () => {
  it("round trips through JSON", () => {
    setShortcut("terminal.clear", ["Ctrl+K"]);
    const file = exportShortcuts();
    resetAllShortcuts();

    expect(importShortcuts(file)).toEqual({ ok: true });
    expect(getShortcutBindings()["terminal.clear"]).toEqual(["Ctrl+K"]);
  });

  it("restores defaults for shortcuts missing from the file", () => {
    setShortcut("lesson.next", ["Alt+J"]);
    importShortcuts('{"version":1,"shortcuts":{"lesson.previous":["Alt+K"]}}');
    expect(getShortcutBindings()["lesson.next"]).toEqual(
      DEFAULT_BINDINGS["lesson.next"],
    );
    expect(getShortcutBindings()["lesson.previous"]).toEqual(["Alt+K"]);
  });

  it.each([
    ["not json", "not valid JSON"],
    ["[]", "shortcuts"],
    ['{"version":2,"shortcuts":{}}', "version 1"],
    ['{"version":1,"shortcuts":{"nope":["Alt+J"]}}', 'Unknown shortcut "nope"'],
    ['{"version":1,"shortcuts":{"__proto__":["Alt+J"]}}', "Unknown shortcut"],
    ['{"version":1,"shortcuts":{"lesson.next":"Alt+J"}}', "list of 1 to 4"],
    ['{"version":1,"shortcuts":{"lesson.next":[]}}', "list of 1 to 4"],
    ['{"version":1,"shortcuts":{"lesson.next":[5]}}', "must be text"],
    ['{"version":1,"shortcuts":{"lesson.next":["Hyper+J"]}}', "not a valid"],
    ['{"version":1,"shortcuts":{"terminal.clear":["J"]}}', "while you type"],
    [" ".repeat(20_001), "too large"],
  ])("rejects %s", (file, message) => {
    const result = importShortcuts(file);
    expect(result.ok).toBe(false);
    expect(!result.ok && result.errors.join(" ")).toContain(message);
  });

  it("changes nothing when one entry in the file is bad", () => {
    setShortcut("lesson.next", ["Alt+J"]);
    importShortcuts(
      '{"version":1,"shortcuts":{"lesson.previous":["Alt+K"],"nope":[]}}',
    );
    expect(getShortcutBindings()["lesson.next"]).toEqual(["Alt+J"]);
    expect(getShortcutBindings()["lesson.previous"]).toEqual(
      DEFAULT_BINDINGS["lesson.previous"],
    );
  });
});

describe("useCustomShortcuts", () => {
  it("re-renders after a change and matches the new keys only", () => {
    const { result } = renderHook(() => useCustomShortcuts());
    const { matches } = result.current;

    act(() => {
      result.current.setShortcut("lesson.toggleHelp", ["Alt+J"]);
    });

    expect(result.current.labels("lesson.toggleHelp")).toEqual(["Alt J"]);
    expect(result.current.matches).toBe(matches);
    expect(matches(press("j", { altKey: true }), "lesson.toggleHelp")).toBe(
      true,
    );
    expect(matches(press("h", { altKey: true }), "lesson.toggleHelp")).toBe(
      false,
    );
  });

  it("picks up a change made in another tab", () => {
    const { result } = renderHook(() => useCustomShortcuts());
    act(() => {
      localStorage.setItem(
        SHORTCUTS_STORAGE_KEY,
        '{"version":1,"shortcuts":{"help.toggle":["F2"]}}',
      );
      window.dispatchEvent(
        new StorageEvent("storage", { key: SHORTCUTS_STORAGE_KEY }),
      );
    });
    expect(result.current.bindings["help.toggle"]).toEqual(["F2"]);
  });

  it("can suspend every shortcut", () => {
    const key = press("h", { altKey: true });
    const release = suspendShortcuts();
    expect(matchesShortcut(key, "lesson.toggleHelp")).toBe(false);
    release();
    release();
    expect(matchesShortcut(key, "lesson.toggleHelp")).toBe(true);
  });
});
