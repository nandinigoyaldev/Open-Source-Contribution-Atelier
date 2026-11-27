import React, { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Flame, ShieldCheck, ShieldOff } from "lucide-react";
import { fetchApi } from "../../lib/api";
import { useStreak } from "../../hooks/useStreak";
import type { components } from "../../types/api";

type FreezeStatus = components["schemas"]["StreakFreezeStatus"];

const QUERY_KEY = ["streakFreezes"];

function StreakFreezePanel() {
  const queryClient = useQueryClient();
  const { streakData } = useStreak();
  const { data, isLoading, isError } = useQuery<FreezeStatus>({
    queryKey: QUERY_KEY,
    queryFn: () =>
      fetchApi("/progress/streak/freezes/", { suppressErrorToast: true }),
  });
  const action = useMutation({
    mutationFn: (url: string) =>
      fetchApi(url, { method: "POST", suppressErrorToast: true }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  });

  if (isLoading) {
    return <p className="text-sm">Loading streak freezes...</p>;
  }
  if (isError || !data) {
    return (
      <p role="alert" className="text-sm text-red-600">
        Could not load streak freezes.
      </p>
    );
  }

  const held = data.streak_freezes;
  const claimable = data.weeks.some((week) => week.claimable);
  const thisWeek = data.weeks[data.weeks.length - 1];
  const ShieldIcon = held > 0 ? ShieldCheck : ShieldOff;
  const buttonClass =
    "w-full rounded-lg border-2 border-black px-3 py-2 text-sm font-bold disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <div className="space-y-3">
      {streakData && (
        <p className="text-sm font-bold">
          Current streak: {streakData.current_streak} days
        </p>
      )}
      <div
        data-testid="freeze-shield"
        data-active={held > 0}
        className={`flex items-center gap-3 rounded-lg border-2 p-3 ${
          held > 0
            ? "border-sky-500 bg-sky-50 dark:bg-sky-950/40"
            : "border-dashed border-slate-300 dark:border-[#2E2924]"
        }`}
      >
        <ShieldIcon
          size={28}
          aria-hidden="true"
          className={held > 0 ? "text-sky-500" : "text-slate-400"}
        />
        <div>
          <p className="text-sm font-black">
            {held} streak {held === 1 ? "freeze" : "freezes"}
          </p>
          <p className="text-xs">
            {held > 0
              ? "Shield ready for your next missed day."
              : "No shield. A missed day ends your streak."}
          </p>
        </div>
      </div>
      {data.last_protected_date && (
        <p className="text-xs">Last used for {data.last_protected_date}</p>
      )}

      {claimable ? (
        <button
          type="button"
          className={`${buttonClass} bg-amber-400 text-black`}
          disabled={action.isPending}
          onClick={() =>
            action.mutate("/progress/streak/freezes/claim-weekly/")
          }
        >
          Claim weekly goal freeze
        </button>
      ) : (
        thisWeek && (
          <p className="text-xs">
            {thisWeek.claimed
              ? "This week's freeze is claimed."
              : `Weekly goal: ${thisWeek.completed_lessons}/${thisWeek.target_lessons} lessons for a free freeze.`}
          </p>
        )
      )}

      <button
        type="button"
        className={buttonClass}
        disabled={action.isPending || data.xp_balance < data.price_xp}
        onClick={() => action.mutate("/auth/shop/streak-freeze/")}
      >
        Redeem for {data.price_xp} XP
      </button>
      <p className="text-xs">You have {data.xp_balance} XP.</p>

      {action.isError && (
        <p role="alert" className="text-xs text-red-600">
          {action.error.message}
        </p>
      )}
    </div>
  );
}

export function StreakFreezePopover() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex items-center p-2 rounded-lg border border-slate-200 dark:border-[#2E2924] text-orange-500 hover:bg-slate-50 dark:hover:bg-white/5 transition-colors"
        aria-label="Streak and freezes"
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <Flame size={16} aria-hidden="true" />
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Streak freezes"
          className="fixed right-4 top-14 sm:absolute sm:right-0 sm:top-full sm:mt-1 w-72 max-w-[calc(100vw-2rem)] rounded-xl border-2 border-slate-200 dark:border-[#2E2924] bg-white dark:bg-[#1a1915] p-4 text-slate-700 dark:text-slate-300 shadow-lg z-50"
        >
          <StreakFreezePanel />
        </div>
      )}
    </div>
  );
}
