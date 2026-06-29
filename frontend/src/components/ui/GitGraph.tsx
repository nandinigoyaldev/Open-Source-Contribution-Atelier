import React from "react";
import { RepoState } from "../../lib/gitSimulator";

interface GitGraphProps {
  state: RepoState;
}

export const GitGraph: React.FC<GitGraphProps> = ({ state }) => {
  const branchColumns: Record<string, number> = { main: 0 };
  let nextCol = 1;

  state.branches.forEach((b) => {
    if (b.name !== "main" && branchColumns[b.name] === undefined) {
      branchColumns[b.name] = nextCol++;
    }
  });

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

  return (
    <div className="w-full overflow-x-auto bg-white dark:bg-[#151411] border-4 border-black rounded-2xl shadow-[4px_4px_0_0_rgba(0,0,0,1)] dark:shadow-[4px_4px_0_0_#2e2924] mb-6">
      <div className="border-b-4 border-black p-3 bg-surface-low dark:bg-[#1f1c18] dark:border-[#2e2924] flex items-center justify-between">
        <h4 className="font-black text-sm uppercase flex items-center gap-2 text-text dark:text-[#f0ebe2]">
          <span>📊</span> Repository State
        </h4>
        {state.conflicts.length > 0 && (
          <span className="bg-red-500 text-white px-2 py-0.5 rounded text-[10px] font-black border-2 border-black animate-pulse">
            CONFLICT DETECTED
          </span>
        )}
      </div>
      <svg
        width={width}
        height={height}
        className="block min-w-full"
        role="img"
        aria-label="Git commit history graph"
      >
        {/* Draw Edges */}
        {state.commits.map((commit) => {
          const pos = nodePositions.get(commit.id);
          if (!pos) return null;

          return commit.parents.map((parentId) => {
            const parentPos = nodePositions.get(parentId);
            if (!parentPos) return null;

            return (
              <path
                key={`edge-${parentId}-${commit.id}`}
                d={createPath(parentPos.x, parentPos.y, pos.x, pos.y)}
                fill="none"
                stroke="currentColor"
                strokeWidth="4"
                className="text-black dark:text-[#524940]"
              />
            );
          });
        })}

        {/* Draw Conflict Boundaries */}
        {state.conflicts.length > 0 &&
          (() => {
            const headBranch = state.branches.find(
              (b) => b.name === state.HEAD,
            );
            const headTargetId = headBranch ? headBranch.target : state.HEAD;
            const pos = nodePositions.get(headTargetId);
            if (!pos) return null;

            return (
              <g>
                <rect
                  x={pos.x - 24}
                  y={pos.y - 24}
                  width={48}
                  height={48}
                  fill="rgba(239, 68, 68, 0.2)"
                  stroke="#ef4444"
                  strokeWidth="3"
                  strokeDasharray="6 4"
                  rx="12"
                  className="animate-pulse"
                />
                <text
                  x={pos.x}
                  y={pos.y - 32}
                  textAnchor="middle"
                  fill="#ef4444"
                  className="text-[10px] font-black pointer-events-none"
                >
                  MERGE CONFLICT
                </text>
              </g>
            );
          })()}

        {/* Draw Nodes */}
        {state.commits.map((commit) => {
          const pos = nodePositions.get(commit.id);
          if (!pos) return null;

          const isHead =
            state.branches.find((b) => b.name === state.HEAD)?.target ===
              commit.id || state.HEAD === commit.id;

          return (
            <g key={`node-${commit.id}`} className="cursor-pointer group">
              <circle
                cx={pos.x}
                cy={pos.y}
                r="14"
                className={`transition-all duration-200 group-hover:scale-125 stroke-black dark:stroke-[#f0ebe2] ${isHead ? "fill-[#FFD700] dark:fill-[#d4b300]" : "fill-white dark:fill-[#2e2924]"}`}
                strokeWidth="4"
              />
              {/* Tooltip on hover */}
              <g className="opacity-0 group-hover:opacity-100 transition-opacity">
                <rect
                  x={pos.x - 50}
                  y={pos.y + 20}
                  width={100}
                  height={40}
                  fill="white"
                  stroke="black"
                  strokeWidth="2"
                  rx="4"
                  className="dark:fill-[#151411] dark:stroke-[#f0ebe2]"
                />
                <text
                  x={pos.x}
                  y={pos.y + 35}
                  textAnchor="middle"
                  className="text-[10px] font-mono font-black fill-black dark:fill-white"
                >
                  {commit.id}
                </text>
                <text
                  x={pos.x}
                  y={pos.y + 50}
                  textAnchor="middle"
                  className="text-[9px] font-mono fill-muted dark:fill-[#c4bbae]"
                >
                  {commit.message.substring(0, 15)}...
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

          // If multiple branches point to the same commit, we need to offset them to prevent complete overlap.
          // For simplicity, we just draw them. A more complex layout could stack them vertically.
          // Let's compute vertical offset based on index of branch at this node.
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
                x={targetPos.x - 35}
                y={targetPos.y + yOffset}
                width={70}
                height={20}
                rx="6"
                className={`stroke-black stroke-[2px] ${isHeadBranch ? "fill-black dark:fill-[#f0ebe2]" : "fill-[#e2e8f0] dark:fill-[#2e2924]"}`}
              />
              <text
                x={targetPos.x}
                y={targetPos.y + yOffset + 14}
                textAnchor="middle"
                className={`text-[10px] font-black font-mono pointer-events-none ${isHeadBranch ? "fill-white dark:fill-black" : "fill-black dark:fill-[#c4bbae]"}`}
              >
                {branch.name}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};
