import React, { useEffect, useId, useRef, useState } from "react";
import { HelpCircle, X, Copy, Check } from "lucide-react";
import {
  loadGitCheatSheetMap,
  resolveContextualCommands,
  type ContextualGitCommand,
} from "../../lib/contextualGitCheatSheet";

export type ContextualGitCheatSheetProps = {
  lessonSlug?: string;
  moduleId?: string;
  /** Insert command into terminal input */
  onInsertCommand?: (command: string) => void;
  /** Compact floating "?" only (default true) */
  className?: string;
};

export function ContextualGitCheatSheet({
  lessonSlug,
  moduleId,
  onInsertCommand,
  className = "",
}: ContextualGitCheatSheetProps) {
  const [open, setOpen] = useState(false);
  const [commands, setCommands] = useState<ContextualGitCommand[]>([]);
  const [sourceLabel, setSourceLabel] = useState("");
  const [loadError, setLoadError] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();

  useEffect(() => {
    let cancelled = false;
    loadGitCheatSheetMap()
      .then((map) => {
        if (cancelled) return;
        const resolved = resolveContextualCommands(lessonSlug, moduleId, map);
        setCommands(resolved.commands);
        const label =
          resolved.source === "lesson" && lessonSlug
            ? `For lesson: ${lessonSlug}`
            : resolved.source === "module" && resolved.resolvedModuleId
              ? `For module: ${resolved.resolvedModuleId}`
              : "Starter Git commands";
        setSourceLabel(label);
        setLoadError("");
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError("Could not load contextual commands.");
          setCommands([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [lessonSlug, moduleId]);

  useEffect(() => {
    if (!open) return;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        triggerRef.current?.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    // Focus close button when opened
    queueMicrotask(() => closeRef.current?.focus());

    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  const handleCopy = async (command: string) => {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(command);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      // ignore
    }
  };

  return (
    <div className={`relative inline-flex ${className}`}>
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? titleId : undefined}
        title="Contextual Git cheat sheet"
        onClick={() => setOpen(true)}
        className="inline-flex items-center justify-center w-9 h-9 rounded-full border-4 border-black bg-accent text-black font-black shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 transition-all dark:border-[#2e2924] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        <HelpCircle size={18} aria-hidden />
        <span className="sr-only">Open contextual Git cheat sheet</span>
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4">
          <button
            type="button"
            aria-label="Close cheat sheet backdrop"
            className="absolute inset-0 bg-black/50"
            onClick={() => {
              setOpen(false);
              triggerRef.current?.focus();
            }}
          />

          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className="relative w-full max-w-lg max-h-[80vh] overflow-hidden rounded-2xl border-4 border-black bg-white shadow-card flex flex-col dark:bg-[#1f1c18] dark:border-[#2e2924]"
          >
            <div className="flex items-start justify-between gap-3 p-4 border-b-4 border-black dark:border-[#2e2924]">
              <div>
                <h2
                  id={titleId}
                  className="text-lg font-black text-text dark:text-[#f0ebe2]"
                >
                  Git cheat sheet
                </h2>
                <p className="text-xs font-bold text-muted mt-1 dark:text-[#c4bbae]">
                  {sourceLabel || "Loading…"} · Press Esc to close
                </p>
              </div>
              <button
                ref={closeRef}
                type="button"
                onClick={() => {
                  setOpen(false);
                  triggerRef.current?.focus();
                }}
                className="p-2 rounded-lg border-2 border-black hover:bg-surface-low dark:border-[#2e2924] dark:text-[#f0ebe2] dark:hover:bg-[#151411]"
                aria-label="Close cheat sheet"
              >
                <X size={18} />
              </button>
            </div>

            <div className="overflow-y-auto p-4 space-y-3">
              {loadError && (
                <p className="text-sm font-bold text-red-600" role="alert">
                  {loadError}
                </p>
              )}

              {!loadError && commands.length === 0 && (
                <p className="text-sm font-bold text-muted dark:text-[#c4bbae]">
                  Loading commands…
                </p>
              )}

              {commands.map((cmd) => (
                <article
                  key={cmd.id}
                  className="rounded-xl border-2 border-black/15 dark:border-[#2e2924] bg-surface-low dark:bg-[#151411] p-3 space-y-1"
                >
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-sm font-black text-text dark:text-[#f0ebe2]">
                      {cmd.name}
                    </h3>
                    <div className="flex gap-1 shrink-0">
                      <button
                        type="button"
                        onClick={() => handleCopy(cmd.command)}
                        className="px-2 py-1 text-[10px] font-black rounded-md border-2 border-black bg-white dark:bg-[#1f1c18] dark:text-[#f0ebe2] dark:border-[#2e2924] inline-flex items-center gap-1"
                      >
                        {copied === cmd.command ? (
                          <>
                            <Check size={12} /> Copied
                          </>
                        ) : (
                          <>
                            <Copy size={12} /> Copy
                          </>
                        )}
                      </button>
                      {onInsertCommand && (
                        <button
                          type="button"
                          onClick={() => {
                            onInsertCommand(cmd.command);
                            setOpen(false);
                            triggerRef.current?.focus();
                          }}
                          className="px-2 py-1 text-[10px] font-black rounded-md border-2 border-black bg-accent text-black"
                        >
                          Use
                        </button>
                      )}
                    </div>
                  </div>
                  <code className="block font-mono text-xs text-accent break-all">
                    {cmd.command}
                  </code>
                  <p className="text-xs font-bold text-muted dark:text-[#c4bbae]">
                    {cmd.description}
                  </p>
                  {cmd.example && (
                    <pre className="text-[11px] font-mono whitespace-pre-wrap text-text/80 dark:text-[#c4bbae] bg-black/5 dark:bg-black/30 rounded-lg p-2 mt-1">
                      {cmd.example}
                    </pre>
                  )}
                </article>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ContextualGitCheatSheet;
