import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Star, Trophy } from "lucide-react";
import { fetchApi } from "../../lib/api";

interface ChallengeOfTheDayData {
  id: number;
  title: string;
  summary: string;
  difficulty: string;
  points: number;
  bonus_points: number;
  already_completed: boolean;
}

export function ChallengeOfTheDayWidget() {
  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery<ChallengeOfTheDayData>({
    queryKey: ["challengeOfTheDay"],
    queryFn: () => fetchApi("/challenges/today/"),
    retry: false,
  });

  const completeMutation = useMutation({
    mutationFn: () =>
      fetchApi("/challenges/today/complete/", { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["challengeOfTheDay"] });
      queryClient.invalidateQueries({
        queryKey: ["contributorDashboardStats"],
      });
    },
  });

  if (isLoading) {
    return (
      <div className="rounded-2xl border-4 border-black bg-white p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none animate-pulse min-h-[160px]" />
    );
  }

  if (isError || !data) {
    return (
      <div className="rounded-2xl border-4 border-dashed border-black bg-white p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none flex items-center justify-center min-h-[160px]">
        <p className="text-sm font-bold text-muted dark:text-[#c4bbae]">
          No challenge set for today. Check back tomorrow! 🗓️
        </p>
      </div>
    );
  }

  const difficultyColour: Record<string, string> = {
    beginner: "bg-green-100 text-green-700 border-green-400",
    intermediate: "bg-yellow-100 text-yellow-700 border-yellow-400",
    advanced: "bg-red-100 text-red-700 border-red-400",
  };

  return (
    <div className="rounded-2xl border-4 border-black bg-white p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none flex flex-col justify-between gap-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="bg-primary/10 p-2 rounded-xl border-2 border-primary/20 dark:border-primary/50">
            <Star size={18} className="text-primary" />
          </div>
          <div>
            <p className="font-mono text-[10px] font-black uppercase tracking-widest text-primary">
              Challenge of the Day
            </p>
            <h3 className="font-black text-lg text-text dark:text-[#f0ebe2] leading-tight">
              {data.title}
            </h3>
          </div>
        </div>

        {/* Difficulty badge */}
        <span
          className={`shrink-0 text-[10px] font-black uppercase px-2 py-0.5 rounded-full border-2 ${
            difficultyColour[data.difficulty] ??
            "bg-gray-100 text-gray-700 border-gray-400"
          }`}
        >
          {data.difficulty}
        </span>
      </div>

      {/* Summary */}
      <p className="text-sm font-bold text-muted dark:text-[#c4bbae] leading-relaxed">
        {data.summary}
      </p>

      {/* Points row + CTA */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Trophy size={14} className="text-accent" />
          <span className="text-xs font-black text-text dark:text-[#f0ebe2]">
            {data.points} XP
          </span>
          <span className="text-[10px] font-black bg-accent/20 text-accent border border-accent/40 px-2 py-0.5 rounded-full">
            +{data.bonus_points} bonus
          </span>
        </div>

        {data.already_completed ? (
          <div className="flex items-center gap-1 text-green-600 bg-green-100 border-2 border-green-400 rounded-lg px-3 py-1.5 text-xs font-black dark:bg-green-900/20 dark:text-green-400">
            ✅ Completed
          </div>
        ) : (
          <button
            id="btn-complete-challenge-of-the-day"
            onClick={() => completeMutation.mutate()}
            disabled={completeMutation.isPending}
            className="rounded-lg bg-primary text-black border-2 border-black px-4 py-2 text-xs font-black shadow-card-sm hover:-translate-y-0.5 disabled:opacity-50 disabled:translate-y-0 transition-all"
          >
            {completeMutation.isPending ? "Saving…" : "Mark Complete"}
          </button>
        )}
      </div>
    </div>
  );
}
