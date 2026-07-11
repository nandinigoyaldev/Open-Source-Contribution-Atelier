import React from "react";
import { CodeSnapshot } from "../../lib/api";
import { Clock, Bookmark, ChevronRight, Check } from "lucide-react";

interface CodeTimelineProps {
  snapshots: CodeSnapshot[];
  onSelectSnapshot: (snapshot: CodeSnapshot) => void;
  onRestoreSnapshot: (snapshot: CodeSnapshot) => void;
  selectedSnapshotId: number | null;
  onClose: () => void;
}

export function CodeTimeline({
  snapshots,
  onSelectSnapshot,
  onRestoreSnapshot,
  selectedSnapshotId,
  onClose,
}: CodeTimelineProps) {
  return (
    <div className="w-64 flex flex-col bg-surface-lowest border-l-4 border-black dark:border-[#2e2924] h-full overflow-hidden">
      <div className="flex items-center justify-between p-4 border-b-4 border-black dark:border-[#2e2924] bg-surface-low dark:bg-[#151411]">
        <h3 className="font-bold text-sm text-text dark:text-[#f0ebe2] flex items-center gap-2">
          <Clock size={16} /> History
        </h3>
        <button
          onClick={onClose}
          aria-label="Close timeline"
          className="p-1 hover:bg-black/10 dark:hover:bg-white/10 rounded focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <ChevronRight size={16} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {snapshots.length === 0 ? (
          <div className="text-center p-4 text-xs text-muted">
            No history yet. Start typing to auto-save, or create a bookmark.
          </div>
        ) : (
          snapshots.map((snap) => {
            const isSelected = selectedSnapshotId === snap.id;
            const date = new Date(snap.timestamp);
            const dateString = date.toLocaleDateString(undefined, {
              month: "short",
              day: "numeric",
              year: "numeric",
            });
            const timeString = date.toLocaleTimeString(undefined, {
              hour: "numeric",
              minute: "2-digit",
            });

            return (
              <div
                key={snap.id}
                onClick={() => onSelectSnapshot(snap)}
                className={`p-3 rounded-lg border-2 cursor-pointer transition ${
                  isSelected
                    ? "border-primary bg-primary/10"
                    : "border-transparent hover:border-black/20 dark:hover:border-white/20 bg-black/5 dark:bg-white/5"
                }`}
              >
                <div className="flex justify-between items-start mb-1">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-text dark:text-[#f0ebe2]">
                    {snap.is_auto ? (
                      <Clock size={12} />
                    ) : (
                      <Bookmark size={12} className="text-amber-500" />
                    )}
                    <span>
                      {snap.label || (snap.is_auto ? "Auto-save" : "Bookmark")}
                    </span>
                  </div>
                </div>
                <div className="text-xs text-text/80 dark:text-[#e0dbd0] mt-1">
                  {dateString} at {timeString}
                </div>
                {isSelected && (
                  <div className="mt-2 flex justify-end">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onRestoreSnapshot(snap);
                      }}
                      aria-label="Restore snapshot"
                      className="flex items-center gap-1 px-2 py-1 text-xs font-bold bg-primary text-white rounded hover:bg-primary-dark transition focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-1 dark:focus:ring-offset-[#151411]"
                    >
                      <Check size={12} /> Restore
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
