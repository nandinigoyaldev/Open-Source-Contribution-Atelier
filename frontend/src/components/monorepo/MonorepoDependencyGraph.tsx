import React, { useState, useMemo, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Boxes,
  AlertTriangle,
  Search,
  Download,
  RefreshCw,
  Zap,
  Sparkles,
  FileCode,
  CheckCircle2,
  Maximize2,
  ZoomIn,
  ZoomOut,
  Layers,
  ArrowRight,
  ShieldAlert,
  Sliders,
  Check,
  X,
  RotateCcw,
} from "lucide-react";

export interface PackageNode {
  id: string;
  name: string;
  version: string;
  dependencies: string[];
  type: "app" | "package" | "utility" | "service";
  x: number;
  y: number;
}

export interface ManifestPreset {
  id: string;
  name: string;
  description: string;
  configJson: string;
}

const PRESET_CONFIGS: ManifestPreset[] = [
  {
    id: "atelier-monorepo",
    name: "Atelier Platform Monorepo (Clean)",
    description: "Standard 4-tier clean architecture monorepo layout.",
    configJson: JSON.stringify(
      {
        name: "open-source-contribution-atelier",
        workspaces: ["apps/*", "packages/*", "services/*"],
        packages: [
          {
            name: "@atelier/frontend",
            type: "app",
            version: "1.0.0",
            dependencies: [
              "@atelier/ui-core",
              "@atelier/auth-sdk",
              "@atelier/utils",
            ],
          },
          {
            name: "@atelier/backend-api",
            type: "app",
            version: "1.0.0",
            dependencies: ["@atelier/auth-sdk", "@atelier/db-schema"],
          },
          {
            name: "@atelier/auth-sdk",
            type: "service",
            version: "2.1.0",
            dependencies: ["@atelier/utils", "@atelier/db-schema"],
          },
          {
            name: "@atelier/ui-core",
            type: "package",
            version: "3.0.0",
            dependencies: ["@atelier/utils", "@atelier/icons"],
          },
          {
            name: "@atelier/icons",
            type: "package",
            version: "1.2.0",
            dependencies: ["@atelier/utils"],
          },
          {
            name: "@atelier/db-schema",
            type: "service",
            version: "1.5.0",
            dependencies: ["@atelier/utils"],
          },
          {
            name: "@atelier/utils",
            type: "utility",
            version: "4.1.0",
            dependencies: [],
          },
        ],
      },
      null,
      2,
    ),
  },
  {
    id: "circular-bug-demo",
    name: "Turborepo with Circular Loop (Warning)",
    description: "Monorepo containing an accidental circular dependency cycle.",
    configJson: JSON.stringify(
      {
        name: "turborepo-ecommerce-app",
        workspaces: ["apps/*", "packages/*"],
        packages: [
          {
            name: "@shop/web",
            type: "app",
            version: "2.0.0",
            dependencies: ["@shop/auth", "@shop/checkout"],
          },
          {
            name: "@shop/checkout",
            type: "package",
            version: "1.1.0",
            dependencies: ["@shop/billing", "@shop/ui"],
          },
          {
            name: "@shop/billing",
            type: "service",
            version: "1.0.0",
            dependencies: ["@shop/auth"],
          },
          {
            name: "@shop/auth",
            type: "service",
            version: "2.1.0",
            dependencies: ["@shop/checkout"],
          }, // Circular: auth -> checkout -> billing -> auth
          {
            name: "@shop/ui",
            type: "package",
            version: "1.0.0",
            dependencies: ["@shop/utils"],
          },
          {
            name: "@shop/utils",
            type: "utility",
            version: "1.0.0",
            dependencies: [],
          },
        ],
      },
      null,
      2,
    ),
  },
];

export function MonorepoDependencyGraph() {
  const [activePreset, setActivePreset] = useState<ManifestPreset>(
    PRESET_CONFIGS[0],
  );
  const [jsonInput, setJsonInput] = useState<string>(
    PRESET_CONFIGS[0].configJson,
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [activeTab, setActiveTab] = useState<"graph" | "editor">("graph");
  const [parseError, setParseError] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  // Parse JSON manifest to extract package nodes
  const parsedPackages = useMemo<PackageNode[]>(() => {
    try {
      setParseError(null);
      const parsed = JSON.parse(jsonInput);
      const rawList = parsed.packages || [];

      // Calculate 2D Layout Positions
      const count = rawList.length;
      return rawList.map((pkg: any, idx: number) => {
        const angle = (idx / Math.max(count, 1)) * 2 * Math.PI;
        const radius = count > 5 ? 180 : 140;
        const centerX = 350;
        const centerY = 240;

        return {
          id: pkg.name,
          name: pkg.name,
          version: pkg.version || "1.0.0",
          type: pkg.type || "package",
          dependencies: pkg.dependencies || [],
          x: Math.round(centerX + radius * Math.cos(angle)),
          y: Math.round(centerY + radius * Math.sin(angle)),
        };
      });
    } catch (err: any) {
      setParseError("Invalid JSON manifest syntax. Please verify formatting.");
      return [];
    }
  }, [jsonInput]);

  // Cycle Detection Algorithm (DFS for Circular Dependencies)
  const circularCycles = useMemo<string[][]>(() => {
    if (!parsedPackages.length) return [];

    const adjMap = new Map<string, string[]>();
    parsedPackages.forEach((pkg) => {
      adjMap.set(pkg.id, pkg.dependencies);
    });

    const cycles: string[][] = [];
    const visited = new Set<string>();
    const recStack = new Set<string>();

    const dfs = (curr: string, path: string[]) => {
      visited.add(curr);
      recStack.add(curr);
      path.push(curr);

      const neighbors = adjMap.get(curr) || [];
      for (const neighbor of neighbors) {
        if (!visited.has(neighbor)) {
          dfs(neighbor, [...path]);
        } else if (recStack.has(neighbor)) {
          // Found cycle!
          const cycleStartIdx = path.indexOf(neighbor);
          if (cycleStartIdx !== -1) {
            const cycleLoop = [...path.slice(cycleStartIdx), neighbor];
            // Check uniqueness
            const cycleKey = cycleLoop.join("->");
            if (!cycles.some((c) => c.join("->") === cycleKey)) {
              cycles.push(cycleLoop);
            }
          }
        }
      }

      recStack.delete(curr);
    };

    parsedPackages.forEach((pkg) => {
      if (!visited.has(pkg.id)) {
        dfs(pkg.id, []);
      }
    });

    return cycles;
  }, [parsedPackages]);

  // Compute set of highlighted package IDs (target + direct upstream/downstream)
  const highlightedNodeIds = useMemo(() => {
    if (!searchQuery.trim()) return null;

    const queryLower = searchQuery.trim().toLowerCase();
    const matching = parsedPackages.filter((p) =>
      p.name.toLowerCase().includes(queryLower),
    );

    if (matching.length === 0) return new Set<string>();

    const highlighted = new Set<string>();
    matching.forEach((target) => {
      highlighted.add(target.id);
      // Direct Upstream Dependencies
      target.dependencies.forEach((depId) => highlighted.add(depId));
      // Direct Downstream Dependents
      parsedPackages.forEach((p) => {
        if (p.dependencies.includes(target.id)) {
          highlighted.add(p.id);
        }
      });
    });

    return highlighted;
  }, [searchQuery, parsedPackages]);

  // Handle Preset Change
  const handlePresetSelect = (preset: ManifestPreset) => {
    setActivePreset(preset);
    setJsonInput(preset.configJson);
    setSelectedNodeId(null);
  };

  // Helper to check if edge is part of a circular cycle
  const isCircularEdge = (sourceId: string, targetId: string): boolean => {
    return circularCycles.some((cycle) => {
      for (let i = 0; i < cycle.length - 1; i++) {
        if (cycle[i] === sourceId && cycle[i + 1] === targetId) return true;
      }
      return false;
    });
  };

  // Export SVG as File
  const handleExportSvg = () => {
    if (!svgRef.current) return;
    const serializer = new XMLSerializer();
    const source = serializer.serializeToString(svgRef.current);
    const svgBlob = new Blob([source], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(svgBlob);
    const downloadLink = document.createElement("a");
    downloadLink.href = url;
    downloadLink.download = `monorepo-graph-${Date.now()}.svg`;
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
  };

  const selectedNode = parsedPackages.find((n) => n.id === selectedNodeId);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="bg-surface-low dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl p-6 shadow-card flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="bg-primary text-black text-xs font-black px-2.5 py-1 rounded-md border border-black uppercase tracking-wider flex items-center gap-1">
              <Boxes className="w-3.5 h-3.5" /> Workspace Tools
            </span>
            <span className="bg-accent/20 text-accent text-xs font-bold px-2.5 py-1 rounded-md border border-accent/40">
              Atelier Studio
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-black text-text dark:text-[#f0ebe2] flex items-center gap-2">
            Monorepo Workspace Dependency Graph Visualizer
          </h1>
          <p className="mt-1 text-sm font-bold text-muted dark:text-[#c4bbae] max-w-2xl">
            Parse monorepo workspace manifests (`package.json`, Turborepo,
            Pnpm), visualize internal package relationships in 2D, and detect
            circular dependency loops.
          </p>
        </div>

        {/* Circular Dependency Status Badge */}
        <div className="flex items-center gap-3 bg-white dark:bg-[#1f1c18] border-2 border-black dark:border-[#2e2924] p-3 rounded-xl shadow-card-sm self-start md:self-auto">
          <div
            className={`p-2.5 rounded-lg border border-black font-black ${
              circularCycles.length > 0
                ? "bg-rose-500 text-white animate-bounce"
                : "bg-emerald-400 text-black"
            }`}
          >
            {circularCycles.length > 0 ? (
              <AlertTriangle className="w-6 h-6" />
            ) : (
              <CheckCircle2 className="w-6 h-6" />
            )}
          </div>
          <div>
            <div className="text-xs font-black uppercase text-muted tracking-wider">
              Health Status
            </div>
            <div className="text-sm font-black text-text dark:text-[#f0ebe2]">
              {circularCycles.length > 0
                ? `${circularCycles.length} Circular Loop(s)`
                : "Clean Architecture"}
            </div>
          </div>
        </div>
      </div>

      {/* Circular Dependency Warning Alert */}
      <AnimatePresence>
        {circularCycles.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="bg-rose-500/10 border-4 border-rose-500 rounded-2xl p-4 flex items-start gap-3 shadow-card"
          >
            <ShieldAlert className="w-6 h-6 text-rose-500 shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="text-sm font-black text-rose-600 dark:text-rose-400 uppercase tracking-wider">
                Circular Dependency Loop Detected!
              </h3>
              <p className="text-xs font-bold text-text dark:text-[#f0ebe2] mt-1">
                The internal package dependencies contain a circular reference
                loop which causes infinite build recursion in Turborepo / Lerna.
              </p>
              <div className="mt-2 space-y-1">
                {circularCycles.map((cycle, idx) => (
                  <div
                    key={idx}
                    className="font-mono text-xs bg-rose-500/20 text-rose-700 dark:text-rose-300 p-2 rounded-lg border border-rose-500/40 font-black flex items-center gap-1 overflow-x-auto"
                  >
                    <span>Loop #{idx + 1}:</span>
                    {cycle.map((node, nIdx) => (
                      <React.Fragment key={nIdx}>
                        <span className="bg-black/10 dark:bg-white/10 px-1.5 py-0.5 rounded">
                          {node}
                        </span>
                        {nIdx < cycle.length - 1 && (
                          <ArrowRight className="w-3 h-3 shrink-0" />
                        )}
                      </React.Fragment>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Container: Graph Visualizer & Code Manifest Editor */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: 2D Graph Visualizer Canvas (8 cols) */}
        <div className="lg:col-span-8 space-y-6 flex flex-col">
          <div className="bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-2xl shadow-card p-5 flex-1 flex flex-col min-h-[550px]">
            {/* Toolbar Controls */}
            <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b-2 border-black/10 dark:border-[#2e2924] mb-4">
              {/* Presets & Tabs */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setActiveTab("graph")}
                  className={`px-3 py-1.5 rounded-lg font-black text-xs transition-all flex items-center gap-1.5 border-2 ${
                    activeTab === "graph"
                      ? "bg-primary text-black border-black shadow-card-sm"
                      : "bg-surface-low dark:bg-[#151411] text-muted border-black/20 dark:border-[#2e2924]"
                  }`}
                >
                  <Boxes className="w-4 h-4" /> 2D Graph View
                </button>
                <button
                  onClick={() => setActiveTab("editor")}
                  className={`px-3 py-1.5 rounded-lg font-black text-xs transition-all flex items-center gap-1.5 border-2 ${
                    activeTab === "editor"
                      ? "bg-primary text-black border-black shadow-card-sm"
                      : "bg-surface-low dark:bg-[#151411] text-muted border-black/20 dark:border-[#2e2924]"
                  }`}
                >
                  <FileCode className="w-4 h-4" /> Workspace Manifest Editor
                </button>
              </div>

              {/* Presets Dropdown */}
              <div className="flex items-center gap-2">
                <span className="text-xs font-black text-muted hidden sm:inline">
                  Presets:
                </span>
                <select
                  value={activePreset.id}
                  onChange={(e) => {
                    const found = PRESET_CONFIGS.find(
                      (p) => p.id === e.target.value,
                    );
                    if (found) handlePresetSelect(found);
                  }}
                  className="bg-surface-low dark:bg-[#12110e] border-2 border-black dark:border-[#2e2924] rounded-xl px-2.5 py-1.5 text-xs font-bold text-text dark:text-[#f0ebe2] focus:outline-none"
                >
                  {PRESET_CONFIGS.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>

                <button
                  onClick={handleExportSvg}
                  className="p-1.5 rounded-lg border-2 border-black dark:border-[#2e2924] bg-surface dark:bg-[#151411] hover:bg-black/5 dark:hover:bg-white/5 transition-all text-text dark:text-[#f0ebe2]"
                  title="Export SVG Graph"
                >
                  <Download className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* TAB 1: 2D Graph Interactive SVG Canvas */}
            {activeTab === "graph" && (
              <div className="relative flex-1 bg-surface-low dark:bg-[#12110e] border-2 border-black/20 dark:border-[#2e2924] rounded-xl overflow-hidden p-4 flex flex-col justify-center items-center">
                {/* Search, Dropdown & Reset Filter Floating Overlay Bar */}
                <div className="absolute top-3 left-3 right-3 z-10 flex flex-wrap items-center justify-between gap-2 pointer-events-none">
                  <div className="flex items-center gap-2 pointer-events-auto max-w-md w-full">
                    {/* Search Input */}
                    <div className="relative flex-1">
                      <Search className="w-4 h-4 absolute left-3 top-2.5 text-muted" />
                      <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Filter packages by workspace name..."
                        className="pl-9 pr-7 py-1.5 bg-white dark:bg-[#1f1c18] border-2 border-black dark:border-[#2e2924] rounded-xl text-xs font-bold shadow-card-sm text-text dark:text-[#f0ebe2] focus:outline-none w-full"
                      />
                      {searchQuery && (
                        <button
                          onClick={() => setSearchQuery("")}
                          className="absolute right-2.5 top-2 text-slate-400 hover:text-black dark:hover:text-white"
                          title="Clear input"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>

                    {/* Interactive Search Dropdown Menu */}
                    <select
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      aria-label="Filter packages by workspace name"
                      className="bg-white dark:bg-[#1f1c18] border-2 border-black dark:border-[#2e2924] rounded-xl px-2.5 py-1.5 text-xs font-bold text-text dark:text-[#f0ebe2] focus:outline-none shadow-card-sm cursor-pointer max-w-[170px] truncate"
                    >
                      <option value="">-- Select Package --</option>
                      {parsedPackages.map((p) => (
                        <option key={p.id} value={p.name}>
                          {p.name}
                        </option>
                      ))}
                    </select>

                    {/* Reset Filter Button */}
                    {searchQuery && (
                      <button
                        onClick={() => {
                          setSearchQuery("");
                          setSelectedNodeId(null);
                        }}
                        aria-label="Reset Filter"
                        className="px-2.5 py-1.5 bg-rose-500 hover:bg-rose-600 text-white font-black text-xs rounded-xl border-2 border-black shadow-card-sm transition-all shrink-0 flex items-center gap-1"
                        title="Reset graph filter"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                        <span>Reset</span>
                      </button>
                    )}
                  </div>

                  <div className="flex items-center gap-1 bg-white dark:bg-[#1f1c18] border-2 border-black dark:border-[#2e2924] rounded-xl p-1 shadow-card-sm pointer-events-auto">
                    <button
                      onClick={() =>
                        setZoomLevel((z) => Math.min(z + 0.15, 1.6))
                      }
                      className="p-1 hover:bg-black/10 dark:hover:bg-white/10 rounded text-text dark:text-[#f0ebe2]"
                    >
                      <ZoomIn className="w-4 h-4" />
                    </button>
                    <span className="text-[10px] font-mono font-bold px-1">
                      {Math.round(zoomLevel * 100)}%
                    </span>
                    <button
                      onClick={() =>
                        setZoomLevel((z) => Math.max(z - 0.15, 0.6))
                      }
                      className="p-1 hover:bg-black/10 dark:hover:bg-white/10 rounded text-text dark:text-[#f0ebe2]"
                    >
                      <ZoomOut className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* SVG Graph Viewport */}
                {parseError ? (
                  <div className="p-8 text-center text-rose-500 font-bold text-xs space-y-2">
                    <AlertTriangle className="w-8 h-8 mx-auto" />
                    <p>{parseError}</p>
                  </div>
                ) : (
                  <div className="w-full h-[450px] relative overflow-hidden flex items-center justify-center">
                    <svg
                      ref={svgRef}
                      className="w-full h-full min-w-[650px] min-h-[420px] transition-transform duration-300"
                      viewBox="0 0 700 480"
                      style={{ transform: `scale(${zoomLevel})` }}
                    >
                      <defs>
                        <marker
                          id="arrow"
                          viewBox="0 0 10 10"
                          refX="22"
                          refY="5"
                          markerWidth="6"
                          markerHeight="6"
                          orient="auto-start-reverse"
                        >
                          <path d="M 0 0 L 10 5 L 0 10 z" fill="#6b7280" />
                        </marker>
                        <marker
                          id="arrow-circular"
                          viewBox="0 0 10 10"
                          refX="22"
                          refY="5"
                          markerWidth="7"
                          markerHeight="7"
                          orient="auto-start-reverse"
                        >
                          <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
                        </marker>
                      </defs>

                      {/* Render Dependency Edges */}
                      {parsedPackages.map((sourceNode) =>
                        sourceNode.dependencies.map((depName) => {
                          const targetNode = parsedPackages.find(
                            (n) => n.id === depName,
                          );
                          if (!targetNode) return null;

                          const isLoop = isCircularEdge(
                            sourceNode.id,
                            targetNode.id,
                          );

                          const isEdgeHighlighted =
                            !highlightedNodeIds ||
                            (highlightedNodeIds.has(sourceNode.id) &&
                              highlightedNodeIds.has(targetNode.id));

                          return (
                            <line
                              key={`${sourceNode.id}->${targetNode.id}`}
                              x1={sourceNode.x}
                              y1={sourceNode.y}
                              x2={targetNode.x}
                              y2={targetNode.y}
                              stroke={isLoop ? "#ef4444" : "#9ca3af"}
                              strokeWidth={isLoop ? 3.5 : isEdgeHighlighted ? 2.2 : 1.2}
                              strokeDasharray={isLoop ? "6,4" : "none"}
                              opacity={isEdgeHighlighted ? 1 : 0.15}
                              markerEnd={
                                isLoop ? "url(#arrow-circular)" : "url(#arrow)"
                              }
                            />
                          );
                        }),
                      )}

                      {/* Render Package Nodes */}
                      {parsedPackages.map((node) => {
                        const isSelected = selectedNodeId === node.id;
                        const isInLoop = circularCycles.some((c) =>
                          c.includes(node.id),
                        );
                        const isNodeHighlighted =
                          !highlightedNodeIds || highlightedNodeIds.has(node.id);
                        const isTargetMatch =
                          searchQuery.trim() &&
                          node.name
                            .toLowerCase()
                            .includes(searchQuery.trim().toLowerCase());

                        return (
                          <g
                            key={node.id}
                            transform={`translate(${node.x}, ${node.y})`}
                            className="cursor-pointer transition-transform hover:scale-110"
                            opacity={isNodeHighlighted ? 1 : 0.2}
                            onClick={() => setSelectedNodeId(node.id)}
                          >
                            <rect
                              x="-65"
                              y="-22"
                              width="130"
                              height="44"
                              rx="10"
                              fill={
                                isInLoop
                                  ? "#fee2e2"
                                  : node.type === "app"
                                    ? "#fef08a"
                                    : node.type === "service"
                                      ? "#e0e7ff"
                                      : "#ffffff"
                              }
                              stroke={
                                isInLoop
                                  ? "#ef4444"
                                  : isTargetMatch
                                    ? "#3b82f6"
                                    : isSelected
                                      ? "#3b82f6"
                                      : "#000"
                              }
                              strokeWidth={
                                isTargetMatch
                                  ? 4
                                  : isSelected
                                    ? 3.5
                                    : isInLoop
                                      ? 2.5
                                      : 2
                              }
                            />
                            <text
                              x="0"
                              y="-4"
                              textAnchor="middle"
                              fontWeight="800"
                              fontSize="11"
                              fill="#111827"
                            >
                              {node.name.length > 16
                                ? node.name.substring(0, 14) + ".."
                                : node.name}
                            </text>
                            <text
                              x="0"
                              y="12"
                              textAnchor="middle"
                              fontWeight="700"
                              fontSize="9"
                              fill={isInLoop ? "#dc2626" : "#6b7280"}
                            >
                              v{node.version} • {node.type}
                            </text>
                          </g>
                        );
                      })}
                    </svg>
                  </div>
                )}

                {/* Graph Legend Footer */}
                <div className="w-full pt-3 border-t border-black/10 dark:border-[#2e2924] flex flex-wrap items-center justify-between text-[11px] font-bold text-muted gap-2">
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1">
                      <span className="w-2.5 h-2.5 rounded-full bg-yellow-400 border border-black inline-block" />{" "}
                      App
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2.5 h-2.5 rounded-full bg-indigo-300 border border-black inline-block" />{" "}
                      Service
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2.5 h-2.5 rounded-full bg-white border border-black inline-block" />{" "}
                      Package
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block" />{" "}
                      Circular Edge
                    </span>
                  </div>
                  <span>Click node to view dependency details</span>
                </div>
              </div>
            )}

            {/* TAB 2: Config Manifest JSON Code Editor */}
            {activeTab === "editor" && (
              <div className="flex-1 bg-[#1e1e1e] text-emerald-400 font-mono text-xs p-4 rounded-xl border-2 border-black overflow-hidden flex flex-col">
                <div className="text-gray-400 pb-2 border-b border-gray-700 mb-2 font-bold flex items-center justify-between">
                  <span>📄 package.json / pnpm-workspace.yaml Manifest</span>
                  <span className="text-[10px] text-gray-500">
                    Edit JSON to update live graph
                  </span>
                </div>
                <textarea
                  value={jsonInput}
                  onChange={(e) => setJsonInput(e.target.value)}
                  className="w-full flex-1 bg-transparent text-emerald-400 font-mono text-xs focus:outline-none resize-none leading-relaxed"
                />
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Node Inspector & Monorepo Analytics (4 cols) */}
        <div className="lg:col-span-4 space-y-6 flex flex-col">
          {/* Node Details Inspector */}
          <div className="bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-2xl shadow-card p-5">
            <h2 className="text-lg font-black text-text dark:text-[#f0ebe2] pb-3 border-b-2 border-black/10 dark:border-[#2e2924] mb-4 flex items-center gap-2">
              <Sliders className="w-5 h-5 text-primary" /> Package Inspector
            </h2>

            {selectedNode ? (
              <div className="space-y-4">
                <div className="bg-surface-low dark:bg-[#151411] border-2 border-black dark:border-[#2e2924] rounded-xl p-3">
                  <div className="font-mono text-sm font-black text-text dark:text-[#f0ebe2]">
                    {selectedNode.name}
                  </div>
                  <div className="text-xs font-bold text-muted mt-0.5">
                    Type:{" "}
                    <span className="uppercase text-primary">
                      {selectedNode.type}
                    </span>{" "}
                    • Version: v{selectedNode.version}
                  </div>
                </div>

                {/* Direct Dependencies List */}
                <div>
                  <div className="text-xs font-black uppercase text-muted tracking-wider mb-2">
                    Internal Dependencies ({selectedNode.dependencies.length})
                  </div>
                  {selectedNode.dependencies.length === 0 ? (
                    <div className="text-xs font-bold text-muted italic">
                      No internal monorepo dependencies.
                    </div>
                  ) : (
                    <div className="space-y-1.5">
                      {selectedNode.dependencies.map((dep) => (
                        <div
                          key={dep}
                          onClick={() => setSelectedNodeId(dep)}
                          className="p-2 rounded-lg border-2 border-black/10 dark:border-[#2e2924] bg-surface dark:bg-[#12110e] text-xs font-mono font-bold flex items-center justify-between cursor-pointer hover:border-black transition-all"
                        >
                          <span className="text-text dark:text-[#f0ebe2]">
                            {dep}
                          </span>
                          <ArrowRight className="w-3.5 h-3.5 text-muted" />
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Reverse Dependents (Which packages depend on this) */}
                <div>
                  <div className="text-xs font-black uppercase text-muted tracking-wider mb-2">
                    Required By (Dependents)
                  </div>
                  {parsedPackages.filter((p) =>
                    p.dependencies.includes(selectedNode.id),
                  ).length === 0 ? (
                    <div className="text-xs font-bold text-muted italic">
                      Top-level root package (not imported).
                    </div>
                  ) : (
                    <div className="space-y-1.5">
                      {parsedPackages
                        .filter((p) => p.dependencies.includes(selectedNode.id))
                        .map((dep) => (
                          <div
                            key={dep.id}
                            onClick={() => setSelectedNodeId(dep.id)}
                            className="p-2 rounded-lg border-2 border-black/10 dark:border-[#2e2924] bg-surface dark:bg-[#12110e] text-xs font-mono font-bold flex items-center justify-between cursor-pointer hover:border-black transition-all"
                          >
                            <span className="text-text dark:text-[#f0ebe2]">
                              {dep.name}
                            </span>
                            <ArrowRight className="w-3.5 h-3.5 text-muted" />
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-6 text-center border-2 border-dashed border-black/20 dark:border-[#2e2924] rounded-xl text-muted text-xs font-bold">
                Select a package node from the 2D graph to inspect its
                dependency linkage.
              </div>
            )}
          </div>

          {/* Monorepo Health Summary Stats Card */}
          <div className="bg-surface-low dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl shadow-card p-5 space-y-3">
            <h3 className="text-xs font-black uppercase tracking-wider text-muted">
              Workspace Overview
            </h3>
            <div className="grid grid-cols-2 gap-3 text-center">
              <div className="bg-white dark:bg-[#1f1c18] border-2 border-black dark:border-[#2e2924] p-3 rounded-xl">
                <div className="text-2xl font-black text-text dark:text-[#f0ebe2]">
                  {parsedPackages.length}
                </div>
                <div className="text-[10px] font-bold text-muted uppercase">
                  Packages
                </div>
              </div>
              <div className="bg-white dark:bg-[#1f1c18] border-2 border-black dark:border-[#2e2924] p-3 rounded-xl">
                <div className="text-2xl font-black text-text dark:text-[#f0ebe2]">
                  {parsedPackages.reduce(
                    (acc, p) => acc + p.dependencies.length,
                    0,
                  )}
                </div>
                <div className="text-[10px] font-bold text-muted uppercase">
                  Edges (Linkages)
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MonorepoDependencyGraph;
