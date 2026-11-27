// Every remappable platform shortcut. The key handlers, the cheat sheet and
// the settings editor all read from this list.

/**
 * Where a shortcut is active. Two shortcuts can only clash when they share a
 * scope or one of them is global.
 */
export type ShortcutScope =
  | "global"
  | "lesson"
  | "terminal"
  | "editor"
  | "stash"
  | "rebase";

interface DefinitionShape {
  id: string;
  category: string;
  description: string;
  scope: ShortcutScope;
  defaults: readonly string[];
  /** Set for shortcuts that also fire while the user is typing. */
  requiresModifier?: boolean;
}

export const SHORTCUTS = [
  {
    id: "search.toggle",
    category: "Global",
    description: "Toggle Command Palette",
    scope: "global",
    defaults: ["Mod+K"],
    requiresModifier: true,
  },
  {
    id: "help.toggle",
    category: "Global",
    description: "Toggle this Keyboard Shortcuts Cheat Sheet modal",
    scope: "global",
    defaults: ["?"],
  },
  {
    id: "nav.dashboard",
    category: "Global",
    description: "Go to the dashboard",
    scope: "global",
    defaults: ["/"],
  },
  {
    id: "lesson.next",
    category: "Lesson Navigation",
    description: "Navigate to next lesson in current pathway",
    scope: "lesson",
    defaults: ["Alt+ArrowRight", "Alt+N"],
  },
  {
    id: "lesson.previous",
    category: "Lesson Navigation",
    description: "Navigate to previous lesson in current pathway",
    scope: "lesson",
    defaults: ["Alt+ArrowLeft", "Alt+P"],
  },
  {
    id: "lesson.toggleSidebar",
    category: "Lesson Navigation",
    description: "Toggle lesson module outline sidebar",
    scope: "lesson",
    defaults: ["Alt+S", "Alt+M"],
  },
  {
    id: "lesson.toggleBookmark",
    category: "Lesson Navigation",
    description: "Toggle lesson bookmark",
    scope: "lesson",
    defaults: ["Alt+B"],
  },
  {
    id: "lesson.toggleNotes",
    category: "Lesson Navigation",
    description: "Toggle user notes panel",
    scope: "lesson",
    defaults: ["Alt+C"],
  },
  {
    id: "lesson.toggleHelp",
    category: "Lesson Navigation",
    description: "Toggle mentor support request panel",
    scope: "lesson",
    defaults: ["Alt+H"],
  },
  {
    id: "lesson.runCommand",
    category: "Git Sandbox",
    description: "Submit command in lesson check prompt",
    scope: "lesson",
    defaults: ["Mod+Enter"],
    requiresModifier: true,
  },
  {
    id: "terminal.clear",
    category: "Terminal",
    description: "Clear the sandbox terminal",
    scope: "terminal",
    defaults: ["Ctrl+L", "Ctrl+R"],
    requiresModifier: true,
  },
  {
    id: "terminal.copy",
    category: "Terminal",
    description: "Copy the terminal text",
    scope: "terminal",
    defaults: ["Ctrl+Shift+C"],
    requiresModifier: true,
  },
  {
    id: "terminal.focusInput",
    category: "Terminal",
    description: "Focus the terminal input",
    scope: "terminal",
    defaults: ["Ctrl+/"],
    requiresModifier: true,
  },
] as const satisfies readonly DefinitionShape[];

export type ShortcutId = (typeof SHORTCUTS)[number]["id"];

export type ShortcutDefinition = Omit<DefinitionShape, "id"> & {
  id: ShortcutId;
};

export type ShortcutBindings = Record<ShortcutId, readonly string[]>;

export const SHORTCUT_LIST: readonly ShortcutDefinition[] = SHORTCUTS;

export const DEFAULT_BINDINGS = Object.fromEntries(
  SHORTCUT_LIST.map((shortcut) => [shortcut.id, shortcut.defaults]),
) as ShortcutBindings;

export function getShortcut(id: ShortcutId): ShortcutDefinition {
  return SHORTCUT_LIST.find((shortcut) => shortcut.id === id)!;
}
