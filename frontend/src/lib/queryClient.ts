import { QueryClient } from "@tanstack/react-query";
import { eventBus } from "../core/events";
import { isRetryableApiError } from "./apiErrors";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 min — data is "fresh" for this long
      gcTime: 1000 * 60 * 30, // 30 min — keep cached data in memory
      retry: (failureCount, error) => {
        if (isRetryableApiError(error)) {
          return failureCount < 1;
        }

        if (error instanceof Error) {
          const message = error.message.toLowerCase();
          if (
            message.includes("unauthorized") ||
            message.includes("forbidden") ||
            message.includes("not found")
          ) {
            return false;
          }
        }

        return failureCount < 1;
      },
      refetchOnWindowFocus: false, // Avoid slow HF round-trips on tab switch
      networkMode: "offlineFirst", // Serve cache instantly, revalidate in background
    },
  },
});

// Listen for offline queue background syncs to update the UI
eventBus.on("sync:success", (payload?: { kind?: string }) => {
  queryClient.invalidateQueries({
    queryKey: payload?.kind === "bookmark" ? ["bookmarks"] : ["userProgress"],
  });
});
