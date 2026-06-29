import React, { useMemo } from "react";
import {
  ReactFlow,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
  Node,
  Edge,
  Handle,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "dagre";
import { useNavigate } from "react-router-dom";

export interface LessonNode {
  id: string; // The database ID, but we'll use slug for react flow ID
  slug: string;
  title: string;
  summary: string;
  difficulty: string;
  estimatedMinutes: number;
  completed: boolean;
  prerequisites: string[];
}

interface LearningPathwayProps {
  lessons: LessonNode[];
}

interface CustomNodeData {
  title: string;
  completed: boolean;
  locked: boolean;
  summary?: string;
}

// Custom Node Component to show locked/unlocked/completed state
const CustomNode = ({ data }: { data: CustomNodeData }) => {
  const { title, completed, locked } = data;

  const bgColor = completed
    ? "bg-green-100 dark:bg-green-900 border-green-500"
    : locked
      ? "bg-gray-100 dark:bg-gray-800 border-gray-300 dark:border-gray-600 opacity-70"
      : "bg-blue-50 dark:bg-blue-900 border-blue-500";

  const textColor = completed
    ? "text-green-800 dark:text-green-200"
    : locked
      ? "text-gray-500 dark:text-gray-400"
      : "text-blue-800 dark:text-blue-200";

  return (
    <div
      className={`px-4 py-2 shadow-md rounded-md border-2 ${bgColor} min-w-[150px] text-center`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="w-16 !bg-teal-500"
      />
      <div className={`font-bold text-sm ${textColor}`}>{title}</div>
      <div className={`text-xs mt-1 ${textColor}`}>
        {completed ? "Completed" : locked ? "Locked" : "Unlocked"}
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="w-16 !bg-teal-500"
      />
    </div>
  );
};

const nodeTypes = {
  custom: CustomNode,
};

const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

const nodeWidth = 200;
const nodeHeight = 80;

const getLayoutedElements = (
  nodes: Node[],
  edges: Edge[],
  direction = "TB",
) => {
  dagreGraph.setGraph({ rankdir: direction });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  nodes.forEach((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    node.targetPosition = Position.Top;
    node.sourcePosition = Position.Bottom;

    // We are shifting the dagre node position (anchor=center center) to the top left
    // so it matches the React Flow node anchor point (top left).
    node.position = {
      x: nodeWithPosition.x - nodeWidth / 2,
      y: nodeWithPosition.y - nodeHeight / 2,
    };
  });

  return { nodes, edges };
};

export const LearningPathway: React.FC<LearningPathwayProps> = ({
  lessons,
}) => {
  const navigate = useNavigate();

  const { nodes: initialNodes, edges: initialEdges } = useMemo(() => {
    const completedSlugs = new Set(
      lessons.filter((l) => l.completed).map((l) => l.slug),
    );

    const nodes: Node[] = lessons.map((lesson) => {
      // Determine state
      const isLocked = !lesson.prerequisites.every((p) =>
        completedSlugs.has(p),
      );

      return {
        id: lesson.slug,
        type: "custom",
        position: { x: 0, y: 0 },
        data: {
          title: lesson.title,
          completed: lesson.completed,
          locked: isLocked,
          summary: lesson.summary,
        },
      };
    });

    const edges: Edge[] = [];
    lessons.forEach((lesson) => {
      lesson.prerequisites.forEach((prereqSlug) => {
        edges.push({
          id: `e-${prereqSlug}-${lesson.slug}`,
          source: prereqSlug,
          target: lesson.slug,
          type: "smoothstep",
          animated: true,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: "#14b8a6", // teal-500
          },
          style: { stroke: "#14b8a6", strokeWidth: 2 },
        });
      });
    });

    return getLayoutedElements(nodes, edges);
  }, [lessons]);

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  const onNodeClick = (event: React.MouseEvent, node: Node) => {
    if (!node.data.locked) {
      navigate(`/lessons/${node.id}`);
    } else {
      alert("This lesson is locked. Complete prerequisites first!");
    }
  };

  return (
    <div className="w-full h-full min-h-[600px] border border-gray-200 dark:border-gray-800 rounded-lg overflow-hidden bg-white dark:bg-gray-950">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        className="bg-gray-50 dark:bg-gray-900"
      >
        <Controls />
        <Background gap={16} size={1} />
      </ReactFlow>
    </div>
  );
};
