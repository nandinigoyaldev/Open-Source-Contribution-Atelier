import React, { useState } from "react";
import { RepoState, GitCommit } from "../../lib/gitSimulator";

interface GitGraphProps {
  state: RepoState;
  onSelectCommit?: (commitId: string) => void;
  highlightedCommits?: string[];
}

interface ConflictInfo {
  commitId: string;
  file: string;
  oursContent?: string;
  theirsContent?: string;
}

export const GitGraph: React.FC<GitGraphProps> = ({
  state,
  onSelectCommit,
  highlightedCommits = [],
}) => {
  const [hoveredCommit, setHoveredCommit] = useState<string | null>(null);
  const [selectedCommit, setSelectedCommit] = useState<string | null>(null);

  const branchColumns: Record<string, number> = { main: 0 };
  let nextCol = 1;

  state.branches.forEach((b) => {
    if (b.name !== "main" && branchColumns[b.name] === undefined) {
      branchColumns[b.name] = nextCol++;
    }
  });

  const hasConflicts = state.conflicts.length > 0;

  const width = Math.max(state.commits.length * 90 + 150, 600);
  const height = Math.max(nextCol * 80 + 80, 250);

  const PADDING_X = 80;
  const PADDING_Y = 60;
  const SPACING_X = 90;
  const SPACING_Y = 80;

  const nodePositions = new Map<string, { x: number; y: number }>();

  state.commits.forEach((commit, i) => {
    const col = branchColumns[commit.branch] || 0;
    const x = PADDING_X + i * SPACING_X;
    const y = PADDING_Y + col * SPACING_Y;
    nodePositions.set(commit.id, { x, y });
  });

  // Calculate the path string for links
  const createPath = (sx: number, sy: number, ex: number, ey: number) => {
    if (sy === ey) {
      return `M ${sx} ${sy} L ${ex} ${ey}`;
    }
    // Curved line for branch/merge
    return `M ${sx} ${sy} C ${sx + SPACING_X / 2} ${sy}, ${ex - SPACING_X / 2} ${ey}, ${ex} ${ey}`;
  };

  // Determine branch colors for better visualization
  const getBranchColor = (branchName: string): string => {
    const colors = [
      "#3B82F6",
      "#10B981",
      "#F59E0B",
      "#EF4444",
      "#8B5CF6",
      "#EC4899",
    ];
    if (branchName === "main") return "#6B7280";
    const hash = branchName.split("").reduce((a, b) => a + b.charCodeAt(0), 0);
    return colors[hash % colors.length];
  };

  // Find commits involved in conflicts
  const isConflictCommit = (commit: GitCommit): boolean => {
    // Merge commits with multiple parents are often conflict sources
    return (
      commit.parents.length > 1 ||
      highlightedCommits.includes(commit.id) ||
      (hasConflicts && selectedCommit === commit.id)
    );
  };

  const handleCommitClick = (commitId: string) => {
    setSelectedCommit(commitId === selectedCommit ? null : commitId);
    onSelectCommit?.(commitId);
  };

  return (
    <div className="w-full overflow-x-auto bg-white dark:bg-[#151411] border-4 border-black rounded-2xl shadow-[4px_4px_0_0_rgba(0,0,0,1)] dark:shadow-[4px_4px_0_0_#2e2924] mb-6">
      <div className="border-b-4 border-black p-3 bg-surface-low dark:bg-[#1f1c18] dark:border-[#2e2924] flex items-center justify-between">
        <h4 className="font-black text-sm uppercase flex items-center gap-2 text-text dark:text-[#f0ebe2]">
          <span>📊</span> Repository State
        </h4>
        <div className="flex items-center gap-3">
          {hasConflicts && (
            <div className="flex items-center gap-2">
              <span className="bg-red-500 text-white px-2 py-0.5 rounded text-[10px] font-black border-2 border-black animate-pulse">
                ⚠️ CONFLICT DETECTED
              </span>
              <span className="text-xs text-red-400 font-medium">
                {state.conflicts.length} file(s)
              </span>
            </div>
          )}
          <div className="text-xs text-gray-500 dark:text-gray-400">
            {state.commits.length} commits • {state.branches.length} branches
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700 flex flex-wrap gap-3 text-xs">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-white dark:bg-[#2e2924] border-2 border-black" />
          <span className="text-gray-600 dark:text-gray-400">Commit</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-yellow-400 border-2 border-black" />
          <span className="text-gray-600 dark:text-gray-400">HEAD</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-3 rounded bg-blue-500 border border-black" />
          <span className="text-gray-600 dark:text-gray-400">Branch</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-3 rounded bg-red-500/30 border-2 border-dashed border-red-500" />
          <span className="text-gray-600 dark:text-gray-400">Conflict</span>
        </div>
        {state.branches.map((branch) => (
          <div key={branch.name} className="flex items-center gap-1.5">
            <div
              className="w-4 h-1 rounded"
              style={{ backgroundColor: getBranchColor(branch.name) }}
            />
            <span className="text-gray-600 dark:text-gray-400">
              {branch.name}
            </span>
          </div>
        ))}
      </div>

      <svg
        width={width}
        height={height}
        className="block min-w-full"
        role="img"
        aria-label="Git commit history graph"
      >
        {/* Draw Edges with branch colors */}
        {state.commits.map((commit) => {
          const pos = nodePositions.get(commit.id);
          if (!pos) return null;

          return commit.parents.map((parentId, parentIdx) => {
            const parentPos = nodePositions.get(parentId);
            if (!parentPos) return null;

            const isHighlighted =
              isConflictCommit(commit) || highlightedCommits.includes(parentId);

            return (
              <path
                key={`edge-${parentId}-${commit.id}-${parentIdx}`}
                d={createPath(parentPos.x, parentPos.y, pos.x, pos.y)}
                fill="none"
                stroke={
                  isHighlighted ? "#ef4444" : getBranchColor(commit.branch)
                }
                strokeWidth={isHighlighted ? "5" : "3"}
                strokeOpacity={isHighlighted ? 0.8 : 0.6}
                className={isHighlighted ? "animate-pulse" : ""}
              />
            );
          });
        })}

        {/* Draw Conflict Zones */}
        {state.commits.map((commit) => {
          if (!isConflictCommit(commit)) return null;
          const pos = nodePositions.get(commit.id);
          if (!pos) return null;

          return (
            <g key={`conflict-${commit.id}`}>
              {/* Conflict zone indicator */}
              <rect
                x={pos.x - 35}
                y={pos.y - 35}
                width={70}
                height={70}
                fill="rgba(239, 68, 68, 0.1)"
                stroke="#ef4444"
                strokeWidth="2"
                strokeDasharray="6 4"
                rx="8"
                className="animate-pulse"
              />
              {/* Conflict icon */}
              <text
                x={pos.x}
                y={pos.y - 40}
                textAnchor="middle"
                className="text-sm pointer-events-none"
                fill="#ef4444"
              >
                ⚠️
              </text>
            </g>
          );
        })}

        {/* Draw Nodes */}
        {state.commits.map((commit) => {
          const pos = nodePositions.get(commit.id);
          if (!pos) return null;

          const isHead =
            state.branches.find((b) => b.name === state.HEAD)?.target ===
              commit.id || state.HEAD === commit.id;
          const isHovered = hoveredCommit === commit.id;
          const isSelected = selectedCommit === commit.id;
          const isConflict = isConflictCommit(commit);
          const branchColor = getBranchColor(commit.branch);

          return (
            <g
              key={`node-${commit.id}`}
              className="cursor-pointer"
              onMouseEnter={() => setHoveredCommit(commit.id)}
              onMouseLeave={() => setHoveredCommit(null)}
              onClick={() => handleCommitClick(commit.id)}
            >
              {/* Selection ring */}
              {isSelected && (
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r="22"
                  fill="none"
                  stroke="#3B82F6"
                  strokeWidth="3"
                  className="animate-pulse"
                />
              )}

              {/* Node circle */}
              <circle
                cx={pos.x}
                cy={pos.y}
                r={isHovered || isSelected ? "18" : "14"}
                className={`transition-all duration-200 stroke-black dark:stroke-[#f0ebe2] ${
                  isConflict
                    ? "fill-red-400"
                    : isHead
                      ? "fill-yellow-400 dark:fill-yellow-500"
                      : "fill-white dark:fill-[#2e2924]"
                }`}
                strokeWidth="4"
                style={{ stroke: isConflict ? "#dc2626" : undefined }}
              />

              {/* Branch indicator ring */}
              <circle
                cx={pos.x}
                cy={pos.y}
                r="10"
                fill="none"
                stroke={branchColor}
                strokeWidth="2"
                className="opacity-60"
              />

              {/* Merge indicator (multiple parents) */}
              {commit.parents.length > 1 && (
                <g>
                  <circle
                    cx={pos.x + 10}
                    cy={pos.y - 10}
                    r="6"
                    fill="#ef4444"
                    stroke="white"
                    strokeWidth="1"
                  />
                  <text
                    x={pos.x + 10}
                    y={pos.y - 7}
                    textAnchor="middle"
                    className="text-[8px] font-black fill-white pointer-events-none"
                  >
                    M
                  </text>
                </g>
              )}

              {/* Tooltip on hover */}
              <g
                className={`transition-opacity duration-150 ${isHovered || isSelected ? "opacity-100" : "opacity-0"}`}
              >
                <rect
                  x={pos.x - 60}
                  y={pos.y + 22}
                  width={120}
                  height={60}
                  fill="white"
                  stroke="black"
                  strokeWidth="2"
                  rx="6"
                  className="dark:fill-[#1a1a2e] dark:stroke-[#f0ebe2]"
                />
                <text
                  x={pos.x}
                  y={pos.y + 38}
                  textAnchor="middle"
                  className="text-[10px] font-mono font-black fill-black dark:fill-white"
                >
                  {commit.id}
                </text>
                <text
                  x={pos.x}
                  y={pos.y + 52}
                  textAnchor="middle"
                  className="text-[9px] font-mono fill-gray-600 dark:fill-gray-400"
                >
                  {commit.message.substring(0, 18)}...
                </text>
                <text
                  x={pos.x}
                  y={pos.y + 66}
                  textAnchor="middle"
                  className="text-[8px] font-mono fill-blue-500"
                >
                  {commit.branch}
                </text>
              </g>
            </g>
          );
        })}

        {/* Draw Branch Labels */}
        {state.branches.map((branch) => {
          const targetPos = nodePositions.get(branch.target);
          if (!targetPos) return null;

          const isHeadBranch = state.HEAD === branch.name;
          const branchColor = getBranchColor(branch.name);

          const branchesAtThisNode = state.branches.filter(
            (b) => b.target === branch.target,
          );
          const indexAtNode = branchesAtThisNode.findIndex(
            (b) => b.name === branch.name,
          );
          const yOffset = -45 - indexAtNode * 24;

          return (
            <g key={`branch-${branch.name}`}>
              <rect
                x={targetPos.x - 40}
                y={targetPos.y + yOffset}
                width={80}
                height={20}
                rx="6"
                fill={isHeadBranch ? "#FFD700" : branchColor}
                stroke="black"
                strokeWidth="2"
                className="transition-all duration-200"
              />
              <text
                x={targetPos.x}
                y={targetPos.y + yOffset + 14}
                textAnchor="middle"
                className={`text-[10px] font-black font-mono pointer-events-none ${isHeadBranch ? "fill-black" : "fill-white"}`}
              >
                {branch.name}
              </text>
            </g>
          );
        })}

        {/* Commit IDs at bottom */}
        {state.commits.map((commit, i) => {
          const x = PADDING_X + i * SPACING_X;
          return (
            <text
              key={`label-${commit.id}`}
              x={x}
              y={height - 15}
              textAnchor="middle"
              className="text-[9px] font-mono fill-gray-500 dark:fill-gray-600"
            >
              {commit.id}
            </text>
          );
        })}
      </svg>

      {/* Conflict Details Panel */}
      {hasConflicts && (
        <div className="border-t-4 border-black dark:border-[#2e2924] p-4 bg-red-50 dark:bg-red-900/20">
          <h5 className="font-black text-sm text-red-600 dark:text-red-400 mb-3 flex items-center gap-2">
            <span>⚠️</span> Merge Conflicts
          </h5>
          <div className="space-y-2">
            {state.conflicts.map((file, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between bg-white dark:bg-[#1a1a2e] p-2 rounded border border-red-200 dark:border-red-800"
              >
                <div className="flex items-center gap-2">
                  <span className="text-red-500">📄</span>
                  <code className="text-xs font-mono">{file}</code>
                </div>
                <span className="text-[10px] font-medium text-red-500 bg-red-100 dark:bg-red-900 px-2 py-0.5 rounded">
                  NEEDS RESOLUTION
                </span>
              </div>
            ))}
          </div>
          <p className="text-xs text-red-600 dark:text-red-400 mt-3">
            💡 Use{" "}
            <code className="font-mono bg-red-100 dark:bg-red-900 px-1 rounded">
              git add &lt;file&gt;
            </code>{" "}
            to stage resolved files after editing.
          </p>
        </div>
      )}
    </div>
  );
};
