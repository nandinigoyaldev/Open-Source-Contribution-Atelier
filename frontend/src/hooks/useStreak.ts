import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";

export interface StreakData {
  current_streak: number;
  highest_streak: number;
  multiplier: number;
  next_milestone: number | null;
}

export function useStreak() {
  const { data, isLoading, error } = useQuery<StreakData>({
    queryKey: ["userStreak"],
    queryFn: () => fetchApi("/progress/streak/"),
  });

  return {
    streakData: data,
    isLoading,
    error,
  };
}
