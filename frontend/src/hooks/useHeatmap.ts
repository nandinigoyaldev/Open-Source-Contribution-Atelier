import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";

export interface HeatmapEntry {
  date: string;
  count: number;
  breakdown?: {
    reading: number;
    quizzes: number;
    code_submissions: number;
  };
}

export function useHeatmap(username?: string, activityType?: string) {
  return useQuery({
    queryKey: ["activity-heatmap", username, activityType],
    queryFn: async (): Promise<HeatmapEntry[]> => {
      let url = username
        ? `/progress/heatmap/?username=${encodeURIComponent(username)}`
        : "/progress/heatmap/";

      const params = [];
      if (activityType && activityType !== "all") {
        params.push(`activity_type=${activityType}`);
      }

      if (params.length > 0) {
        const delimiter = url.includes("?") ? "&" : "?";
        url += `${delimiter}${params.join("&")}`;
      }

      const data = await fetchApi(url, {
        suppressErrorToast: true,
        requireAuth: !username,
      });
      return data || [];
    },
  });
}
