import React from "react";
import { Link } from "react-router-dom";
import { Sparkles, Info } from "lucide-react";

import Tooltip from "./Tooltip";

type WhyPayload = {
  score_breakdown?: {
    prerequisites?: number;
    streak?: number;
    xp_difficulty_fit?: number;
    recency?: number;
  };
  prerequisites?: {
    detail?: string;
    missing_titles?: string[];
    missing_count?: number;
    total_prerequisites?: number;
  };
  streak?: {
    detail?: string;
    current_streak_days?: number;
    activity_today?: boolean;
  };
  xp_level?: {
    detail?: string;
    avg_completed_score?: number;
    user_level_band?: number;
    lesson_difficulty?: string;
  };
  recency?: { detail?: string };
};

type LessonPayload = {
  id?: number;
  slug: string;
  title: string;
  difficulty?: string;
  estimated_minutes?: number;
  points?: number;
};

export function NextLessonWidget({
  recommended,
  why,
  disabled,
}: {
  recommended: LessonPayload | null;
  why: WhyPayload | null;
  disabled?: boolean;
}) {
  if (!recommended) return null;

  const difficulty = recommended.difficulty || "beginner";
  const minutes = recommended.estimated_minutes ?? 10;
  const points = recommended.points ?? undefined;

  const missingTitles = why?.prerequisites?.missing_titles || [];
  const prereqDetail = why?.prerequisites?.detail;
  const streakDetail = why?.streak?.detail;
  const xpDetail = why?.xp_level?.detail;
  const recencyDetail = why?.recency?.detail;

  const tooltipText = [
    prereqDetail ? `Prerequisites: ${prereqDetail}` : null,
    missingTitles.length ? `Missing: ${missingTitles.join(", ")}` : null,
    streakDetail ? `Streak: ${streakDetail}` : null,
    xpDetail ? `XP fit: ${xpDetail}` : null,
    recencyDetail ? `Recency: ${recencyDetail}` : null,
  ]
    .filter(Boolean)
    .join("\n");

  return (
    <section className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className="bg-[#ffcc00] p-3 rounded-2xl border-2 border-black flex-shrink-0 text-2xl dark:bg-[#ffcc00]/20 dark:text-[#ffcc00]">
            🎯
          </div>
          <div>
            <h3 className="font-black text-2xl dark:text-[#f0ebe2] flex items-center gap-2">
              Your Next Recommended Lesson
              <span className="font-mono text-xs bg-black text-white px-2 py-0.5 rounded-full uppercase dark:bg-[#2e2924]">
                {difficulty}
              </span>
            </h3>
            <p className="font-bold text-sm text-muted dark:text-[#c4bbae] mt-1">
              {recommended.title}
            </p>
          </div>
        </div>

        <Tooltip content={tooltipText}>
          <div className="flex items-center gap-1 text-xs font-black bg-amber-50 border-2 border-amber-200 px-2 py-1 rounded-lg dark:bg-[#1c1915]">
            <Info size={14} /> Why this?
          </div>
        </Tooltip>
      </div>

      <div className="grid gap-3 sm:grid-cols-[1fr_auto] items-center">
        <div className="text-xs font-bold text-black/70 dark:text-[#f0ebe2]">
          <span className="inline-flex items-center gap-2">
            <Sparkles size={14} /> {minutes} min •{" "}
            {points ? `${points} XP` : "XP ready"}
          </span>
        </div>

        <Link
          to={`/lessons/${recommended.slug}`}
          className={
            disabled
              ? "pointer-events-none opacity-50 w-full sm:w-auto rounded-lg bg-[#e2e8f0] text-black border-2 border-black px-4 py-2 text-xs font-black uppercase tracking-wider text-center"
              : "w-full sm:w-auto rounded-lg bg-accent text-black border-2 border-black px-4 py-2 text-xs font-black uppercase tracking-wider shadow-card-sm hover:-translate-y-0.5 transition-all text-center"
          }
        >
          Start Lesson 🚀
        </Link>
      </div>
    </section>
  );
}
