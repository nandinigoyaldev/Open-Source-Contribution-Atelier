export type ClipboardMethod = "clipboard-api" | "exec-command";

export type ClipboardResult =
  | { ok: true; method: ClipboardMethod }
  | {
      ok: false;
      method: ClipboardMethod | "unavailable";
      error: ClipboardError;
    };

export type ClipboardErrorCode =
  | "EMPTY_TEXT"
  | "DOCUMENT_UNAVAILABLE"
  | "PERMISSION_DENIED"
  | "COPY_FAILED";

export class ClipboardError extends Error {
  readonly code: ClipboardErrorCode;

  constructor(code: ClipboardErrorCode, message: string) {
    super(message);
    this.name = "ClipboardError";
    this.code = code;
  }
}

function normalizeClipboardError(error: unknown): ClipboardError {
  if (
    error instanceof DOMException &&
    (error.name === "NotAllowedError" || error.name === "SecurityError")
  ) {
    return new ClipboardError(
      "PERMISSION_DENIED",
      "Clipboard permission was denied.",
    );
  }

  return new ClipboardError("COPY_FAILED", "The text could not be copied.");
}

function copyWithExecCommand(text: string): ClipboardResult {
  if (
    typeof document === "undefined" ||
    !document.body ||
    typeof document.execCommand !== "function"
  ) {
    return {
      ok: false,
      method: "unavailable",
      error: new ClipboardError(
        "DOCUMENT_UNAVAILABLE",
        "Clipboard copying is unavailable in this environment.",
      ),
    };
  }

  const activeElement =
    document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
  const selection = window.getSelection?.() ?? null;
  const savedRanges: Range[] = [];

  if (selection) {
    for (let index = 0; index < selection.rangeCount; index += 1) {
      savedRanges.push(selection.getRangeAt(index).cloneRange());
    }
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.setAttribute("aria-hidden", "true");
  textarea.tabIndex = -1;
  textarea.style.position = "fixed";
  textarea.style.insetInlineStart = "-9999px";
  textarea.style.top = "0";
  textarea.style.opacity = "0";
  textarea.style.pointerEvents = "none";

  document.body.appendChild(textarea);

  try {
    textarea.focus();
    textarea.select();
    textarea.setSelectionRange(0, textarea.value.length);

    if (!document.execCommand("copy")) {
      return {
        ok: false,
        method: "exec-command",
        error: new ClipboardError(
          "COPY_FAILED",
          "The browser rejected the copy request.",
        ),
      };
    }

    return { ok: true, method: "exec-command" };
  } catch {
    return {
      ok: false,
      method: "exec-command",
      error: new ClipboardError(
        "COPY_FAILED",
        "The browser could not complete the copy request.",
      ),
    };
  } finally {
    textarea.remove();

    if (selection) {
      selection.removeAllRanges();
      savedRanges.forEach((range) => selection.addRange(range));
    }

    activeElement?.focus();
  }
}

/** Copies text without logging or exposing the copied value. */
export async function copyText(text: string): Promise<ClipboardResult> {
  if (text.length === 0) {
    return {
      ok: false,
      method: "unavailable",
      error: new ClipboardError("EMPTY_TEXT", "There is no text to copy."),
    };
  }

  if (
    typeof navigator !== "undefined" &&
    navigator.clipboard &&
    typeof navigator.clipboard.writeText === "function"
  ) {
    try {
      await navigator.clipboard.writeText(text);
      return { ok: true, method: "clipboard-api" };
    } catch (error) {
      const fallbackResult = copyWithExecCommand(text);

      if (fallbackResult.ok) {
        return fallbackResult;
      }

      return {
        ok: false,
        method: fallbackResult.method,
        error: normalizeClipboardError(error),
      };
    }
  }

  return copyWithExecCommand(text);
}
