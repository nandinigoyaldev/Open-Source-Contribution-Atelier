import { useCallback, useSyncExternalStore } from "react";
import { comboLabels } from "./combo";
import { DEFAULT_BINDINGS, ShortcutId } from "./registry";
import {
  exportShortcuts,
  getShortcutBindings,
  importShortcuts,
  matchesShortcut,
  resetAllShortcuts,
  resetShortcut,
  setShortcut,
  subscribeShortcuts,
} from "./store";

const getServerBindings = () => DEFAULT_BINDINGS;

/**
 * The user's keyboard shortcuts. `matches` reads the saved bindings when the
 * key is pressed and never changes identity, so it is safe in effect deps.
 */
export function useCustomShortcuts() {
  const bindings = useSyncExternalStore(
    subscribeShortcuts,
    getShortcutBindings,
    getServerBindings,
  );

  /** Display labels of every combination bound to a shortcut. */
  const labels = useCallback(
    (id: ShortcutId) => [...new Set(bindings[id].flatMap(comboLabels))],
    [bindings],
  );

  return {
    bindings,
    labels,
    matches: matchesShortcut,
    setShortcut,
    resetShortcut,
    resetAll: resetAllShortcuts,
    exportJson: exportShortcuts,
    importJson: importShortcuts,
  };
}
