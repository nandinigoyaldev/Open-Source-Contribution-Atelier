import React, { useMemo, useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
  Node,
  Edge,
  Handle,
  Position,
  NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "dagre";
import { RepoState, GitCommit } from "../../lib/gitSimulator";
import clsx from "clsx";

interface GitGraphProps {
  state: RepoState;
  onSelectCommit?: (commitId: string) => void;
  highlightedCommits?: string[];
}

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

const CommitNode = ({ data }: NodeProps) => {
  const isSelected = data.isSelected as boolean;
  const isHead = data.isHead as boolean;
  const isConflict = data.isConflict as boolean;
  const branchColor = data.branchColor as string;

  return (
    <div
      className={clsx(
        "relative flex flex-col items-center justify-center p-2 rounded-lg border-2 bg-white dark:bg-[#2e2924] shadow-sm cursor-pointer transition-transform hover:scale-105 min-w-[120px]",
        isSelected ? "border-blue-500 shadow-md" : "border-black",
        isConflict ? "animate-pulse ring-4 ring-red-500/50" : ""
      )}
      style={{
        borderTopColor: branchColor,
        borderTopWidth: "4px",
      }}
    >
      <Handle type="target" position={Position.Left} className="opacity-0" />
      
      {isHead && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-yellow-400 text-black text-[10px] font-black px-1.5 rounded border border-black shadow-[1px_1px_0_0_rgba(0,0,0,1)]">
          HEAD
        </div>
      )}
      {isConflict && (
        <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 bg-red-500 text-white text-[10px] font-black px-1.5 rounded border border-black shadow-[1px_1px_0_0_rgba(0,0,0,1)]">
          ⚠️ CONFLICT
        </div>
      )}

      <div className="text-xs font-mono font-bold">{String(data.id).substring(0, 7)}</div>
      <div className="text-[10px] text-gray-500 mt-1 truncate w-full text-center px-1" title={String(data.message)}>
        {data.message}
      </div>
      
      <Handle type="source" position={Position.Right} className="opacity-0" />
    </div>
  );
};

const nodeTypes = {
  commit: CommitNode,
};

const getLayoutedElements = (nodes: Node[], edges: Edge[]) => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  
  // Left to right layout
  dagreGraph.setGraph({ rankdir: "LR", ranksep: 60, nodesep: 50 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 140, height: 70 });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const newNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - 140 / 2,
        y: nodeWithPosition.y - 70 / 2,
      },
    };
  });

  return { nodes: newNodes, edges };
};

export const GitGraph: React.FC<GitGraphProps> = ({
  state,
  onSelectCommit,
  highlightedCommits = [],
}) => {
  const hasConflicts = state.conflicts.length > 0;
  
  const { nodes, edges } = useMemo(() => {
    const initialNodes: Node[] = state.commits.map((commit) => {
      const isHead = state.branches.find((b) => b.name === state.HEAD)?.target === commit.id || state.HEAD === commit.id;
      const isConflict = commit.parents.length > 1 || highlightedCommits.includes(commit.id) || (hasConflicts && highlightedCommits.includes(commit.id));

      return {
        id: commit.id,
        type: "commit",
        position: { x: 0, y: 0 },
        data: {
          id: commit.id,
          message: commit.message,
          branchColor: getBranchColor(commit.branch),
          isHead,
          isConflict,
        },
      };
    });

    const initialEdges: Edge[] = [];
    state.commits.forEach((commit) => {
      commit.parents.forEach((parentId) => {
        const isConflict = commit.parents.length > 1 || highlightedCommits.includes(commit.id) || highlightedCommits.includes(parentId);
        
        initialEdges.push({
          id: `e-${parentId}-${commit.id}`,
          source: parentId,
          target: commit.id,
          animated: isConflict,
          style: { stroke: isConflict ? '#EF4444' : getBranchColor(commit.branch), strokeWidth: 3 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: isConflict ? '#EF4444' : getBranchColor(commit.branch),
          },
        });
      });
    });

    return getLayoutedElements(initialNodes, initialEdges);
  }, [state, highlightedCommits, hasConflicts]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (onSelectCommit) {
        onSelectCommit(node.id);
      }
    },
    [onSelectCommit]
  );

  return (
    <div className="w-full h-[400px] bg-white dark:bg-[#151411] border-4 border-black rounded-2xl shadow-[4px_4px_0_0_rgba(0,0,0,1)] dark:shadow-[4px_4px_0_0_#2e2924] mb-6 flex flex-col overflow-hidden">
      <div className="border-b-4 border-black p-3 bg-surface-low dark:bg-[#1f1c18] flex items-center justify-between z-10 shrink-0">
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

      <div className="flex-1 w-full h-full relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={onNodeClick}
          fitView
          minZoom={0.5}
          maxZoom={2}
          attributionPosition="bottom-right"
        >
          <Background color="#000" gap={16} size={1} />
          <Controls />
        </ReactFlow>
      </div>
    </div>
  );
};
