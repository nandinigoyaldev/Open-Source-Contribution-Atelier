import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";

export interface HeatmapEntry {
  date: string;
  count: number;
}

export function useHeatmap() {
  return useQuery({
    queryKey: ["activity-heatmap"],
    queryFn: async (): Promise<HeatmapEntry[]> => {
      const response = await fetchApi("/progress/heatmap/");
      if (!response.ok) {
        throw new Error("Failed to fetch activity heatmap data");
      }
      return response.json();
    },
  });
}
