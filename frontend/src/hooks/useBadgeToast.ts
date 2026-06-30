import { useCallback, useEffect, useState } from "react";
import type { BadgeToastData } from "../components/ui/BadgeToast";
import type { BadgeDefinition } from "../constants/badges";

interface UseBadgeToastReturn {
  toasts: BadgeToastData[];
  addToast: (slug: string) => void;
  addDynamicToast: (data: BadgeToastData) => void;
  dismissToast: (id: string) => void;
}

export function useBadgeToast(
  allBadges: BadgeDefinition[],
): UseBadgeToastReturn {
  const [toasts, setToasts] = useState<BadgeToastData[]>([]);

  const addToast = useCallback(
    (slug: string) => {
      const badge = allBadges.find((b) => b.id === slug);
      if (!badge) return;

      setToasts((prev) => {
        if (prev.some((t) => t.id === badge.id)) return prev;
        return [...prev, badge];
      });
    },
    [allBadges],
  );

  const addDynamicToast = useCallback((data: BadgeToastData) => {
    setToasts((prev) => {
      if (prev.some((t) => t.id === data.id)) return prev;
      return [...prev, data];
    });
  }, []);

  // Dev-only: dispatch window event "badge:test" with { id } to trigger a toast from DevTools.
  useEffect(() => {
    if (import.meta.env.PROD) return;

    const handler = (e: Event) => {
      const { id } = (e as CustomEvent<{ id: string }>).detail;
      addToast(id);
    };

    window.addEventListener("badge:test", handler);
    return () => window.removeEventListener("badge:test", handler);
  }, [addToast]);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { toasts, addToast, addDynamicToast, dismissToast };
}
