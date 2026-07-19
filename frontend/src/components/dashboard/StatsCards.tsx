import { CheckCircle2, Code, Trophy } from "lucide-react";
import type { PersonalStats } from "./types";
import { StreakFlame } from "./StreakFlame";
import "./streakFlame.css";

interface StatsCardsProps {
  personalStats: PersonalStats;
  completedLessonsCount: number;
}

export function StatsCards({
  personalStats,
  completedLessonsCount,
}: StatsCardsProps) {
  return (
    <div
      id="tour-stats"
      className="grid grid-cols-2 gap-4"
      role="list"
      aria-label="Your dashboard statistics"
    >
      <div
        role="listitem"
        aria-label={`${personalStats.streak_days} streak days, longest ${personalStats.longest_streak || personalStats.streak_days}`}
        className="relative rounded-[2rem] border-4 border-black bg-white p-6 shadow-card flex flex-col justify-center items-center text-center dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none hover:-translate-y-0.5 transition-transform"
      >
        <div
          className="relative w-12 h-12 mb-2"
          style={{ color: "#ff7a18" }}
          aria-hidden="true"
        >
          <StreakFlame
            animate={personalStats.streak_days >= 3}
            className="absolute inset-0 m-auto"
          />
        </div>

        <span className="text-4xl font-black text-primary drop-shadow-[2px_2px_0_#000] dark:drop-shadow-none">
          {personalStats.streak_days}
        </span>

        <span className="font-black text-black uppercase tracking-widest text-[9px] mt-1 dark:text-[#c4bbae]">
          Streak Days
        </span>
        <div className="absolute top-2 right-2 bg-surface-low border-2 border-black rounded-full px-2 py-0.5 text-[8px] font-black text-muted flex items-center gap-1 dark:bg-[#151411]">
          <span className="text-[10px]" aria-hidden="true">
            🏆
          </span>{" "}
          Max: {personalStats.longest_streak || personalStats.streak_days}
        </div>
      </div>

      <div
        role="listitem"
        aria-label={`Atelier rank number ${personalStats.rank}`}
        className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card flex flex-col justify-center items-center text-center dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none hover:-translate-y-0.5 transition-transform"
      >
        <Trophy
          className="w-12 h-12 text-accent mb-2 animate-bounce"
          aria-hidden="true"
        />
        <span className="text-4xl font-black text-accent drop-shadow-[2px_2px_0_#000] dark:drop-shadow-none">
          #{personalStats.rank}
        </span>
        <span className="font-black text-black uppercase tracking-widest text-[9px] mt-1 dark:text-[#c4bbae]">
          Atelier Rank
        </span>
      </div>

      <div
        role="listitem"
        aria-label={`${completedLessonsCount} lessons solved`}
        className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card flex flex-col justify-center items-center text-center dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none hover:-translate-y-0.5 transition-transform"
      >
        <Code className="w-12 h-12 text-[#c3c0ff] mb-2" aria-hidden="true" />
        <span className="text-4xl font-black text-text dark:text-[#f0ebe2]">
          {completedLessonsCount}
        </span>
        <span className="font-black text-black uppercase tracking-widest text-[9px] mt-1 dark:text-[#c4bbae]">
          Lessons Solved
        </span>
      </div>

      <div
        role="listitem"
        aria-label={`${personalStats.prs_merged} pull requests merged`}
        className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card flex flex-col justify-center items-center text-center dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none hover:-translate-y-0.5 transition-transform"
      >
        <CheckCircle2
          className="w-12 h-12 text-green-500 mb-2"
          aria-hidden="true"
        />
        <span className="text-4xl font-black text-green-600">
          {personalStats.prs_merged}
        </span>
        <span className="font-black text-black uppercase tracking-widest text-[9px] mt-1 dark:text-[#c4bbae]">
          PRs Merged
        </span>
      </div>
    </div>
  );
}
