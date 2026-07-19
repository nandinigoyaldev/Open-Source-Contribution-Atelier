import React, { useEffect, useState } from "react";
import { eventBus } from "../../core/events";
import { removeQueuedAction } from "../../lib/offlineQueue";
import { fetchApi } from "../../lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Server, Monitor } from "lucide-react";

interface ConflictData {
  lesson_slug: string;
  serverData: any;
  localData: any;
}

export function ConflictResolutionModal() {
  const queryClient = useQueryClient();
  const [conflict, setConflict] = useState<ConflictData | null>(null);
  const [isResolving, setIsResolving] = useState(false);

  useEffect(() => {
    const handleConflict = (payload: any) => {
      setConflict(payload);
    };

    eventBus.on("sync:conflict", handleConflict);
    return () => {
      eventBus.off("sync:conflict", handleConflict);
    };
  }, []);

  if (!conflict) return null;

  const handleKeepServer = async () => {
    setIsResolving(true);
    try {
      const id = `progress-sync-${conflict.lesson_slug}`;
      await removeQueuedAction(id, conflict.lesson_slug);
      queryClient.invalidateQueries({ queryKey: ["userProgress"] });
      setConflict(null);
    } finally {
      setIsResolving(false);
    }
  };

  const handleOverwriteServer = async () => {
    setIsResolving(true);
    try {
      // Overwrite the server by forcing a POST request with local data
      await fetchApi("/progress/me/", {
        method: "POST",
        body: JSON.stringify({
          lesson_slug: conflict.lesson_slug,
          score: conflict.localData.score ?? 100,
          completed: conflict.localData.completed ?? true,
        }),
      });
      const id = `progress-sync-${conflict.lesson_slug}`;
      await removeQueuedAction(id, conflict.lesson_slug);
      queryClient.invalidateQueries({ queryKey: ["userProgress"] });
      setConflict(null);
    } catch (e) {
      console.error("Failed to overwrite server state:", e);
      alert("Failed to update server. Please try again.");
    } finally {
      setIsResolving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
      <div className="bg-white dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl p-6 max-w-md w-full shadow-[6px_6px_0_#000]">
        <div className="flex items-center gap-3 text-amber-500 mb-4">
          <AlertTriangle size={28} />
          <h3 className="text-lg font-black uppercase text-text dark:text-[#f0ebe2]">
            Progress Conflict
          </h3>
        </div>

        <p className="text-xs font-bold text-muted dark:text-[#c4bbae] mb-6 leading-relaxed">
          While you were offline, you completed the lesson{" "}
          <span className="text-black dark:text-white underline">
            "{conflict.lesson_slug}"
          </span>
          . However, the server has a different progress record for this lesson.
        </p>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="border-2 border-black p-3 rounded-xl bg-gray-50 dark:bg-[#0f0e0c] dark:border-[#2e2924]">
            <h4 className="text-xs font-black uppercase flex items-center gap-1.5 mb-2 text-muted dark:text-[#9b8f80]">
              <Server size={12} /> Server Data
            </h4>
            <p className="text-xs font-bold dark:text-[#f0ebe2]">
              Score: {conflict.serverData?.score ?? "N/A"}
            </p>
            <p className="text-xs font-bold dark:text-[#f0ebe2]">
              Status:{" "}
              {conflict.serverData?.completed ? "Completed" : "In Progress"}
            </p>
          </div>

          <div className="border-2 border-black p-3 rounded-xl bg-[#ffb5e8]/20 dark:border-[#2e2924] dark:bg-pink-950/20">
            <h4 className="text-xs font-black uppercase flex items-center gap-1.5 mb-2 text-pink-600">
              <Monitor size={12} /> Local Offline
            </h4>
            <p className="text-xs font-bold dark:text-[#f0ebe2]">
              Score: {conflict.localData?.score ?? "N/A"}
            </p>
            <p className="text-xs font-bold dark:text-[#f0ebe2]">
              Status:{" "}
              {conflict.localData?.completed ? "Completed" : "In Progress"}
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <button
            onClick={handleOverwriteServer}
            disabled={isResolving}
            className="w-full py-2 bg-primary text-black font-black uppercase rounded-lg border-2 border-black hover:-translate-y-0.5 transition shadow-[2px_2px_0_#000] disabled:opacity-50"
          >
            {isResolving ? "Resolving..." : "Overwrite Server"}
          </button>
          <button
            onClick={handleKeepServer}
            disabled={isResolving}
            className="w-full py-2 bg-white hover:bg-gray-100 text-black font-black uppercase rounded-lg border-2 border-black hover:-translate-y-0.5 transition shadow-[2px_2px_0_#000] disabled:opacity-50 dark:bg-black dark:text-white dark:border-[#2e2924]"
          >
            Keep Server State
          </button>
        </div>
      </div>
    </div>
  );
}

export default ConflictResolutionModal;
