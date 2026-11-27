// A key combination is stored as text such as "Alt+N" or "Mod+Enter".
// "Mod" means Ctrl or the macOS Command key.

export interface KeyEventLike {
  key: string;
  code?: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
  shiftKey?: boolean;
  getModifierState?(key: string): boolean;
}

export interface KeyCombo {
  mod: boolean;
  ctrl: boolean;
  meta: boolean;
  alt: boolean;
  shift: boolean;
  key: string;
}

const MODIFIERS = ["mod", "ctrl", "meta", "alt", "shift"] as const;

const NAMED_KEYS = [
  "ArrowUp",
  "ArrowDown",
  "ArrowLeft",
  "ArrowRight",
  "Enter",
  "Escape",
  "Tab",
  "Space",
  "Backspace",
  "Delete",
  "Home",
  "End",
  "PageUp",
  "PageDown",
  "Insert",
  "Plus",
  ...Array.from({ length: 12 }, (_, i) => `F${i + 1}`),
];

const KEY_LABELS: Record<string, string> = {
  ArrowUp: "↑",
  ArrowDown: "↓",
  ArrowLeft: "←",
  ArrowRight: "→",
  Escape: "Esc",
  Plus: "+",
};

function isSingleChar(key: string): boolean {
  return Array.from(key).length === 1;
}

function normalizeKey(key: string): string | null {
  if (key === " ") return "Space";
  if (key === "+") return "Plus";
  if (isSingleChar(key)) {
    if (!key.trim()) return null;
    const upper = key.toUpperCase();
    return upper.length === 1 ? upper : key;
  }
  const lower = key.toLowerCase();
  return NAMED_KEYS.find((name) => name.toLowerCase() === lower) ?? null;
}

/**
 * Symbols and digits already depend on Shift on many layouts ("?" on US,
 * digits on AZERTY), so Shift is not part of the combination for them.
 */
function ignoresShift(key: string): boolean {
  return (
    key === "Plus" ||
    (isSingleChar(key) && key.toLowerCase() === key.toUpperCase())
  );
}

export function parseCombo(text: string): KeyCombo | null {
  const parts = text.split("+").map((part) => part.trim());
  const key = normalizeKey(parts.pop() ?? "");
  if (!key) return null;

  const combo: KeyCombo = {
    mod: false,
    ctrl: false,
    meta: false,
    alt: false,
    shift: false,
    key,
  };
  for (const part of parts) {
    const name = MODIFIERS.find((m) => m === part.toLowerCase());
    if (!name || combo[name]) return null;
    combo[name] = true;
  }
  if (combo.mod && (combo.ctrl || combo.meta)) return null;
  if (ignoresShift(key)) combo.shift = false;
  return combo;
}

export function formatCombo(combo: KeyCombo): string {
  const parts: string[] = [];
  if (combo.mod) parts.push("Mod");
  if (combo.ctrl) parts.push("Ctrl");
  if (combo.meta) parts.push("Meta");
  if (combo.alt) parts.push("Alt");
  if (combo.shift) parts.push("Shift");
  parts.push(combo.key);
  return parts.join("+");
}

/** Returns null for a modifier pressed on its own, AltGr and unknown keys. */
export function comboFromEvent(event: KeyEventLike): string | null {
  // AltGr is used to type characters on many international layouts.
  if (event.getModifierState?.("AltGraph")) return null;
  if (!event.key) return null;

  const ctrl = Boolean(event.ctrlKey);
  const meta = Boolean(event.metaKey);
  const alt = Boolean(event.altKey);

  let rawKey = event.key;
  // Option on macOS and non-Latin layouts turn Alt+H into another character.
  // Use the physical key in that case.
  const isForeign =
    rawKey === "Dead" || (isSingleChar(rawKey) && rawKey.charCodeAt(0) > 127);
  if ((ctrl || meta || alt) && isForeign) {
    const physical = /^(?:Key([A-Z])|Digit(\d))$/.exec(event.code ?? "");
    if (physical) rawKey = physical[1] ?? physical[2];
  }

  const key = normalizeKey(rawKey);
  if (!key) return null;
  return formatCombo({
    mod: false,
    ctrl,
    meta,
    alt,
    shift: Boolean(event.shiftKey) && !ignoresShift(key),
    key,
  });
}

/** The [ctrl, meta] states that satisfy a combination. */
function ctrlMetaStates(combo: KeyCombo): string[] {
  if (combo.mod) return ["true,false", "false,true", "true,true"];
  return [`${combo.ctrl},${combo.meta}`];
}

/** True when a single key press could trigger both combinations. */
export function combosOverlap(a: string, b: string): boolean {
  const first = parseCombo(a);
  const second = parseCombo(b);
  if (!first || !second) return false;
  if (
    first.key !== second.key ||
    first.alt !== second.alt ||
    first.shift !== second.shift
  ) {
    return false;
  }
  const states = ctrlMetaStates(second);
  return ctrlMetaStates(first).some((state) => states.includes(state));
}

export function matchesCombo(event: KeyEventLike, combo: string): boolean {
  const pressed = comboFromEvent(event);
  return pressed !== null && combosOverlap(pressed, combo);
}

/** Display labels. A "Mod" combination gets one label per platform. */
export function comboLabels(text: string): string[] {
  const combo = parseCombo(text);
  if (!combo) return [text];
  const label = (modifiers: string[]) =>
    [
      ...modifiers,
      ...(combo.alt ? ["Alt"] : []),
      ...(combo.shift ? ["Shift"] : []),
      KEY_LABELS[combo.key] ?? combo.key,
    ].join(" ");

  if (combo.mod) return [label(["⌘"]), label(["Ctrl"])];
  return [
    label([...(combo.ctrl ? ["Ctrl"] : []), ...(combo.meta ? ["⌘"] : [])]),
  ];
}
