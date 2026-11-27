import { comboLabels, combosOverlap, parseCombo } from "./combo";
import {
  SHORTCUT_LIST,
  ShortcutBindings,
  ShortcutId,
  ShortcutScope,
  getShortcut,
} from "./registry";

export interface Collision {
  type: "browser" | "action" | "fixed";
  message: string;
}

interface BrowserShortcut {
  combo: string;
  use: string;
  /** The browser handles it first, so a page may never receive the key. */
  reserved?: boolean;
}

const reserved = (combo: string, use: string): BrowserShortcut => ({
  combo,
  use,
  reserved: true,
});
const browser = (combo: string, use: string): BrowserShortcut => ({
  combo,
  use,
});

export const BROWSER_SHORTCUTS: readonly BrowserShortcut[] = [
  reserved("Mod+W", "close tab"),
  reserved("Mod+T", "new tab"),
  reserved("Mod+N", "new window"),
  reserved("Mod+Shift+W", "close window"),
  reserved("Mod+Shift+T", "reopen closed tab"),
  reserved("Mod+Shift+N", "new private window"),
  reserved("Mod+Q", "quit browser"),
  browser("Mod+A", "select all"),
  browser("Mod+C", "copy"),
  browser("Mod+V", "paste"),
  browser("Mod+X", "cut"),
  browser("Mod+Z", "undo"),
  browser("Mod+Y", "redo"),
  browser("Mod+D", "bookmark page"),
  browser("Mod+F", "find in page"),
  browser("Mod+G", "find next"),
  browser("Mod+H", "history"),
  browser("Mod+J", "downloads"),
  browser("Mod+K", "search bar"),
  browser("Mod+L", "address bar"),
  browser("Mod+O", "open file"),
  browser("Mod+P", "print"),
  browser("Mod+R", "reload page"),
  browser("Mod+Shift+R", "hard reload"),
  browser("Mod+S", "save page"),
  browser("Mod+U", "view source"),
  browser("Mod+Shift+C", "inspect element"),
  browser("Mod+Shift+I", "developer tools"),
  browser("Mod+Shift+J", "developer console"),
  browser("Mod+0", "reset zoom"),
  browser("Mod+-", "zoom out"),
  browser("Mod+=", "zoom in"),
  browser("Mod+Plus", "zoom in"),
  ...Array.from({ length: 9 }, (_, i) => browser(`Mod+${i + 1}`, "switch tab")),
  browser("Alt+ArrowLeft", "back"),
  browser("Alt+ArrowRight", "forward"),
  browser("Alt+Home", "home page"),
  browser("Alt+D", "address bar"),
  browser("F1", "help"),
  browser("F3", "find"),
  browser("F5", "reload page"),
  browser("F6", "address bar"),
  browser("F11", "full screen"),
  browser("F12", "developer tools"),
];

/** Platform shortcuts that cannot be remapped but can still clash. */
export const FIXED_SHORTCUTS: readonly {
  combo: string;
  description: string;
  scope: ShortcutScope;
}[] = [
  { combo: "Alt+S", description: "Stash all changes", scope: "stash" },
  { combo: "Alt+P", description: "Pop the top stash", scope: "stash" },
  { combo: "Alt+D", description: "Drop the top stash", scope: "stash" },
  { combo: "Mod+Z", description: "Undo rebase step", scope: "rebase" },
  { combo: "Mod+Shift+Z", description: "Redo rebase step", scope: "rebase" },
  { combo: "Mod+Y", description: "Redo rebase step", scope: "rebase" },
  { combo: "Ctrl+X", description: "Save and exit nano", scope: "editor" },
  { combo: "Ctrl+C", description: "Cancel nano editing", scope: "editor" },
];

function scopesOverlap(a: ShortcutScope, b: ShortcutScope): boolean {
  return a === b || a === "global" || b === "global";
}

/** Why a combination cannot be used for a shortcut, or null when it can. */
export function validateCombo(id: ShortcutId, text: string): string | null {
  const combo = parseCombo(text);
  if (!combo) return `"${text}" is not a valid key combination.`;

  if (combo.key === "Escape" || combo.key === "Tab") {
    return "Escape and Tab are kept for closing dialogs and moving focus.";
  }
  const hasModifier = combo.mod || combo.ctrl || combo.meta || combo.alt;
  if (!hasModifier && (combo.key === "Enter" || combo.key === "Space")) {
    return "Enter and Space on their own are needed to press buttons.";
  }
  if (
    getShortcut(id).requiresModifier &&
    !hasModifier &&
    !/^F\d+$/.test(combo.key)
  ) {
    return "This shortcut also works while you type, so it needs Ctrl, ⌘, Alt or a function key.";
  }
  return null;
}

export function findCollisions(
  id: ShortcutId,
  combo: string,
  bindings: ShortcutBindings,
): Collision[] {
  const { scope } = getShortcut(id);
  const name = comboLabels(combo).join(" / ");
  const collisions: Collision[] = [];

  const used = BROWSER_SHORTCUTS.find((entry) =>
    combosOverlap(entry.combo, combo),
  );
  if (used) {
    collisions.push({
      type: "browser",
      message: used.reserved
        ? `${name} is a browser shortcut (${used.use}). The browser keeps it, so this page may never receive it.`
        : `${name} is also a browser shortcut (${used.use}).`,
    });
  }

  for (const other of SHORTCUT_LIST) {
    if (other.id === id || !scopesOverlap(scope, other.scope)) continue;
    if (bindings[other.id].some((taken) => combosOverlap(taken, combo))) {
      collisions.push({
        type: "action",
        message: `${name} is already used by "${other.description}" (${other.category}). The two would clash.`,
      });
    }
  }

  for (const fixed of FIXED_SHORTCUTS) {
    if (
      scopesOverlap(scope, fixed.scope) &&
      combosOverlap(fixed.combo, combo)
    ) {
      collisions.push({
        type: "fixed",
        message: `${name} is already used by "${fixed.description}", which cannot be remapped.`,
      });
    }
  }

  return collisions;
}
