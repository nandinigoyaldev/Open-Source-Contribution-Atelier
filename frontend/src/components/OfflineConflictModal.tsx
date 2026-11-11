import React, { useState } from "react";
import { type ConflictRecord } from "../hooks/useOfflineConflictResolution";

interface OfflineConflictModalProps {
  conflict: ConflictRecord<any> | null;
  onResolve: (
    conflictId: string,
    choice: "local" | "remote" | "merge",
    mergedData?: any,
  ) => void;
  onCancel: () => void;
}

export const OfflineConflictModal: React.FC<OfflineConflictModalProps> = ({
  conflict,
  onResolve,
  onCancel,
}) => {
  const [mergeContent, setMergeContent] = useState("");
  const [activeTab, setActiveTab] = useState<"choose" | "merge">("choose");

  if (!conflict) return null;

  const localText =
    conflict.localData.encrypted_content ||
    conflict.localData.what_i_learned ||
    JSON.stringify(conflict.localData, null, 2);
  const serverText =
    conflict.serverData.encrypted_content ||
    conflict.serverData.what_i_learned ||
    JSON.stringify(conflict.serverData, null, 2);

  const handleMergeSubmit = () => {
    const merged = {
      ...conflict.localData,
      encrypted_content:
        conflict.entityType === "note" ? mergeContent : undefined,
      what_i_learned:
        conflict.entityType === "journal" ? mergeContent : undefined,
    };
    onResolve(conflict.id, "merge", merged);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[#141a26] border border-amber-500/30 rounded-2xl shadow-2xl max-w-2xl w-full p-6 space-y-5">
        <div className="flex items-center justify-between border-b border-gray-800 pb-3">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
              Edit Conflict Detected
            </h3>
            <p className="text-xs text-gray-400 mt-0.5">
              This {conflict.entityType} was modified on another device. Choose
              which version to preserve.
            </p>
          </div>
          <button
            onClick={onCancel}
            className="text-gray-400 hover:text-white text-sm"
          >
            âœ•
          </button>
        </div>

        <div className="flex gap-2 border-b border-gray-800 pb-2">
          <button
            onClick={() => setActiveTab("choose")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold ${
              activeTab === "choose"
                ? "bg-indigo-600 text-white"
                : "text-gray-400 hover:text-white"
            }`}
          >
            Compare & Pick
          </button>
          <button
            onClick={() => {
              setActiveTab("merge");
              setMergeContent(`${localText}\n\n--- MERGED WITH ---\n\n${serverText}`);
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold ${
              activeTab === "merge"
                ? "bg-indigo-600 text-white"
                : "text-gray-400 hover:text-white"
            }`}
          >
            Merge Manually
          </button>
        </div>

        {activeTab === "choose" ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-[#0b0f17] p-4 rounded-xl border border-gray-800 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-indigo-400 uppercase">
                    Your Local Version
                  </span>
                  <span className="text-[10px] text-gray-400 font-mono">
                    {conflict.localTimestamp || "Recent"}
                  </span>
                </div>
                <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap max-h-48 overflow-y-auto bg-gray-900/50 p-2.5 rounded-lg">
                  {localText}
                </pre>
              </div>
              <button
                onClick={() => onResolve(conflict.id, "local")}
                className="mt-4 w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold"
              >
                Keep Local Version
              </button>
            </div>

            <div className="bg-[#0b0f17] p-4 rounded-xl border border-gray-800 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-amber-400 uppercase">
                    Remote / Server Version
                  </span>
                  <span className="text-[10px] text-gray-400 font-mono">
                    {conflict.serverTimestamp || "Server"}
                  </span>
                </div>
                <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap max-h-48 overflow-y-auto bg-gray-900/50 p-2.5 rounded-lg">
                  {serverText}
                </pre>
              </div>
              <button
                onClick={() => onResolve(conflict.id, "remote")}
                className="mt-4 w-full py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg text-xs font-semibold border border-gray-700"
              >
                Keep Remote Version
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <textarea
              value={mergeContent}
              onChange={(e) => setMergeContent(e.target.value)}
              className="w-full h-48 bg-[#0b0f17] border border-gray-800 rounded-xl p-3 text-xs text-gray-200 font-mono focus:border-indigo-500 focus:outline-none"
            />
            <button
              onClick={handleMergeSubmit}
              className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold"
            >
              Save Merged Content
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
