import { QueryClient } from "@tanstack/react-query";
import { eventBus } from "../core/events";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 min — data is "fresh" for this long
      gcTime: 1000 * 60 * 30, // 30 min — keep cached data in memory
      retry: 1,
      refetchOnWindowFocus: false, // Avoid slow HF round-trips on tab switch
      networkMode: "offlineFirst", // Serve cache instantly, revalidate in background
    },
  },
});

// Listen for offline queue background syncs to update the UI
eventBus.on("sync:success", () => {
  queryClient.invalidateQueries({ queryKey: ["userProgress"] });
});
