import {
  useCallback,
  useEffect,
  useMemo,
  useContext,
  useRef,
  useState,
} from "react";
import {
  useBlocker,
  UNSAFE_DataRouterContext,
  UNSAFE_NavigationContext,
  type BlockerFunction,
} from "react-router-dom";

export interface UseUnsavedChangesOptions {
  isDirty: boolean;
  message?: string;
  onDiscard?: () => void;
  /**
   * The app mounts a plain BrowserRouter, where useBlocker is not available.
   * When true (and there is no data router), clicks on same-origin links are
   * intercepted while dirty so the dialog can ask first.
   */
  interceptLinks?: boolean;
}

export interface UnsavedChangesGuard {
  isBlocked: boolean;
  message: string;
  stay: () => void;
  discard: () => void;
  /** Use instead of navigate() for programmatic moves away from the page. */
  guardedNavigate: (to: string) => void;
}

function isPlainLeftClick(event: MouseEvent) {
  return (
    event.button === 0 &&
    !event.metaKey &&
    !event.ctrlKey &&
    !event.shiftKey &&
    !event.altKey
  );
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
  interceptLinks = false,
}: UseUnsavedChangesOptions): UnsavedChangesGuard {
  const hasDataRouter = useContext(UNSAFE_DataRouterContext) != null;
  const navigator = useContext(UNSAFE_NavigationContext)?.navigator;
  const [pendingTo, setPendingTo] = useState<string | null>(null);
  const isDirtyRef = useRef(isDirty);
  isDirtyRef.current = isDirty;

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

  // Without a data router there is no blocker, so catch link clicks ourselves.
  const legacyIntercept = interceptLinks && !hasDataRouter && !!navigator;
  useEffect(() => {
    if (!legacyIntercept || !isDirty) return;

    const handleClick = (event: MouseEvent) => {
      const anchor = (event.target as Element | null)?.closest?.("a[href]") as
        | HTMLAnchorElement
        | null
        | undefined;
      if (
        !anchor ||
        event.defaultPrevented ||
        !isPlainLeftClick(event) ||
        (anchor.target && anchor.target !== "_self") ||
        anchor.hasAttribute("download") ||
        anchor.getAttribute("aria-disabled") === "true"
      ) {
        return;
      }
      const url = new URL(anchor.href, window.location.href);
      const here = window.location;
      if (
        url.origin !== here.origin ||
        (url.pathname === here.pathname && url.search === here.search)
      ) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      setPendingTo(url.pathname + url.search + url.hash);
    };

    document.addEventListener("click", handleClick, true);
    return () => document.removeEventListener("click", handleClick, true);
  }, [legacyIntercept, isDirty]);

  useEffect(() => {
    if (!isDirty) setPendingTo(null);
  }, [isDirty]);

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

  const guardedNavigate = useCallback(
    (to: string) => {
      if (isDirtyRef.current && legacyIntercept) {
        setPendingTo(to);
      } else {
        navigator?.push(to);
      }
    },
    [legacyIntercept, navigator],
  );

  const stay = useCallback(() => {
    if (blocker && blocker.state === "blocked") {
      blocker.reset();
    }
    setPendingTo(null);
  }, [blocker]);

  const discard = useCallback(() => {
    onDiscard?.();
    if (blocker && blocker.state === "blocked") {
      blocker.proceed();
    } else if (pendingTo !== null) {
      setPendingTo(null);
      navigator?.push(pendingTo);
    }
  }, [blocker, onDiscard, pendingTo, navigator]);

  return useMemo(
    () => ({
      isBlocked: blocker ? blocker.state === "blocked" : pendingTo !== null,
      message,
      stay,
      discard,
      guardedNavigate,
    }),
    [blocker, pendingTo, message, stay, discard, guardedNavigate],
  );
}
