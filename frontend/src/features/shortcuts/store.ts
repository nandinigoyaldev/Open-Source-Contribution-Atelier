import { KeyEventLike, matchesCombo, parseCombo, formatCombo } from "./combo";
import { validateCombo } from "./collisions";
import {
  DEFAULT_BINDINGS,
  SHORTCUT_LIST,
  ShortcutBindings,
  ShortcutId,
} from "./registry";

export const SHORTCUTS_STORAGE_KEY = "atelier:keyboard-shortcuts";
const FORMAT_VERSION = 1;
const MAX_COMBOS = 4;
export const MAX_IMPORT_BYTES = 20_000;

export type ImportResult = { ok: true } | { ok: false; errors: string[] };

const listeners = new Set<() => void>();
// Holds the value in memory when the browser refuses to write to storage.
let unsaved: string | null | undefined;
let cachedRaw: string | null = null;
let cachedBindings: ShortcutBindings = DEFAULT_BINDINGS;
let suspendCount = 0;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Checks one list of combinations and returns it in canonical form. */
function readCombos(
  id: ShortcutId,
  value: unknown,
): { combos: string[] } | { error: string } {
  if (
    !Array.isArray(value) ||
    value.length === 0 ||
    value.length > MAX_COMBOS
  ) {
    return {
      error: `expected a list of 1 to ${MAX_COMBOS} key combinations.`,
    };
  }
  const combos: string[] = [];
  for (const item of value) {
    if (typeof item !== "string") {
      return { error: "every key combination must be text." };
    }
    const error = validateCombo(id, item);
    if (error) return { error };
    const canonical = formatCombo(parseCombo(item)!);
    if (!combos.includes(canonical)) combos.push(canonical);
  }
  return { combos };
}

/** Reads saved data and skips anything that is no longer valid. */
function parseStored(raw: string | null): ShortcutBindings {
  if (!raw) return DEFAULT_BINDINGS;
  try {
    const data: unknown = JSON.parse(raw);
    if (
      !isRecord(data) ||
      data.version !== FORMAT_VERSION ||
      !isRecord(data.shortcuts)
    ) {
      return DEFAULT_BINDINGS;
    }
    const bindings = { ...DEFAULT_BINDINGS };
    for (const { id } of SHORTCUT_LIST) {
      const result = readCombos(id, data.shortcuts[id]);
      if ("combos" in result) bindings[id] = result.combos;
    }
    return bindings;
  } catch {
    return DEFAULT_BINDINGS;
  }
}

function readRaw(): string | null {
  if (unsaved !== undefined) return unsaved;
  try {
    return window.localStorage.getItem(SHORTCUTS_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function getShortcutBindings(): ShortcutBindings {
  const raw = readRaw();
  if (raw !== cachedRaw) {
    cachedRaw = raw;
    cachedBindings = parseStored(raw);
  }
  return cachedBindings;
}

export function isDefaultBinding(
  id: ShortcutId,
  combos: readonly string[],
): boolean {
  return combos.join("\n") === DEFAULT_BINDINGS[id].join("\n");
}

/** Only changed shortcuts are saved, so new defaults still reach everyone. */
function save(bindings: ShortcutBindings) {
  const changed = SHORTCUT_LIST.filter(
    ({ id }) => !isDefaultBinding(id, bindings[id]),
  ).map(({ id }) => [id, bindings[id]]);
  const raw = changed.length
    ? JSON.stringify({
        version: FORMAT_VERSION,
        shortcuts: Object.fromEntries(changed),
      })
    : null;

  try {
    if (raw) window.localStorage.setItem(SHORTCUTS_STORAGE_KEY, raw);
    else window.localStorage.removeItem(SHORTCUTS_STORAGE_KEY);
    unsaved = undefined;
  } catch {
    unsaved = raw;
  }
  listeners.forEach((listener) => listener());
}

export function subscribeShortcuts(listener: () => void): () => void {
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || event.key === SHORTCUTS_STORAGE_KEY) listener();
  };
  listeners.add(listener);
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

/** Replaces the combinations of one shortcut. Returns an error or null. */
export function setShortcut(
  id: ShortcutId,
  combos: readonly string[],
): string | null {
  const result = readCombos(id, combos);
  if ("error" in result) return result.error;
  save({ ...getShortcutBindings(), [id]: result.combos });
  return null;
}

export function resetShortcut(id: ShortcutId) {
  save({ ...getShortcutBindings(), [id]: DEFAULT_BINDINGS[id] });
}

export function resetAllShortcuts() {
  save(DEFAULT_BINDINGS);
}

export function exportShortcuts(): string {
  return JSON.stringify(
    { version: FORMAT_VERSION, shortcuts: getShortcutBindings() },
    null,
    2,
  );
}

/**
 * Applies an exported file. Nothing changes unless the whole file is valid.
 * Shortcuts missing from the file go back to their defaults.
 */
export function importShortcuts(json: string): ImportResult {
  const fail = (...errors: string[]): ImportResult => ({ ok: false, errors });

  if (json.length > MAX_IMPORT_BYTES) return fail("The file is too large.");
  let data: unknown;
  try {
    data = JSON.parse(json);
  } catch {
    return fail("The file is not valid JSON.");
  }
  if (!isRecord(data) || !isRecord(data.shortcuts)) {
    return fail('The file needs a "shortcuts" object.');
  }
  if (data.version !== FORMAT_VERSION) {
    return fail(`Only version ${FORMAT_VERSION} files can be imported.`);
  }

  const bindings = { ...DEFAULT_BINDINGS };
  const errors: string[] = [];
  for (const [key, value] of Object.entries(data.shortcuts)) {
    const shortcut = SHORTCUT_LIST.find(({ id }) => id === key);
    if (!shortcut) {
      errors.push(`Unknown shortcut "${key}".`);
      continue;
    }
    const result = readCombos(shortcut.id, value);
    if ("error" in result) errors.push(`${key}: ${result.error}`);
    else bindings[shortcut.id] = result.combos;
  }
  if (errors.length) return fail(...errors);

  save(bindings);
  return { ok: true };
}

/** Stops every shortcut from firing until the returned function is called. */
export function suspendShortcuts(): () => void {
  suspendCount += 1;
  let released = false;
  return () => {
    if (released) return;
    released = true;
    suspendCount -= 1;
  };
}

export function matchesShortcut(event: KeyEventLike, id: ShortcutId): boolean {
  if (suspendCount > 0) return false;
  return getShortcutBindings()[id].some((combo) => matchesCombo(event, combo));
}
