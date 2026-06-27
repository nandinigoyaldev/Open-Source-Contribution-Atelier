import React from "react";
import { Flame, Zap, Trophy } from "lucide-react";
import { useStreak } from "../../hooks/useStreak";
import { motion } from "framer-motion";

export function StreakWidget() {
  const { streakData, isLoading } = useStreak();

  if (isLoading || !streakData) {
    return (
      <div className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card flex flex-col justify-center items-center text-center dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none min-h-[220px] animate-pulse">
        <div className="w-12 h-12 rounded-full bg-gray-200 dark:bg-gray-700" />
      </div>
    );
  }

  const { current_streak, multiplier, next_milestone } = streakData;
  const progressPercent = next_milestone
    ? Math.min(100, Math.round((current_streak / next_milestone) * 100))
    : 100;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card flex flex-col justify-between text-left dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none hover:-translate-y-0.5 transition-transform"
    >
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-xl font-black text-black dark:text-[#f0ebe2] flex items-center gap-2 uppercase tracking-widest">
            Streak
            {current_streak >= 3 && (
              <motion.span
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 200, damping: 10 }}
                className="bg-primary text-white text-[10px] font-black px-2 py-0.5 rounded-full border-2 border-black rotate-[-5deg]"
              >
                HOT!
              </motion.span>
            )}
          </h3>
          <p className="text-xs font-bold text-muted mt-1 dark:text-[#c4bbae]">
            XP Multiplier Active
          </p>
        </div>
        <div className="p-2 bg-primary/10 rounded-xl border-2 border-primary/20 dark:border-primary/50 text-primary">
          <Flame
            size={24}
            className={current_streak > 0 ? "animate-pulse" : ""}
          />
        </div>
      </div>

      <div className="flex justify-between items-end mb-4">
        <div className="flex flex-col">
          <div className="flex items-end gap-1">
            <span className="text-5xl font-black text-primary drop-shadow-[2px_2px_0_#000] dark:drop-shadow-none">
              {current_streak}
            </span>
          </div>
        </div>

        <div className="flex flex-col items-end">
          <div className="flex items-center gap-1 bg-accent/20 px-2 py-1 border-2 border-accent rounded-lg">
            <span className="text-xl font-black text-accent drop-shadow-[1px_1px_0_#000] dark:drop-shadow-none">
              {multiplier}x
            </span>
            <Zap size={16} className="text-accent" />
          </div>
        </div>
      </div>

      <div className="mt-auto">
        {next_milestone ? (
          <>
            <div className="flex justify-between text-[10px] font-black uppercase mb-1">
              <span className="text-text dark:text-[#c4bbae]">
                Next: {next_milestone} days
              </span>
              <span className="text-muted dark:text-[#888]">
                {next_milestone - current_streak} left
              </span>
            </div>
            <div className="h-3 w-full bg-surface-low border-2 border-black rounded-full overflow-hidden dark:bg-[#151411] dark:border-[#2e2924]">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${progressPercent}%` }}
                transition={{ duration: 1, ease: "easeOut" }}
                className="h-full bg-gradient-to-r from-primary to-accent border-r-2 border-black"
              />
            </div>
          </>
        ) : (
          <div className="flex items-center justify-center gap-2 p-2 bg-accent text-black font-black uppercase text-[10px] border-2 border-black rounded-lg">
            <Trophy size={14} />
            Max Multiplier Unlocked!
          </div>
        )}
      </div>
    </motion.div>
  );
}
