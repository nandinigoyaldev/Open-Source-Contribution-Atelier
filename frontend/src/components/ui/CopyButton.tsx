import { Check, ClipboardCopy, LoaderCircle, TriangleAlert } from "lucide-react";
import { useClipboard } from "../../hooks/useClipboard";
import Tooltip from "./Tooltip";

export type CopyButtonProps = {
  text: string;
  label?: string;
  copiedLabel?: string;
  errorLabel?: string;
  disabled?: boolean;
  resetAfterMs?: number;
};

export default function CopyButton({
  text,
  label = "Copy",
  copiedLabel = "Copied!",
  errorLabel = "Copy failed",
  disabled = false,
  resetAfterMs = 2000,
}: CopyButtonProps) {
  const { status, error, copy } = useClipboard({ resetAfterMs });
  const isCopying = status === "copying";
  const isDisabled = disabled || isCopying || text.length === 0;

  const visibleLabel =
    status === "success"
      ? copiedLabel
      : status === "error"
        ? errorLabel
        : label;

  return (
    <>
      <Tooltip content={visibleLabel}>
        <button
          type="button"
          onClick={() => void copy(text)}
          disabled={isDisabled}
          aria-label={visibleLabel}
          className="rounded-lg border-2 border-black bg-surface-low px-3 py-1 text-xs font-black text-black shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 transition-all cursor-pointer flex items-center justify-center min-w-[72px] disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0"
        >
          {isCopying ? (
            <LoaderCircle className="w-3.5 h-3.5 mr-1 animate-spin" aria-hidden="true" />
          ) : status === "success" ? (
            <Check className="w-3.5 h-3.5 mr-1" strokeWidth={3} aria-hidden="true" />
          ) : status === "error" ? (
            <TriangleAlert className="w-3.5 h-3.5 mr-1" aria-hidden="true" />
          ) : (
            <ClipboardCopy className="w-3.5 h-3.5 mr-1" aria-hidden="true" />
          )}
          {visibleLabel}
        </button>
      </Tooltip>

      <span className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {status === "success"
          ? `${copiedLabel}.`
          : status === "error"
            ? error ?? `${errorLabel}.`
            : ""}
      </span>
    </>
  );
}
