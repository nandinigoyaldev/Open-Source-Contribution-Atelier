import { useCallback, useEffect, useRef, useState } from "react";
import type { BadgeToastData } from "../components/ui/BadgeToast";
import type { BadgeDefinition } from "../constants/badges";

interface UseBadgeToastReturn {
  toasts: BadgeToastData[];
  dismissToast: (id: string) => void;
}

export function useBadgeToast(
  earnedBadgeIds: string[],
  allBadges: BadgeDefinition[],
  isDataReady: boolean = false,
): UseBadgeToastReturn {
  const [toasts, setToasts] = useState<BadgeToastData[]>([]);

  // To ensure that only new entries trigger toast
  const sessionBaselineRef = useRef<Set<string> | null>(null);
  const earnedKey = earnedBadgeIds.join(",");

  useEffect(() => {
    if (!isDataReady) return;

    if (sessionBaselineRef.current === null) {
      sessionBaselineRef.current = new Set(earnedBadgeIds);
      return;
    }

    const newlyEarned = earnedBadgeIds.filter(
      (id) => !sessionBaselineRef.current!.has(id),
    );
    if (newlyEarned.length === 0) return;

    newlyEarned.forEach((id) => sessionBaselineRef.current!.add(id));

    const badgeMap = new Map(allBadges.map((b) => [b.id, b]));
    const newToasts: BadgeToastData[] = newlyEarned
      .map((id) => badgeMap.get(id))
      .filter((b): b is BadgeDefinition => b !== undefined);

    if (newToasts.length === 0) return;

    setToasts((prev) => {
      const queuedIds = new Set(prev.map((t) => t.id));
      const deduped = newToasts.filter((t) => !queuedIds.has(t.id));
      return deduped.length > 0 ? [...prev, ...deduped] : prev;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDataReady, earnedKey]);

  // Dev-only: dispatch window event "badge:test" with { id } to trigger a toast from DevTools.
  useEffect(() => {
    if (import.meta.env.PROD) return;

    const handler = (e: Event) => {
      const { id } = (e as CustomEvent<{ id: string }>).detail;
      const badge = allBadges.find((b) => b.id === id);
      if (!badge) {
        console.warn(
          `[badge:test] Unknown badge id "${id}". Valid:`,
          allBadges.map((b) => b.id),
        );
        return;
      }
      setToasts((prev) => {
        if (prev.some((t) => t.id === id)) return prev;
        return [...prev, badge];
      });
    };

    window.addEventListener("badge:test", handler);
    return () => window.removeEventListener("badge:test", handler);
  }, [allBadges]);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { toasts, dismissToast };
}
