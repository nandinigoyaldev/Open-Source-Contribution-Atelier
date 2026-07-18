import React, { useEffect, useRef } from "react";
import { X, BookOpen } from "lucide-react";
import type { GlossaryEntry } from "../../lib/glossary";

export type GlossaryDrawerProps = {
  entry: GlossaryEntry | null;
  onClose: () => void;
};

export function GlossaryDrawer({ entry, onClose }: GlossaryDrawerProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!entry) return;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    queueMicrotask(() => closeRef.current?.focus());
    return () => document.removeEventListener("keydown", onKey);
  }, [entry, onClose]);

  if (!entry) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="presentation">
      <button
        type="button"
        className="flex-1 cursor-default bg-black/40"
        aria-label="Close glossary drawer"
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="glossary-drawer-title"
        className="h-full w-full max-w-md overflow-y-auto border-l-4 border-black bg-white p-6 shadow-card space-y-4 dark:bg-[#0f0e0c] dark:border-[#2e2924]"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <span className="mt-1 p-2 rounded-xl border-2 border-black bg-accent/40 dark:border-[#2e2924]">
              <BookOpen size={18} aria-hidden />
            </span>
            <div>
              <p className="text-[10px] font-black uppercase tracking-widest text-muted dark:text-[#c4bbae]">
                Explain like I&apos;m new
              </p>
              <h2
                id="glossary-drawer-title"
                className="text-2xl font-black text-text dark:text-[#f0ebe2]"
              >
                {entry.term}
              </h2>
            </div>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="px-3 py-1 border-2 border-black rounded-lg font-black text-xs hover:bg-surface-low dark:border-[#2e2924] dark:text-[#f0ebe2]"
            aria-label="Close glossary"
          >
            <X size={16} />
          </button>
        </div>

        <p className="text-sm font-black text-primary">{entry.short}</p>
        <p className="text-sm font-bold leading-relaxed text-muted dark:text-[#c4bbae]">
          {entry.definition}
        </p>

        {entry.aliases && entry.aliases.length > 0 && (
          <div>
            <p className="text-[10px] font-black uppercase tracking-widest text-muted dark:text-[#c4bbae] mb-2">
              Also matched as
            </p>
            <div className="flex flex-wrap gap-2">
              {entry.aliases.map((alias) => (
                <span
                  key={alias}
                  className="text-xs font-mono font-bold px-2 py-1 rounded-lg border-2 border-black/15 dark:border-[#2e2924] bg-surface-low dark:bg-[#151411]"
                >
                  {alias}
                </span>
              ))}
            </div>
          </div>
        )}

        <p className="text-xs font-bold text-muted dark:text-[#c4bbae] pt-2 border-t-2 border-black/10 dark:border-[#2e2924]">
          Tip: glossary terms are underlined with dots in lesson text. Press Esc
          to close.
        </p>
      </aside>
    </div>
  );
}

export default GlossaryDrawer;
