import { useCallback } from "react";
import { useNetworkStatus } from "../context/useNetworkStatus";
import { enqueueOfflineAction } from "../lib/offlineQueue";
import { getAccessToken } from "../lib/authToken";
import { fetchApi } from "../lib/api";

export function useOfflineSync() {
  const { isOnline } = useNetworkStatus();

  const syncProgress = useCallback(
    async (vars: {
      lesson_slug: string;
      score?: number;
      completed?: boolean;
    }) => {
      const payload = {
        lesson_slug: vars.lesson_slug,
        score: vars.score ?? 100,
        completed: vars.completed ?? true,
      };

      if (isOnline) {
        return fetchApi("/progress/me/", {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      } else {
        const token = getAccessToken();
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
        };
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }

        await enqueueOfflineAction(
          "/progress/me/",
          "PATCH",
          headers,
          payload,
          "progress",
          vars.lesson_slug,
        );

        return {
          lesson_slug: vars.lesson_slug,
          completed: vars.completed ?? true,
          score: vars.score ?? 100,
          status: "queued",
        };
      }
    },
    [isOnline],
  );

  return { syncProgress };
}
