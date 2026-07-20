import { useEffect, useRef } from "react";

interface UnsavedChangesDialogProps {
  open: boolean;
  message: string;
  onStay: () => void;
  onDiscard: () => void;
}

const FOCUSABLE_SELECTOR = [
  "button:not([disabled])",
  "[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

export function UnsavedChangesDialog({
  open,
  message,
  onStay,
  onDiscard,
}: UnsavedChangesDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const stayButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;

    previousFocusRef.current = document.activeElement as HTMLElement | null;
    stayButtonRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onStay();
        return;
      }

      if (event.key !== "Tab" || !dialogRef.current) return;

      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      );

      if (focusable.length === 0) {
        event.preventDefault();
        dialogRef.current.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previousFocusRef.current?.focus();
    };
  }, [open, onStay]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onStay();
      }}
    >
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="unsaved-changes-title"
        aria-describedby="unsaved-changes-description"
        tabIndex={-1}
        className="w-full max-w-md rounded-2xl border-4 border-black bg-white p-6 text-black shadow-card dark:bg-[#1a1816] dark:text-[#f0ebe2]"
      >
        <h2
          id="unsaved-changes-title"
          className="text-2xl font-black uppercase"
        >
          Unsaved changes
        </h2>

        <p
          id="unsaved-changes-description"
          className="mt-3 font-bold text-muted dark:text-[#c4bbae]"
        >
          {message}
        </p>

        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onDiscard}
            className="rounded-xl border-4 border-black bg-red-200 px-5 py-3 font-black uppercase text-black shadow-card-sm hover:-translate-y-0.5"
          >
            Discard changes
          </button>

          <button
            ref={stayButtonRef}
            type="button"
            onClick={onStay}
            className="rounded-xl border-4 border-black bg-accent px-5 py-3 font-black uppercase text-black shadow-card-sm hover:-translate-y-0.5"
          >
            Stay here
          </button>
        </div>
      </div>
    </div>
  );
}

export default UnsavedChangesDialog;
