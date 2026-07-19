import {
  Check,
  ClipboardCopy,
  LoaderCircle,
  TriangleAlert,
} from "lucide-react";
import { useClipboard } from "../../hooks/useClipboard";

export interface CopyButtonProps {
  text: string;
  label?: string;
  copiedLabel?: string;
  errorLabel?: string;
  className?: string;
  disabled?: boolean;
  resetAfterMs?: number;
  onCopyResult?: (success: boolean) => void;
}

export function CopyButton({
  text,
  label = "Copy",
  copiedLabel = "Copied",
  errorLabel = "Copy failed",
  className = "",
  disabled = false,
  resetAfterMs = 2000,
  onCopyResult,
}: CopyButtonProps) {
  const { status, error, copy } = useClipboard({ resetAfterMs });
  const isDisabled = disabled || status === "copying" || text.length === 0;

  const handleCopy = async () => {
    const result = await copy(text);
    onCopyResult?.(result.ok);
  };

  const visibleLabel =
    status === "success"
      ? copiedLabel
      : status === "error"
        ? errorLabel
        : label;

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <button
        type="button"
        onClick={() => void handleCopy()}
        disabled={isDisabled}
        aria-label={visibleLabel}
        className={[
          "inline-flex items-center gap-2 rounded-lg border-2 border-current px-3 py-2",
          "font-bold transition-transform hover:-translate-y-0.5",
          "disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0",
          className,
        ].join(" ")}
      >
        {status === "copying" ? (
          <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
        ) : status === "success" ? (
          <Check className="h-4 w-4" aria-hidden="true" />
        ) : status === "error" ? (
          <TriangleAlert className="h-4 w-4" aria-hidden="true" />
        ) : (
          <ClipboardCopy className="h-4 w-4" aria-hidden="true" />
        )}
        <span>{visibleLabel}</span>
      </button>

      <span
        className="sr-only"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {status === "success"
          ? `${copiedLabel}.`
          : status === "error"
            ? error ?? `${errorLabel}.`
            : ""}
      </span>
    </div>
  );
}

export default CopyButton;
