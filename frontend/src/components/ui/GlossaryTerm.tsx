import React, { useId } from "react";
import type { GlossaryEntry } from "../../lib/glossary";

export type GlossaryTermProps = {
  entry: GlossaryEntry;
  children: React.ReactNode;
  onOpen: (entry: GlossaryEntry) => void;
};

/**
 * Clickable / keyboard-activatable glossary term in lesson prose.
 */
export function GlossaryTerm({ entry, children, onOpen }: GlossaryTermProps) {
  const descId = useId();

  return (
    <>
      <button
        type="button"
        className="glossary-term inline p-0 m-0 border-0 bg-transparent cursor-pointer font-inherit text-inherit underline decoration-dotted decoration-2 underline-offset-2 decoration-accent text-primary hover:decoration-solid focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent rounded-sm"
        onClick={() => onOpen(entry)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onOpen(entry);
          }
        }}
        aria-describedby={descId}
        title={entry.short}
      >
        {children}
      </button>
      <span id={descId} className="sr-only">
        Glossary: {entry.short}
      </span>
    </>
  );
}

export default GlossaryTerm;
