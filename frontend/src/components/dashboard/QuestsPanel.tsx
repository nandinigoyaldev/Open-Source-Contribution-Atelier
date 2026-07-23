import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Circle,
  Gift,
  Loader2,
  Sparkles,
  Trophy,
  Timer,
} from "lucide-react";
import { useState } from "react";
import { fetchApi } from "../../lib/api";

interface QuestData {
  id: number;
  quest: {
    id: number;
    title: string;
    description: string;
    quest_type: string;
    frequency: string;
    requirement_count: number;
    xp_reward: number;
  };
  progress: number;
  completed: boolean;
  reward_claimed: boolean;
  assigned_at: string;
  expires_at: string;
}

function QuestCard({
  quest,
  onClaim,
  claiming,
}: {
  quest: QuestData;
  onClaim: (id: number) => void;
  claiming: boolean;
}) {
  const progressPct = Math.min(
    100,
    Math.round((quest.progress / quest.quest.requirement_count) * 100),
  );

  return (
    <div
      className={`rounded-2xl border-4 p-4 transition-all ${
        quest.completed
          ? "border-green-500 bg-green-50 dark:bg-green-900/20"
          : "border-black/10 bg-white dark:border-[#2e2924] dark:bg-[#1f1c18]"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {quest.completed ? (
              <CheckCircle2 className="w-5 h-5 text-green-500 shrink-0" />
            ) : (
              <Circle className="w-5 h-5 text-muted shrink-0" />
            )}
            <h4 className="font-bold text-sm text-text dark:text-[#f0ebe2] truncate">
              {quest.quest.title}
            </h4>
            <span className="text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-accent/10 text-accent shrink-0">
              {quest.quest.frequency === "daily" ? "24h" : "7d"}
            </span>
          </div>
          <p className="text-xs text-muted mt-1 ml-7">
            {quest.quest.description}
          </p>
        </div>
        <div className="text-right shrink-0">
          <div className="flex items-center gap-1 text-amber-600 font-bold text-sm">
            <Sparkles className="w-3.5 h-3.5" />
            {quest.quest.xp_reward} XP
          </div>
        </div>
      </div>

      <div className="mt-3 ml-7">
        <div className="flex items-center justify-between text-xs text-muted mb-1">
          <span>
            {quest.progress} / {quest.quest.requirement_count}
          </span>
          <span>{progressPct}%</span>
        </div>
        <div className="w-full h-2 bg-black/5 dark:bg-white/5 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              quest.completed ? "bg-green-500" : "bg-accent"
            }`}
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {quest.completed && !quest.reward_claimed && (
        <button
          onClick={() => onClaim(quest.id)}
          disabled={claiming}
          className="mt-3 ml-7 w-full py-2 px-4 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white font-bold text-xs rounded-xl border-2 border-black transition-colors flex items-center justify-center gap-2"
        >
          {claiming ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Gift className="w-4 h-4" />
          )}
          Claim Reward
        </button>
      )}

      {quest.reward_claimed && (
        <div className="mt-3 ml-7 flex items-center gap-2 text-green-600 text-xs font-bold">
          <CheckCircle2 className="w-4 h-4" />
          Reward claimed
        </div>
      )}

      {!quest.completed && (
        <div className="mt-2 ml-7 flex items-center gap-1 text-[10px] text-muted">
          <Timer className="w-3 h-3" />
          Expires {new Date(quest.expires_at).toLocaleDateString()}
        </div>
      )}
    </div>
  );
}

export function QuestsPanel() {
  const queryClient = useQueryClient();
  const [claimingId, setClaimingId] = useState<number | null>(null);

  const { data: quests, isLoading } = useQuery({
    queryKey: ["myQuests"],
    queryFn: () =>
      fetchApi<QuestData[]>("/gamification/my-quests/", {
        suppressErrorToast: true,
      }),
  });

  const claimMutation = useMutation({
    mutationFn: (questId: number) =>
      fetchApi("/gamification/my-quests/", {
        method: "POST",
        body: JSON.stringify({ quest_id: questId }),
        headers: { "Content-Type": "application/json" },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["myQuests"] });
      queryClient.invalidateQueries({ queryKey: ["contributorStats"] });
    },
    onSettled: () => setClaimingId(null),
  });

  const handleClaim = (questId: number) => {
    setClaimingId(questId);
    claimMutation.mutate(questId);
  };

  if (isLoading) {
    return (
      <div className="bg-surface-low rounded-3xl border-4 border-black p-5 dark:bg-[#151411] dark:border-[#2e2924]">
        <div className="flex items-center gap-2 mb-4">
          <Trophy className="w-5 h-5 text-accent" />
          <h3 className="font-black text-sm uppercase tracking-wider">
            Daily Quests
          </h3>
        </div>
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-muted" />
        </div>
      </div>
    );
  }

  const dailyQuests =
    quests?.filter((q) => q.quest.frequency === "daily") ?? [];
  const weeklyQuests =
    quests?.filter((q) => q.quest.frequency === "weekly") ?? [];

  const completedToday = dailyQuests.filter((q) => q.completed).length;
  const totalToday = dailyQuests.length;

  return (
    <div className="bg-surface-low rounded-3xl border-4 border-black p-5 dark:bg-[#151411] dark:border-[#2e2924]">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Trophy className="w-5 h-5 text-accent" />
          <h3 className="font-black text-sm uppercase tracking-wider">
            Quests
          </h3>
        </div>
        {totalToday > 0 && (
          <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-1 rounded-full bg-accent/10 text-accent">
            {completedToday}/{totalToday} done
          </span>
        )}
      </div>

      {(!quests || quests.length === 0) && (
        <div className="text-center py-8 text-muted">
          <Sparkles className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm font-bold">No quests yet</p>
          <p className="text-xs">Complete lessons to earn quests tomorrow!</p>
        </div>
      )}

      {dailyQuests.length > 0 && (
        <div className="mb-4">
          <h4 className="text-[10px] font-mono uppercase tracking-widest text-muted mb-2 px-1">
            Daily
          </h4>
          <div className="space-y-2">
            {dailyQuests.map((q) => (
              <QuestCard
                key={q.id}
                quest={q}
                onClaim={handleClaim}
                claiming={claimingId === q.id}
              />
            ))}
          </div>
        </div>
      )}

      {weeklyQuests.length > 0 && (
        <div>
          <h4 className="text-[10px] font-mono uppercase tracking-widest text-muted mb-2 px-1">
            Weekly
          </h4>
          <div className="space-y-2">
            {weeklyQuests.map((q) => (
              <QuestCard
                key={q.id}
                quest={q}
                onClaim={handleClaim}
                claiming={claimingId === q.id}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
