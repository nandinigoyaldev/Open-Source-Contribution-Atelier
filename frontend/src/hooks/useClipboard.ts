import { useCallback, useEffect, useRef, useState } from "react";
import { copyText, type ClipboardResult } from "../lib/clipboard";

export type ClipboardStatus = "idle" | "copying" | "success" | "error";

export interface UseClipboardOptions {
  resetAfterMs?: number;
}

export interface UseClipboardResult {
  status: ClipboardStatus;
  error: string | null;
  copy: (text: string) => Promise<ClipboardResult>;
  reset: () => void;
}

export function useClipboard({
  resetAfterMs = 2000,
}: UseClipboardOptions = {}): UseClipboardResult {
  const [status, setStatus] = useState<ClipboardStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const resetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearResetTimer = useCallback(() => {
    if (resetTimerRef.current !== null) {
      clearTimeout(resetTimerRef.current);
      resetTimerRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    clearResetTimer();
    setStatus("idle");
    setError(null);
  }, [clearResetTimer]);

  const scheduleReset = useCallback(() => {
    clearResetTimer();

    if (resetAfterMs <= 0) return;

    resetTimerRef.current = setTimeout(() => {
      setStatus("idle");
      setError(null);
      resetTimerRef.current = null;
    }, resetAfterMs);
  }, [clearResetTimer, resetAfterMs]);

  const copy = useCallback(
    async (text: string) => {
      clearResetTimer();
      setStatus("copying");
      setError(null);

      const result = await copyText(text);

      if (result.ok) {
        setStatus("success");
      } else {
        setStatus("error");
        setError(result.error.message);
      }

      scheduleReset();
      return result;
    },
    [clearResetTimer, scheduleReset],
  );

  useEffect(() => clearResetTimer, [clearResetTimer]);

  return { status, error, copy, reset };
}
