import { useCallback, useEffect, useMemo, useContext } from "react";
import { useBlocker, type BlockerFunction } from "react-router-dom";
import { UNSAFE_DataRouterContext } from "react-router";

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
 * If not within a Data Router (e.g. legacy BrowserRouter), in-app blocking is bypassed
 * to prevent react-router useBlocker runtime exceptions.
 */
export function useUnsavedChanges({
  isDirty,
  message = "You have unsaved changes. Discard them and leave this page?",
  onDiscard,
}: UseUnsavedChangesOptions): UnsavedChangesGuard {
  const hasDataRouter = useContext(UNSAFE_DataRouterContext) != null;

  const shouldBlock = useCallback<BlockerFunction>(
    ({ currentLocation, nextLocation }) =>
      isDirty &&
      (currentLocation.pathname !== nextLocation.pathname ||
        currentLocation.search !== nextLocation.search ||
        currentLocation.hash !== nextLocation.hash),
    [isDirty],
  );

  // eslint-disable-next-line react-hooks/rules-of-hooks
  const blocker = hasDataRouter ? useBlocker(shouldBlock) : null;

  useEffect(() => {
    if (!blocker || !isDirty) return;
    if (blocker.state === "blocked") {
      blocker.reset();
    }
  }, [blocker, isDirty]);

  useEffect(() => {
    if (!isDirty) return;

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = message;
      return message;
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [isDirty, message]);

  const stay = useCallback(() => {
    if (blocker && blocker.state === "blocked") {
      blocker.reset();
    }
  }, [blocker]);

  const discard = useCallback(() => {
    if (blocker && blocker.state === "blocked") {
      onDiscard?.();
      blocker.proceed();
    } else {
      onDiscard?.();
    }
  }, [blocker, onDiscard]);

  return useMemo(
    () => ({
      isBlocked: blocker ? blocker.state === "blocked" : false,
      message,
      stay,
      discard,
    }),
    [blocker, message, stay, discard],
  );
}
