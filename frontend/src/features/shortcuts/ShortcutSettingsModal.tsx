import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { useFocusTrap } from "../../hooks/useFocusTrap";
import { comboFromEvent } from "./combo";
import { Collision, findCollisions, validateCombo } from "./collisions";
import { SHORTCUT_LIST, ShortcutDefinition, ShortcutId } from "./registry";
import { MAX_IMPORT_BYTES, isDefaultBinding, suspendShortcuts } from "./store";
import { useCustomShortcuts } from "./useCustomShortcuts";

const EXPORT_FILE_NAME = "atelier-shortcuts.json";

const BUTTON_CLASS =
  "px-2.5 py-1 text-xs font-black rounded-md border-2 border-[#2e2924] bg-black text-[#f0ebe2] hover:border-[#FFCC00] disabled:opacity-40 disabled:cursor-not-allowed";

const CATEGORIES = [...new Set(SHORTCUT_LIST.map((s) => s.category))];

interface Pending {
  id: ShortcutId;
  combo: string;
  collisions: Collision[];
}

interface ShortcutSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

function readFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

function ShortcutEditor({ onClose }: { onClose: () => void }) {
  const {
    bindings,
    labels,
    setShortcut,
    resetShortcut,
    resetAll,
    exportJson,
    importJson,
  } = useCustomShortcuts();

  const [recordingId, setRecordingId] = useState<ShortcutId | null>(null);
  const [recordError, setRecordError] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);
  const [status, setStatus] = useState("");
  const [importErrors, setImportErrors] = useState<string[]>([]);

  const modalRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const changeRefs = useRef(new Map<ShortcutId, HTMLButtonElement>());
  useFocusTrap(modalRef, true);

  // Shortcuts must not fire behind the editor while keys are being pressed.
  useEffect(() => suspendShortcuts(), []);

  // Bumped by every edit, reset and close, so a file read that is still
  // running when one of those happens does not import afterwards.
  const operationRef = useRef(0);
  useEffect(
    () => () => {
      operationRef.current += 1;
    },
    [],
  );

  const clearMessages = () => {
    operationRef.current += 1;
    setRecordingId(null);
    setRecordError("");
    setPending(null);
    setStatus("");
    setImportErrors([]);
  };

  const apply = (id: ShortcutId, combo: string) => {
    clearMessages();
    const error = setShortcut(id, [combo]);
    setStatus(error ?? "Shortcut saved.");
    changeRefs.current.get(id)?.focus();
  };

  // Capture phase, so a recorded key never reaches any other handler.
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!recordingId) {
        if (event.key === "Escape") {
          event.preventDefault();
          event.stopImmediatePropagation();
          onClose();
        }
        return;
      }
      // A plain Tab leaves recording so keyboard users are never stuck.
      if (event.key === "Tab" && !event.ctrlKey && !event.altKey) {
        setRecordingId(null);
        setRecordError("");
        return;
      }
      event.preventDefault();
      event.stopImmediatePropagation();
      if (event.key === "Escape") {
        setRecordingId(null);
        setRecordError("");
        return;
      }
      if (event.repeat) return;
      const combo = comboFromEvent(event);
      if (!combo) return;

      const error = validateCombo(recordingId, combo);
      if (error) {
        setRecordError(error);
        return;
      }
      const collisions = findCollisions(recordingId, combo, bindings);
      if (collisions.length) {
        setPending({ id: recordingId, combo, collisions });
        setRecordingId(null);
        setRecordError("");
        return;
      }
      apply(recordingId, combo);
    };

    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  });

  const handleExport = () => {
    clearMessages();
    const url = URL.createObjectURL(
      new Blob([exportJson()], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = EXPORT_FILE_NAME;
    link.click();
    URL.revokeObjectURL(url);
    setStatus(`Shortcuts exported to ${EXPORT_FILE_NAME}.`);
  };

  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const input = event.target;
    const file = input.files?.[0];
    if (!file) return;
    // Lets the same file be picked again after it has been fixed.
    input.value = "";
    clearMessages();
    const operation = operationRef.current;

    if (file.size > MAX_IMPORT_BYTES) {
      setImportErrors(["The file is too large."]);
      return;
    }
    let text: string;
    try {
      text = await readFile(file);
    } catch {
      if (operation === operationRef.current) {
        setImportErrors(["The file could not be read."]);
      }
      return;
    }
    if (operation !== operationRef.current) return;
    const result = importJson(text);
    if (result.ok) setStatus("Shortcuts imported.");
    else setImportErrors(result.errors);
  };

  const renderRow = (shortcut: ShortcutDefinition) => {
    const { id, description } = shortcut;
    const combos = bindings[id];
    const isRecording = recordingId === id;
    const rowPending = pending?.id === id ? pending : null;
    const warnings = [
      ...new Set(
        combos.flatMap((combo) =>
          findCollisions(id, combo, bindings).map((c) => c.message),
        ),
      ),
    ];

    return (
      <li
        key={id}
        data-testid={`shortcut-row-${id}`}
        className="px-4 py-3 border-b-2 border-black/60 last:border-b-0 space-y-2"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm font-bold text-[#f0ebe2]">
            {description}
          </span>
          <div className="flex flex-wrap items-center gap-2">
            {labels(id).map((label) => (
              <kbd
                key={label}
                className="px-2 py-1 bg-black text-[#FFCC00] font-mono text-xs rounded border-2 border-[#2e2924]"
              >
                {label}
              </kbd>
            ))}
            <button
              type="button"
              ref={(node) => {
                if (node) changeRefs.current.set(id, node);
              }}
              className={BUTTON_CLASS}
              aria-label={`Change shortcut: ${description}`}
              onClick={() => {
                clearMessages();
                setRecordingId(id);
              }}
            >
              Change
            </button>
            <button
              type="button"
              className={BUTTON_CLASS}
              aria-label={`Reset shortcut: ${description}`}
              disabled={isDefaultBinding(id, combos)}
              onClick={() => {
                clearMessages();
                resetShortcut(id);
                setStatus("Shortcut reset to its default.");
                changeRefs.current.get(id)?.focus();
              }}
            >
              Reset
            </button>
          </div>
        </div>

        {isRecording && (
          <div className="text-xs font-bold text-[#FFCC00]">
            <p role="status">
              Press the new key combination, or Esc to cancel.
            </p>
            {recordError && (
              <p role="alert" className="text-red-400 mt-1">
                {recordError}
              </p>
            )}
          </div>
        )}

        {rowPending && (
          <div
            role="alert"
            className="rounded-lg border-2 border-amber-500 bg-amber-500/10 p-3 text-xs font-bold text-amber-300 space-y-2"
          >
            <ul className="space-y-1">
              {rowPending.collisions.map((collision) => (
                <li key={collision.message}>{collision.message}</li>
              ))}
            </ul>
            <div className="flex gap-2">
              <button
                type="button"
                className={BUTTON_CLASS}
                onClick={() => apply(id, rowPending.combo)}
              >
                Save anyway
              </button>
              <button
                type="button"
                className={BUTTON_CLASS}
                onClick={() => {
                  setPending(null);
                  changeRefs.current.get(id)?.focus();
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {!rowPending && warnings.length > 0 && (
          <ul className="text-xs text-amber-400 space-y-1">
            {warnings.map((message) => (
              <li key={message}>⚠ {message}</li>
            ))}
          </ul>
        )}
      </li>
    );
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div
        className="fixed inset-0 bg-black/80 backdrop-blur-sm"
        onClick={onClose}
        data-testid="shortcut-settings-backdrop"
      />
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcut-settings-title"
        aria-describedby="shortcut-settings-desc"
        className="relative z-10 w-full max-w-2xl max-h-[85vh] flex flex-col bg-[#0f0e0c] border border-slate-700 rounded-2xl shadow-2xl overflow-hidden"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b-4 border-black bg-[#151411]">
          <h2
            id="shortcut-settings-title"
            className="font-black text-xl tracking-tight text-white uppercase"
          >
            Customize shortcuts
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-md text-[#c4bbae] hover:bg-[#2e2924]"
            aria-label="Close shortcut settings"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          <p
            id="shortcut-settings-desc"
            className="text-sm font-bold text-[#c4bbae]"
          >
            Choose Change and press the new keys. This replaces every key set
            for that action and is saved in this browser. Some combinations,
            such as Ctrl W, are kept by the browser and cannot be recorded.
          </p>
          {CATEGORIES.map((category) => (
            <section key={category} aria-label={category}>
              <h3 className="mb-2 text-xs font-mono uppercase tracking-wider text-[#FFCC00]">
                {category}
              </h3>
              <ul className="border-4 border-black bg-[#151411] rounded-xl">
                {SHORTCUT_LIST.filter((s) => s.category === category).map(
                  renderRow,
                )}
              </ul>
            </section>
          ))}
        </div>

        <div className="px-6 py-3 border-t-4 border-black bg-[#151411] space-y-2">
          <p role="status" className="text-xs font-bold text-green-400">
            {status}
          </p>
          {importErrors.length > 0 && (
            <div role="alert" className="text-xs font-bold text-red-400">
              <p>Import failed. Your shortcuts were not changed.</p>
              <ul className="max-h-20 overflow-y-auto">
                {importErrors.map((message) => (
                  <li key={message}>{message}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="flex flex-wrap justify-between gap-2">
            <button
              type="button"
              className={BUTTON_CLASS}
              onClick={() => {
                clearMessages();
                resetAll();
                setStatus("All shortcuts reset to their defaults.");
              }}
            >
              Reset to Defaults
            </button>
            <div className="flex gap-2">
              <button
                type="button"
                className={BUTTON_CLASS}
                onClick={handleExport}
              >
                Export JSON
              </button>
              <button
                type="button"
                className={BUTTON_CLASS}
                onClick={() => fileRef.current?.click()}
              >
                Import JSON
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="application/json,.json"
                className="hidden"
                aria-label="Shortcuts JSON file"
                onChange={handleImport}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function ShortcutSettingsModal({
  isOpen,
  onClose,
}: ShortcutSettingsModalProps) {
  if (!isOpen) return null;
  return createPortal(<ShortcutEditor onClose={onClose} />, document.body);
}
