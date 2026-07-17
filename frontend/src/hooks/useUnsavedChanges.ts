import { useCallback, useEffect, useMemo } from "react";
import {
  useBlocker,
  type BlockerFunction,
} from "react-router-dom";

export interface UseUnsavedChangesOptions {
  isDirty: boolean;
  message?: string;
  onDiscard?: () => void;
}

export interface UnsavedChangesGuard {
  isBlocked: boolean;
  message: string;
  stay: () => void;
  discard: () => void;
}

/**
 * Protects dirty forms from both in-app navigation and hard page exits.
 *
 * Must be rendered inside the application's React Router provider.
 */
export function useUnsavedChanges({
  isDirty,
  message = "You have unsaved changes. Discard them and leave this page?",
  onDiscard,
}: UseUnsavedChangesOptions): UnsavedChangesGuard {
  const shouldBlock = useCallback<BlockerFunction>(
    ({ currentLocation, nextLocation }) =>
      isDirty &&
      (currentLocation.pathname !== nextLocation.pathname ||
        currentLocation.search !== nextLocation.search ||
        currentLocation.hash !== nextLocation.hash),
    [isDirty],
  );

  const blocker = useBlocker(shouldBlock);

  useEffect(() => {
    if (!isDirty && blocker.state === "blocked") {
      blocker.reset();
    }
  }, [blocker, isDirty]);

  useEffect(() => {
    if (!isDirty) return;

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [isDirty]);

  const stay = useCallback(() => {
    if (blocker.state === "blocked") {
      blocker.reset();
    }
  }, [blocker]);

  const discard = useCallback(() => {
    if (blocker.state !== "blocked") return;

    onDiscard?.();
    blocker.proceed();
  }, [blocker, onDiscard]);

  return useMemo(
    () => ({
      isBlocked: blocker.state === "blocked",
      message,
      stay,
      discard,
    }),
    [blocker.state, discard, message, stay],
  );
}
