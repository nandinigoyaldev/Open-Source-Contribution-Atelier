import React, { useEffect, useState } from "react";
import { eventBus } from "../../core/events";
import { removeQueuedAction } from "../../lib/offlineQueue";
import { fetchApi } from "../../lib/api";
import { ApiError } from "../../lib/apiErrors";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Server, Monitor } from "lucide-react";

interface ConflictData {
  id?: string;
  /** "bookmark" for a queued bookmark removal, anything else is lesson progress. */
  kind?: string;
  lesson_slug: string;
  serverData: any;
  localData: any;
}

function formatSavedAt(value: unknown): string {
  const time = typeof value === "string" ? Date.parse(value) : NaN;
  return Number.isNaN(time) ? "N/A" : new Date(time).toLocaleString();
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

  const isBookmark = conflict.kind === "bookmark";
  const queuedId =
    conflict.id ??
    `${isBookmark ? "bookmark" : "progress-sync"}-${conflict.lesson_slug}`;
  const queryKey = isBookmark ? ["bookmarks"] : ["userProgress"];

  const settle = async () => {
    await removeQueuedAction(queuedId, conflict.lesson_slug);
    queryClient.invalidateQueries({ queryKey });
    setConflict(null);
  };

  const handleKeepServer = async () => {
    setIsResolving(true);
    try {
      await settle();
    } finally {
      setIsResolving(false);
    }
  };

  const overwrite = () => {
    if (isBookmark) {
      // Only the bookmark the user was shown: if it was saved again while the
      // prompt was open the server answers 409 instead of removing that one.
      const shownId = conflict.serverData?.id;
      const query =
        typeof shownId === "number" ? `?expected_id=${shownId}` : "";
      return fetchApi(`/progress/bookmarks/${conflict.lesson_slug}/${query}`, {
        method: "DELETE",
        suppressErrorToast: true,
      });
    }
    // The version shown to the user. Without it the server would refuse to
    // lower anything, with a stale one it answers 409 instead of overwriting
    // something the user never saw.
    return fetchApi("/progress/me/", {
      method: "POST",
      body: JSON.stringify({
        lesson_slug: conflict.lesson_slug,
        score: conflict.localData?.score ?? 100,
        completed: conflict.localData?.completed ?? true,
        expected_version: conflict.serverData?.version,
      }),
    });
  };

  const handleOverwriteServer = async () => {
    setIsResolving(true);
    try {
      try {
        await overwrite();
      } catch (e) {
        // Removed somewhere else meanwhile: what the user asked for
        if (!(isBookmark && e instanceof ApiError && e.status === 404)) throw e;
      }
      await settle();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.body) {
        // It moved again while the prompt was open: show the new numbers and let
        // the user decide again.
        setConflict({ ...conflict, serverData: e.body });
        return;
      }
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
            {isBookmark ? "Bookmark Conflict" : "Progress Conflict"}
          </h3>
        </div>

        {isBookmark ? (
          <p className="text-xs font-bold text-muted dark:text-[#c4bbae] mb-6 leading-relaxed">
            You removed{" "}
            <span className="text-black dark:text-white underline">
              "{conflict.lesson_slug}"
            </span>{" "}
            from Read Later while offline, but it was saved again after that,
            probably from another tab or device.
          </p>
        ) : (
          <p className="text-xs font-bold text-muted dark:text-[#c4bbae] mb-6 leading-relaxed">
            Your progress on the lesson{" "}
            <span className="text-black dark:text-white underline">
              "{conflict.lesson_slug}"
            </span>{" "}
            was not saved because the server has a newer record for it, probably
            from another tab or device.
          </p>
        )}

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="border-2 border-black p-3 rounded-xl bg-gray-50 dark:bg-[#0f0e0c] dark:border-[#2e2924]">
            <h4 className="text-xs font-black uppercase flex items-center gap-1.5 mb-2 text-muted dark:text-[#9b8f80]">
              <Server size={12} /> Server Data
            </h4>
            {isBookmark ? (
              <>
                <p className="text-xs font-bold dark:text-[#f0ebe2]">
                  Bookmark: Saved
                </p>
                <p className="text-xs font-bold dark:text-[#f0ebe2]">
                  Saved: {formatSavedAt(conflict.serverData?.created_at)}
                </p>
              </>
            ) : (
              <>
                <p className="text-xs font-bold dark:text-[#f0ebe2]">
                  Score: {conflict.serverData?.score ?? "N/A"}
                </p>
                <p className="text-xs font-bold dark:text-[#f0ebe2]">
                  Status:{" "}
                  {conflict.serverData?.completed ? "Completed" : "In Progress"}
                </p>
              </>
            )}
          </div>

          <div className="border-2 border-black p-3 rounded-xl bg-[#ffb5e8]/20 dark:border-[#2e2924] dark:bg-pink-950/20">
            <h4 className="text-xs font-black uppercase flex items-center gap-1.5 mb-2 text-pink-600">
              <Monitor size={12} /> This Device
            </h4>
            {isBookmark ? (
              <p className="text-xs font-bold dark:text-[#f0ebe2]">
                Bookmark: Removed
              </p>
            ) : (
              <>
                <p className="text-xs font-bold dark:text-[#f0ebe2]">
                  Score: {conflict.localData?.score ?? "N/A"}
                </p>
                <p className="text-xs font-bold dark:text-[#f0ebe2]">
                  Status:{" "}
                  {conflict.localData?.completed ? "Completed" : "In Progress"}
                </p>
              </>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <button
            onClick={handleOverwriteServer}
            disabled={isResolving}
            className="w-full py-2 bg-primary text-black font-black uppercase rounded-lg border-2 border-black hover:-translate-y-0.5 transition shadow-[2px_2px_0_#000] disabled:opacity-50"
          >
            {isResolving
              ? "Resolving..."
              : isBookmark
                ? "Remove It Anyway"
                : "Overwrite Server"}
          </button>
          <button
            onClick={handleKeepServer}
            disabled={isResolving}
            className="w-full py-2 bg-white hover:bg-gray-100 text-black font-black uppercase rounded-lg border-2 border-black hover:-translate-y-0.5 transition shadow-[2px_2px_0_#000] disabled:opacity-50 dark:bg-black dark:text-white dark:border-[#2e2924]"
          >
            {isBookmark ? "Keep Bookmark" : "Keep Server State"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ConflictResolutionModal;
