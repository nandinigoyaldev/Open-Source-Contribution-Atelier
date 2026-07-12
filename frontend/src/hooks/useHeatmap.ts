import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";

export interface HeatmapEntry {
  date: string;
  count: number;
}

export function useHeatmap(username?: string) {
  return useQuery({
    queryKey: ["activity-heatmap", username],
    queryFn: async (): Promise<HeatmapEntry[]> => {
      const url = username
        ? `/progress/heatmap/?username=${encodeURIComponent(username)}`
        : "/progress/heatmap/";
      const data = await fetchApi(url, {
        suppressErrorToast: true,
        requireAuth: !username,
      });
      return data || [];
    },
  });
}
