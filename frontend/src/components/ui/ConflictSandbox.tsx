import React, { useState, useMemo } from "react";
import { Check, AlertTriangle, GitMerge, XCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export interface ConflictSandboxProps {
  baseBranchName?: string;
  featureBranchName?: string;
  initialContent: string;
  onResolved?: (finalContent: string) => void;
}

interface NormalBlock {
  type: "normal";
  content: string;
}

interface ConflictBlock {
  type: "conflict";
  id: string;
  currentContent: string;
  incomingContent: string;
  resolution: "current" | "incoming" | "both" | "manual" | null;
  manualContent?: string;
}

type Block = NormalBlock | ConflictBlock;

function parseConflicts(text: string): Block[] {
  const lines = text.split("\n");
  const blocks: Block[] = [];

  let inConflict = false;
  let conflictStage: "current" | "incoming" = "current";
  let currentNormal = "";
  let currentConflict: Partial<ConflictBlock> = {};

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith("<<<<<<<")) {
      if (currentNormal) {
        blocks.push({ type: "normal", content: currentNormal });
        currentNormal = "";
      }
      inConflict = true;
      conflictStage = "current";
      currentConflict = {
        type: "conflict",
        id: `conflict-${i}`,
        currentContent: "",
        incomingContent: "",
        resolution: null,
      };
      continue;
    }

    if (line.startsWith("=======")) {
      if (inConflict) {
        conflictStage = "incoming";
      } else {
        currentNormal += line + "\n";
      }
      continue;
    }

    if (line.startsWith(">>>>>>>")) {
      if (inConflict) {
        // Strip trailing newlines for cleaner UI
        if (currentConflict.currentContent?.endsWith("\n")) {
          currentConflict.currentContent = currentConflict.currentContent.slice(
            0,
            -1,
          );
        }
        if (currentConflict.incomingContent?.endsWith("\n")) {
          currentConflict.incomingContent =
            currentConflict.incomingContent.slice(0, -1);
        }
        blocks.push(currentConflict as ConflictBlock);
        inConflict = false;
        currentConflict = {};
      } else {
        currentNormal += line + "\n";
      }
      continue;
    }

    if (inConflict) {
      if (conflictStage === "current") {
        currentConflict.currentContent += line + "\n";
      } else {
        currentConflict.incomingContent += line + "\n";
      }
    } else {
      currentNormal += line + "\n";
    }
  }

  if (currentNormal) {
    if (currentNormal.endsWith("\n"))
      currentNormal = currentNormal.slice(0, -1);
    blocks.push({ type: "normal", content: currentNormal });
  }

  return blocks;
}

export function ConflictSandbox({
  baseBranchName = "main",
  featureBranchName = "feature",
  initialContent,
  onResolved,
}: ConflictSandboxProps) {
  const [blocks, setBlocks] = useState<Block[]>(() =>
    parseConflicts(initialContent),
  );

  const allResolved = useMemo(() => {
    return blocks.every((b) => b.type === "normal" || b.resolution !== null);
  }, [blocks]);

  const handleResolve = (
    id: string,
    resolution: ConflictBlock["resolution"],
  ) => {
    setBlocks((prev) =>
      prev.map((b) => {
        if (b.type === "conflict" && b.id === id) {
          return { ...b, resolution };
        }
        return b;
      }),
    );
  };

  const handleComplete = () => {
    if (!allResolved || !onResolved) return;

    let finalString = "";
    blocks.forEach((b) => {
      if (b.type === "normal") {
        finalString += b.content + "\n";
      } else if (b.type === "conflict") {
        if (b.resolution === "current") finalString += b.currentContent + "\n";
        else if (b.resolution === "incoming")
          finalString += b.incomingContent + "\n";
        else if (b.resolution === "both") {
          finalString += b.currentContent + "\n" + b.incomingContent + "\n";
        }
      }
    });

    // Cleanup trailing newline
    if (finalString.endsWith("\n")) {
      finalString = finalString.slice(0, -1);
    }

    onResolved(finalString);
  };

  return (
    <div className="flex flex-col border-4 border-black rounded-2xl bg-surface-lowest shadow-card overflow-hidden w-full max-w-5xl mx-auto dark:bg-[#151411] dark:border-[#2e2924]">
      {/* Visual Git Timeline Header */}
      <div className="bg-white border-b-4 border-black p-6 relative overflow-hidden dark:bg-[#1f1c18] dark:border-[#2e2924]">
        <h3 className="text-xl font-black mb-4 flex items-center gap-2 text-text dark:text-[#f0ebe2] uppercase tracking-tight">
          <GitMerge className="h-6 w-6 text-primary" strokeWidth={3} />
          Merge Conflict Detected
        </h3>
        <p className="text-sm font-bold text-muted dark:text-[#c4bbae] max-w-xl">
          Git could not automatically merge your changes. Review the overlapping
          edits below and manually choose which lines to keep.
        </p>

        {/* Simplified Animated Timeline Graph */}
        <div className="mt-8 flex items-center justify-center relative h-24">
          <svg className="absolute inset-0 w-full h-full" overflow="visible">
            <path
              d="M 10 50 L 150 50"
              stroke="currentColor"
              strokeWidth="4"
              className="text-black dark:text-[#2e2924]"
              fill="none"
            />
            <path
              d="M 50 50 C 80 10, 100 10, 120 10 L 250 10"
              stroke="#FF3B30"
              strokeWidth="4"
              fill="none"
              strokeDasharray="6 6"
              className="animate-[dash_1s_linear_infinite]"
            />
            <path
              d="M 150 50 L 250 50"
              stroke="currentColor"
              strokeWidth="4"
              className="text-black dark:text-[#2e2924]"
              fill="none"
            />
            <path
              d="M 250 10 C 270 10, 290 50, 310 50 L 350 50"
              stroke="#FF3B30"
              strokeWidth="4"
              fill="none"
            />

            {/* Nodes */}
            <circle
              cx="50"
              cy="50"
              r="8"
              fill="currentColor"
              className="text-black dark:text-[#f0ebe2]"
            />
            <circle
              cx="150"
              cy="50"
              r="8"
              fill="currentColor"
              className="text-black dark:text-[#f0ebe2]"
            />
            <circle cx="120" cy="10" r="8" fill="#FF3B30" />
            <circle cx="250" cy="10" r="8" fill="#FF3B30" />
            <circle
              cx="250"
              cy="50"
              r="8"
              fill="currentColor"
              className="text-black dark:text-[#f0ebe2]"
            />

            {/* Conflict Node */}
            <circle
              cx="310"
              cy="50"
              r="14"
              fill="#FFD600"
              stroke="#000"
              strokeWidth="4"
              className="animate-pulse"
            />
            <text
              x="310"
              y="55"
              textAnchor="middle"
              fontSize="16"
              fontWeight="900"
              fill="#000"
            >
              !
            </text>

            {/* Labels */}
            <text
              x="50"
              y="75"
              fontSize="12"
              fontWeight="bold"
              fill="currentColor"
              className="text-muted dark:text-[#c4bbae]"
            >
              Base
            </text>
            <text x="120" y="-5" fontSize="12" fontWeight="bold" fill="#FF3B30">
              {featureBranchName}
            </text>
            <text
              x="150"
              y="75"
              fontSize="12"
              fontWeight="bold"
              fill="currentColor"
              className="text-muted dark:text-[#c4bbae]"
            >
              {baseBranchName}
            </text>
            <text x="310" y="80" fontSize="12" fontWeight="bold" fill="#FFD600">
              Conflict
            </text>
          </svg>
        </div>
      </div>

      {/* Editor Content */}
      <div className="bg-surface-lowest p-6 dark:bg-[#0f0e0c] font-mono text-sm leading-relaxed overflow-x-auto">
        {blocks.map((block, idx) => {
          if (block.type === "normal") {
            return (
              <div
                key={idx}
                className="py-2 px-4 text-text/80 dark:text-[#c4bbae]/80 whitespace-pre"
              >
                {block.content}
              </div>
            );
          }

          const isResolved = block.resolution !== null;

          return (
            <motion.div
              key={block.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`my-4 border-4 rounded-lg overflow-hidden shadow-card-sm transition-all ${
                isResolved
                  ? "border-green-500 shadow-[4px_4px_0_#22c55e]"
                  : "border-yellow-400 shadow-[4px_4px_0_#facc15]"
              }`}
            >
              {/* Conflict Header */}
              <div
                className={`p-3 border-b-4 border-inherit flex items-center justify-between bg-inherit ${isResolved ? "bg-green-100 dark:bg-green-900/30" : "bg-yellow-50 dark:bg-yellow-900/30"}`}
              >
                <div className="flex items-center gap-2 font-black uppercase text-xs tracking-widest">
                  {isResolved ? (
                    <span className="text-green-700 dark:text-green-400 flex items-center gap-1">
                      <Check size={16} /> Resolved
                    </span>
                  ) : (
                    <span className="text-yellow-700 dark:text-yellow-400 flex items-center gap-1">
                      <AlertTriangle size={16} /> Unresolved Conflict
                    </span>
                  )}
                </div>
                {isResolved && (
                  <button
                    onClick={() => handleResolve(block.id, null)}
                    className="text-xs font-bold px-2 py-1 bg-white border-2 border-black rounded shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 transition-all hover:bg-surface-low dark:bg-[#1f1c18] dark:text-[#f0ebe2]"
                  >
                    Undo
                  </button>
                )}
              </div>

              <div className="flex flex-col md:flex-row divide-y-4 md:divide-y-0 md:divide-x-4 divide-inherit bg-white dark:bg-[#151411]">
                {/* Current Changes (Left) */}
                <div
                  className={`flex-1 flex flex-col ${isResolved && block.resolution !== "current" && block.resolution !== "both" ? "opacity-30 grayscale pointer-events-none" : ""}`}
                >
                  <div className="p-2 border-b-4 border-inherit bg-blue-50 dark:bg-blue-900/20 text-blue-800 dark:text-blue-300 font-bold flex justify-between items-center text-xs">
                    <span>Current Change ({baseBranchName})</span>
                    {!isResolved && (
                      <button
                        onClick={() => handleResolve(block.id, "current")}
                        className="bg-blue-600 text-white px-3 py-1 rounded-lg border-2 border-black shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 transition-all font-black"
                      >
                        Accept Current
                      </button>
                    )}
                  </div>
                  <div className="p-4 whitespace-pre text-blue-900 dark:text-blue-200 bg-blue-50/50 dark:bg-blue-900/10 overflow-x-auto min-h-[100px]">
                    {block.currentContent}
                  </div>
                </div>

                {/* Incoming Changes (Right) */}
                <div
                  className={`flex-1 flex flex-col ${isResolved && block.resolution !== "incoming" && block.resolution !== "both" ? "opacity-30 grayscale pointer-events-none" : ""}`}
                >
                  <div className="p-2 border-b-4 border-inherit bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-300 font-bold flex justify-between items-center text-xs">
                    <span>Incoming Change ({featureBranchName})</span>
                    {!isResolved && (
                      <button
                        onClick={() => handleResolve(block.id, "incoming")}
                        className="bg-green-600 text-black px-3 py-1 rounded-lg border-2 border-black shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 transition-all font-black"
                      >
                        Accept Incoming
                      </button>
                    )}
                  </div>
                  <div className="p-4 whitespace-pre text-green-900 dark:text-green-200 bg-green-50/50 dark:bg-green-900/10 overflow-x-auto min-h-[100px]">
                    {block.incomingContent}
                  </div>
                </div>
              </div>

              {/* Accept Both Button spanning the bottom if not resolved */}
              <AnimatePresence>
                {!isResolved && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="border-t-4 border-inherit bg-surface dark:bg-[#1f1c18] p-3 flex justify-center"
                  >
                    <button
                      onClick={() => handleResolve(block.id, "both")}
                      className="bg-black text-white px-6 py-2 rounded-lg font-bold border-2 border-transparent hover:bg-gray-800 shadow-card-sm transition-all"
                    >
                      Accept Both Changes
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          );
        })}
      </div>

      {/* Footer Action */}
      <div className="bg-white border-t-4 border-black p-6 flex flex-col sm:flex-row items-center justify-between gap-4 dark:bg-[#1f1c18] dark:border-[#2e2924]">
        <div className="flex items-center gap-3">
          {allResolved ? (
            <div className="flex items-center gap-2 text-green-600 font-black px-4 py-2 bg-green-100 rounded-lg border-2 border-green-600">
              <Check size={20} /> All conflicts resolved
            </div>
          ) : (
            <div className="flex items-center gap-2 text-muted font-bold dark:text-[#c4bbae]">
              <XCircle size={20} /> Resolve all conflicts to continue
            </div>
          )}
        </div>
        <button
          onClick={handleComplete}
          disabled={!allResolved}
          className="px-8 py-3 bg-primary text-white font-black uppercase tracking-wider rounded-lg border-4 border-black shadow-card hover:-translate-y-1 active:translate-y-0 disabled:opacity-50 disabled:shadow-none disabled:translate-y-0 transition-all"
        >
          Complete Merge
        </button>
      </div>
    </div>
  );
}
