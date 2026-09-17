import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Terminal,
  GitBranch,
  GitCommit,
  FolderTree,
  CheckCircle2,
  AlertCircle,
  Play,
  RotateCcw,
  Sparkles,
  HelpCircle,
  FileCode,
  ExternalLink,
  Layers,
  ArrowRight,
  ShieldCheck,
  Zap,
} from "lucide-react";

export interface SubmoduleNode {
  id: string;
  name: string;
  path: string;
  url: string;
  commitHash: string;
  remoteHash: string;
  branch: string;
  status:
    | "uninitialized"
    | "clean"
    | "detached_head"
    | "ahead_behind"
    | "modified";
  initialized: boolean;
  parentId?: string;
  children?: SubmoduleNode[];
}

export interface Exercise {
  id: number;
  title: string;
  description: string;
  hint: string;
  requiredCmdPrefix: string;
  targetSubmodule?: string;
  completed: boolean;
  xp: number;
}

const INITIAL_TREE: SubmoduleNode = {
  id: "root",
  name: "parent-app",
  path: "/",
  url: "https://github.com/atelier/parent-app.git",
  commitHash: "c3a1f49",
  remoteHash: "c3a1f49",
  branch: "main",
  status: "clean",
  initialized: true,
  children: [
    {
      id: "auth-sdk",
      name: "auth-sdk",
      path: "services/auth-sdk",
      url: "https://github.com/atelier/auth-sdk.git",
      commitHash: "8f2a10b",
      remoteHash: "9e4b78c",
      branch: "v2.1.0",
      status: "uninitialized",
      initialized: false,
      parentId: "root",
    },
    {
      id: "ui-components",
      name: "ui-components",
      path: "libs/ui-components",
      url: "https://github.com/atelier/ui-components.git",
      commitHash: "4d7e91a",
      remoteHash: "4d7e91a",
      branch: "main",
      status: "uninitialized",
      initialized: false,
      parentId: "root",
      children: [
        {
          id: "icons-pack",
          name: "icons-pack",
          path: "libs/ui-components/icons",
          url: "https://github.com/atelier/icons-pack.git",
          commitHash: "1b3f5e9",
          remoteHash: "2c4a6b8",
          branch: "main",
          status: "uninitialized",
          initialized: false,
          parentId: "ui-components",
        },
      ],
    },
  ],
};

const INITIAL_EXERCISES: Exercise[] = [
  {
    id: 1,
    title: "Add a Submodule",
    description: "Add a new core utility submodule at path `libs/core-utils`.",
    hint: "Type: git submodule add https://github.com/atelier/core-utils.git libs/core-utils",
    requiredCmdPrefix: "git submodule add",
    targetSubmodule: "libs/core-utils",
    completed: false,
    xp: 50,
  },
  {
    id: 2,
    title: "Initialize Registered Submodules",
    description:
      "Initialize the submodules recorded in your `.gitmodules` file.",
    hint: "Type: git submodule init",
    requiredCmdPrefix: "git submodule init",
    completed: false,
    xp: 50,
  },
  {
    id: 3,
    title: "Update & Fetch Submodule Contents",
    description:
      "Fetch and checkout the commits specified in the parent repository.",
    hint: "Type: git submodule update",
    requiredCmdPrefix: "git submodule update",
    completed: false,
    xp: 75,
  },
  {
    id: 4,
    title: "Sync with Upstream Remote",
    description: "Update all submodules to their latest remote HEAD commit.",
    hint: "Type: git submodule update --remote",
    requiredCmdPrefix: "git submodule update --remote",
    completed: false,
    xp: 100,
  },
  {
    id: 5,
    title: "Perform a Recursive Clone",
    description:
      "Simulate cloning a project along with all nested submodules in one step.",
    hint: "Type: git clone --recursive https://github.com/atelier/parent-app.git",
    requiredCmdPrefix: "git clone --recursive",
    completed: false,
    xp: 125,
  },
];

export function GitSubmoduleSimulator() {
  const [tree, setTree] = useState<SubmoduleNode>(INITIAL_TREE);
  const [terminalInput, setTerminalInput] = useState("");
  const [terminalLogs, setTerminalLogs] = useState<string[]>([
    "🖥️  Git Submodule Interactive Terminal & Visualizer v1.0",
    "Type 'help' for available commands or follow the guided exercise tasks below.",
    "--------------------------------------------------------------------------------",
  ]);
  const [selectedNode, setSelectedNode] = useState<SubmoduleNode | null>(
    INITIAL_TREE,
  );
  const [activeTab, setActiveTab] = useState<"tree" | "gitmodules">("tree");
  const [exercises, setExercises] = useState<Exercise[]>(INITIAL_EXERCISES);
  const [currentExerciseIdx, setCurrentExerciseIdx] = useState(0);
  const [totalXP, setTotalXP] = useState(0);
  const [showCelebration, setShowCelebration] = useState(false);

  const addLog = (text: string) => {
    setTerminalLogs((prev) => [...prev, text]);
  };

  // Helper to traverse and update nodes recursively
  const updateNodeRecursively = (
    current: SubmoduleNode,
    updater: (node: SubmoduleNode) => SubmoduleNode,
  ): SubmoduleNode => {
    const updatedCurrent = updater(current);
    if (updatedCurrent.children) {
      return {
        ...updatedCurrent,
        children: updatedCurrent.children.map((child) =>
          updateNodeRecursively(child, updater),
        ),
      };
    }
    return updatedCurrent;
  };

  // Execute Simulated Commands
  const handleCommand = (e: React.FormEvent) => {
    e.preventDefault();
    const cmd = terminalInput.trim();
    if (!cmd) return;

    addLog(`$ ${cmd}`);
    setTerminalInput("");

    const parts = cmd.split(" ").filter(Boolean);
    const mainCmd = parts[0]?.toLowerCase();

    if (cmd === "clear") {
      setTerminalLogs([]);
      return;
    }

    if (cmd === "help") {
      addLog("💡 Available Git Submodule Commands:");
      addLog(
        "  git submodule add <url> [path]   - Add a repository as a submodule",
      );
      addLog(
        "  git submodule init [path]        - Initialize submodules in .git/config",
      );
      addLog(
        "  git submodule update [--remote]  - Fetch & checkout submodules",
      );
      addLog(
        "  git submodule status             - View status & HEAD commit hashes",
      );
      addLog(
        "  git clone --recursive <url>      - Clone repo and all submodules recursively",
      );
      addLog(
        "  git status                       - View parent repository status",
      );
      addLog(
        "  reset                            - Reset simulator to initial state",
      );
      addLog("  clear                            - Clear terminal screen");
      return;
    }

    if (cmd === "reset") {
      setTree(INITIAL_TREE);
      setSelectedNode(INITIAL_TREE);
      setExercises(INITIAL_EXERCISES);
      setCurrentExerciseIdx(0);
      setTotalXP(0);
      addLog("🔄 Simulator reset to initial state.");
      return;
    }

    if (mainCmd === "git") {
      const subCmd = parts[1]?.toLowerCase();

      if (subCmd === "status") {
        addLog("On branch main");
        addLog("Your branch is up to date with 'origin/main'.");
        addLog("");
        addLog("Submodules configuration:");
        let uninitCount = 0;
        let cleanCount = 0;

        const checkStatus = (n: SubmoduleNode) => {
          if (n.id !== "root") {
            if (!n.initialized) uninitCount++;
            else cleanCount++;
          }
          n.children?.forEach(checkStatus);
        };
        checkStatus(tree);

        addLog(`  Initialized submodules: ${cleanCount}`);
        addLog(`  Uninitialized submodules: ${uninitCount}`);
        if (uninitCount > 0) {
          addLog(
            "  (use 'git submodule init' and 'git submodule update' to fetch them)",
          );
        }
      } else if (subCmd === "submodule") {
        const action = parts[2]?.toLowerCase();

        if (action === "status") {
          addLog("Submodule status summary:");
          const printStatus = (node: SubmoduleNode, prefix = " ") => {
            if (node.id !== "root") {
              const symbol = !node.initialized
                ? "-"
                : node.status === "detached_head"
                  ? "+"
                  : " ";
              addLog(
                `${symbol}${node.commitHash} ${node.path} (${node.branch})`,
              );
            }
            node.children?.forEach((child) =>
              printStatus(child, prefix + "  "),
            );
          };
          printStatus(tree);
        } else if (action === "add") {
          const url = parts[3];
          const path =
            parts[4] ||
            (url
              ? url.split("/").pop()?.replace(".git", "")
              : "libs/new-module");

          if (!url) {
            addLog(
              "❌ Error: Missing repository URL. Usage: git submodule add <url> [path]",
            );
            return;
          }

          const newSubmodule: SubmoduleNode = {
            id: `submodule-${Date.now()}`,
            name: path.split("/").pop() || "new-module",
            path: path,
            url: url,
            commitHash: "e5f6a7b",
            remoteHash: "e5f6a7b",
            branch: "main",
            status: "clean",
            initialized: true,
            parentId: "root",
          };

          setTree((prev) => ({
            ...prev,
            children: [...(prev.children || []), newSubmodule],
          }));

          addLog(`Cloning into '${path}'...`);
          addLog(`done.`);
          addLog(`✅ Added submodule '${path}' (${url}) to .gitmodules`);
          checkExerciseCompletion("git submodule add", path);
        } else if (action === "init") {
          setTree((prev) =>
            updateNodeRecursively(prev, (node) => {
              if (node.id !== "root") {
                return { ...node, initialized: true, status: "detached_head" };
              }
              return node;
            }),
          );
          addLog("Submodule register success:");
          const logInits = (n: SubmoduleNode) => {
            if (n.id !== "root") {
              addLog(
                `Submodule '${n.name}' (${n.url}) registered for path '${n.path}'`,
              );
            }
            n.children?.forEach(logInits);
          };
          logInits(tree);
          addLog(
            "✅ Registered submodules in .git/config. Next run 'git submodule update'.",
          );
          checkExerciseCompletion("git submodule init");
        } else if (action === "update") {
          const isRemote = parts.includes("--remote");
          const isRecursive = parts.includes("--recursive");

          setTree((prev) =>
            updateNodeRecursively(prev, (node) => {
              if (node.id !== "root") {
                const newCommit = isRemote ? node.remoteHash : node.commitHash;
                return {
                  ...node,
                  initialized: true,
                  commitHash: newCommit,
                  status: isRemote ? "clean" : "clean",
                };
              }
              return node;
            }),
          );

          if (isRemote) {
            addLog("Submodule remote update:");
            addLog("Fetching origin...");
            addLog("✅ Updated all submodules to latest remote HEAD pointers.");
            checkExerciseCompletion("git submodule update --remote");
          } else {
            addLog("Submodule checkout complete:");
            addLog(
              "Submodules checked out to commit hashes listed in parent repository.",
            );
            checkExerciseCompletion("git submodule update");
          }
        } else {
          addLog(
            `❌ Unknown submodule action '${action}'. Try 'add', 'init', 'update', or 'status'.`,
          );
        }
      } else if (subCmd === "clone" && parts.includes("--recursive")) {
        const url = parts[parts.length - 1];
        setTree((prev) =>
          updateNodeRecursively(prev, (node) => {
            if (node.id !== "root") {
              return {
                ...node,
                initialized: true,
                status: "clean",
                commitHash: node.remoteHash,
              };
            }
            return node;
          }),
        );
        addLog(`Cloning into 'parent-app' from ${url}...`);
        addLog("Submodule 'services/auth-sdk' registered and cloned.");
        addLog("Submodule 'libs/ui-components' registered and cloned.");
        addLog(
          "Submodule 'libs/ui-components/icons' (nested) registered and cloned.",
        );
        addLog(
          "✅ Recursive clone complete! Parent and all submodules are fully initialized.",
        );
        checkExerciseCompletion("git clone --recursive");
      } else {
        addLog(
          `❌ Command not recognized: '${cmd}'. Type 'help' for command list.`,
        );
      }
    } else {
      addLog(
        `❌ Command not recognized: '${cmd}'. Type 'help' for command list.`,
      );
    }
  };

  // Check exercise completion
  const checkExerciseCompletion = (cmdPrefix: string, arg?: string) => {
    const currentEx = exercises[currentExerciseIdx];
    if (!currentEx || currentEx.completed) return;

    if (
      cmdPrefix
        .toLowerCase()
        .startsWith(currentEx.requiredCmdPrefix.toLowerCase())
    ) {
      const updatedExs = [...exercises];
      updatedExs[currentExerciseIdx].completed = true;
      setExercises(updatedExs);
      setTotalXP((prev) => prev + currentEx.xp);

      addLog(
        `🎉 EXERCISE COMPLETE! +${currentEx.xp} XP unlocked: "${currentEx.title}"`,
      );

      if (currentExerciseIdx + 1 < exercises.length) {
        setCurrentExerciseIdx((prev) => prev + 1);
      } else {
        setShowCelebration(true);
      }
    }
  };

  // Helper to extract .gitmodules text
  const generateGitModulesText = (node: SubmoduleNode): string => {
    const lines: string[] = [];
    const traverse = (n: SubmoduleNode) => {
      if (n.id !== "root") {
        lines.push(`[submodule "${n.path}"]`);
        lines.push(`\tpath = ${n.path}`);
        lines.push(`\turl = ${n.url}`);
        lines.push(`\tbranch = ${n.branch}`);
        lines.push("");
      }
      n.children?.forEach(traverse);
    };
    traverse(node);
    return lines.length
      ? lines.join("\n")
      : "# No submodules registered yet.\n# Use 'git submodule add <url> <path>' to register one.";
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="bg-surface-low dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl p-6 shadow-card flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="bg-primary text-black text-xs font-black px-2.5 py-1 rounded-md border border-black uppercase tracking-wider flex items-center gap-1">
              <FolderTree className="w-3.5 h-3.5" /> Interactive Sandbox
            </span>
            <span className="bg-accent/20 text-accent text-xs font-bold px-2.5 py-1 rounded-md border border-accent/40">
              Atelier Studio
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-black text-text dark:text-[#f0ebe2] flex items-center gap-2">
            Git Submodule Manager & Visual Tree Simulator
          </h1>
          <p className="mt-1 text-sm font-bold text-muted dark:text-[#c4bbae] max-w-2xl">
            Master multi-repository Git architectures. Practice adding,
            updating, initializing, and recursively cloning nested submodules
            with real-time SVG tree feedback.
          </p>
        </div>

        {/* XP Badge */}
        <div className="flex items-center gap-3 bg-white dark:bg-[#1f1c18] border-2 border-black dark:border-[#2e2924] p-3 rounded-xl shadow-card-sm self-start md:self-auto">
          <div className="bg-yellow-400 p-2.5 rounded-lg border border-black text-black">
            <Sparkles className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <div className="text-xs font-black uppercase text-muted tracking-wider">
              Skill XP
            </div>
            <div className="text-xl font-black text-text dark:text-[#f0ebe2]">
              {totalXP} XP
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid: Tree / Visualizer & Exercises / Terminal */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Visual SVG Graph & Gitmodules Editor (7 cols) */}
        <div className="lg:col-span-7 space-y-6 flex flex-col">
          {/* Visual Graph Header Controls */}
          <div className="bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-2xl shadow-card p-4 flex-1 flex flex-col min-h-[480px]">
            <div className="flex items-center justify-between pb-3 border-b-2 border-black/10 dark:border-[#2e2924] mb-4">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setActiveTab("tree")}
                  className={`px-3 py-1.5 rounded-lg font-black text-xs transition-all flex items-center gap-1.5 border-2 ${
                    activeTab === "tree"
                      ? "bg-primary text-black border-black shadow-card-sm"
                      : "bg-surface-low dark:bg-[#151411] text-muted border-black/20 dark:border-[#2e2924]"
                  }`}
                >
                  <Layers className="w-4 h-4" /> Live Submodule Graph
                </button>
                <button
                  onClick={() => setActiveTab("gitmodules")}
                  className={`px-3 py-1.5 rounded-lg font-black text-xs transition-all flex items-center gap-1.5 border-2 ${
                    activeTab === "gitmodules"
                      ? "bg-primary text-black border-black shadow-card-sm"
                      : "bg-surface-low dark:bg-[#151411] text-muted border-black/20 dark:border-[#2e2924]"
                  }`}
                >
                  <FileCode className="w-4 h-4" /> .gitmodules Preview
                </button>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-[11px] font-bold text-muted hidden sm:inline">
                  Click any node to inspect pointer
                </span>
                <button
                  onClick={() => {
                    setTree(INITIAL_TREE);
                    setSelectedNode(INITIAL_TREE);
                    addLog("🔄 Graph view refreshed.");
                  }}
                  className="p-1.5 rounded-lg border-2 border-black dark:border-[#2e2924] bg-surface dark:bg-[#151411] hover:bg-black/5 dark:hover:bg-white/5 transition-all text-text dark:text-[#f0ebe2]"
                  title="Reset Submodule Tree"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* TAB 1: SVG Graph Render */}
            {activeTab === "tree" && (
              <div className="relative flex-1 bg-surface-low dark:bg-[#12110e] border-2 border-black/20 dark:border-[#2e2924] rounded-xl overflow-hidden p-4 flex flex-col justify-center items-center">
                {/* SVG Visual Canvas */}
                <div className="w-full h-[380px] relative overflow-auto flex items-center justify-center">
                  <svg
                    className="w-full h-full min-w-[500px] min-h-[350px]"
                    viewBox="0 0 700 350"
                  >
                    <defs>
                      <linearGradient
                        id="parentGrad"
                        x1="0%"
                        y1="0%"
                        x2="100%"
                        y2="100%"
                      >
                        <stop offset="0%" stopColor="#FFD700" />
                        <stop offset="100%" stopColor="#FFA500" />
                      </linearGradient>
                      <linearGradient
                        id="nodeGrad"
                        x1="0%"
                        y1="0%"
                        x2="100%"
                        y2="100%"
                      >
                        <stop offset="0%" stopColor="#ffffff" />
                        <stop offset="100%" stopColor="#f3f4f6" />
                      </linearGradient>
                    </defs>

                    {/* Connecting Bezier Edges */}
                    {/* Root to auth-sdk */}
                    <path
                      d="M 350 70 C 350 120, 180 120, 180 160"
                      fill="none"
                      stroke="#4b5563"
                      strokeWidth="3"
                      strokeDasharray={
                        tree.children?.[0]?.initialized ? "none" : "6,6"
                      }
                    />
                    {/* Root to ui-components */}
                    <path
                      d="M 350 70 C 350 120, 520 120, 520 160"
                      fill="none"
                      stroke="#4b5563"
                      strokeWidth="3"
                      strokeDasharray={
                        tree.children?.[1]?.initialized ? "none" : "6,6"
                      }
                    />
                    {/* ui-components to icons-pack */}
                    {tree.children?.[1]?.children?.[0] && (
                      <path
                        d="M 520 220 C 520 260, 520 260, 520 280"
                        fill="none"
                        stroke="#6b7280"
                        strokeWidth="2.5"
                        strokeDasharray={
                          tree.children[1].children[0].initialized
                            ? "none"
                            : "5,5"
                        }
                      />
                    )}

                    {/* ROOT NODE */}
                    <g
                      transform="translate(250, 20)"
                      className="cursor-pointer transition-transform hover:scale-105"
                      onClick={() => setSelectedNode(tree)}
                    >
                      <rect
                        width="200"
                        height="50"
                        rx="12"
                        fill="url(#parentGrad)"
                        stroke="#000"
                        strokeWidth="3"
                      />
                      <text
                        x="100"
                        y="24"
                        textAnchor="middle"
                        fontWeight="900"
                        fontSize="13"
                        fill="#000"
                      >
                        📦 parent-app (Root Repo)
                      </text>
                      <text
                        x="100"
                        y="40"
                        textAnchor="middle"
                        fontWeight="700"
                        fontSize="10"
                        fill="#333"
                      >
                        HEAD: {tree.commitHash} • main
                      </text>
                    </g>

                    {/* SUBMODULE 1: auth-sdk */}
                    {tree.children?.[0] && (
                      <g
                        transform="translate(80, 160)"
                        className="cursor-pointer transition-transform hover:scale-105"
                        onClick={() => setSelectedNode(tree.children![0])}
                      >
                        <rect
                          width="200"
                          height="60"
                          rx="10"
                          fill={
                            tree.children[0].initialized ? "#ffffff" : "#fef2f2"
                          }
                          stroke={
                            selectedNode?.id === tree.children[0].id
                              ? "#3b82f6"
                              : "#000"
                          }
                          strokeWidth={
                            selectedNode?.id === tree.children[0].id
                              ? "4"
                              : "2.5"
                          }
                        />
                        <text
                          x="15"
                          y="22"
                          fontWeight="800"
                          fontSize="12"
                          fill="#111827"
                        >
                          📁 {tree.children[0].name}
                        </text>
                        <text
                          x="15"
                          y="38"
                          fontWeight="600"
                          fontSize="10"
                          fill="#6b7280"
                        >
                          {tree.children[0].path}
                        </text>
                        <text
                          x="15"
                          y="52"
                          fontWeight="700"
                          fontSize="10"
                          fill="#3b82f6"
                        >
                          SHA: {tree.children[0].commitHash}
                        </text>
                        {/* Status Pill */}
                        <rect
                          x="125"
                          y="10"
                          width="65"
                          height="18"
                          rx="9"
                          fill={
                            !tree.children[0].initialized
                              ? "#ef4444"
                              : tree.children[0].status === "detached_head"
                                ? "#f59e0b"
                                : "#10b981"
                          }
                        />
                        <text
                          x="157"
                          y="22"
                          textAnchor="middle"
                          fontWeight="800"
                          fontSize="8"
                          fill="#fff"
                        >
                          {!tree.children[0].initialized
                            ? "UNINIT"
                            : tree.children[0].status.toUpperCase()}
                        </text>
                      </g>
                    )}

                    {/* SUBMODULE 2: ui-components */}
                    {tree.children?.[1] && (
                      <g
                        transform="translate(420, 160)"
                        className="cursor-pointer transition-transform hover:scale-105"
                        onClick={() => setSelectedNode(tree.children![1])}
                      >
                        <rect
                          width="200"
                          height="60"
                          rx="10"
                          fill={
                            tree.children[1].initialized ? "#ffffff" : "#fef2f2"
                          }
                          stroke={
                            selectedNode?.id === tree.children[1].id
                              ? "#3b82f6"
                              : "#000"
                          }
                          strokeWidth={
                            selectedNode?.id === tree.children[1].id
                              ? "4"
                              : "2.5"
                          }
                        />
                        <text
                          x="15"
                          y="22"
                          fontWeight="800"
                          fontSize="12"
                          fill="#111827"
                        >
                          📁 {tree.children[1].name}
                        </text>
                        <text
                          x="15"
                          y="38"
                          fontWeight="600"
                          fontSize="10"
                          fill="#6b7280"
                        >
                          {tree.children[1].path}
                        </text>
                        <text
                          x="15"
                          y="52"
                          fontWeight="700"
                          fontSize="10"
                          fill="#3b82f6"
                        >
                          SHA: {tree.children[1].commitHash}
                        </text>
                        {/* Status Pill */}
                        <rect
                          x="125"
                          y="10"
                          width="65"
                          height="18"
                          rx="9"
                          fill={
                            !tree.children[1].initialized
                              ? "#ef4444"
                              : tree.children[1].status === "detached_head"
                                ? "#f59e0b"
                                : "#10b981"
                          }
                        />
                        <text
                          x="157"
                          y="22"
                          textAnchor="middle"
                          fontWeight="800"
                          fontSize="8"
                          fill="#fff"
                        >
                          {!tree.children[1].initialized
                            ? "UNINIT"
                            : tree.children[1].status.toUpperCase()}
                        </text>
                      </g>
                    )}

                    {/* NESTED SUBMODULE: icons-pack */}
                    {tree.children?.[1]?.children?.[0] && (
                      <g
                        transform="translate(435, 275)"
                        className="cursor-pointer transition-transform hover:scale-105"
                        onClick={() =>
                          setSelectedNode(tree.children![1].children![0])
                        }
                      >
                        <rect
                          width="170"
                          height="50"
                          rx="8"
                          fill={
                            tree.children[1].children[0].initialized
                              ? "#f0fdf4"
                              : "#fff1f2"
                          }
                          stroke="#000"
                          strokeWidth="2"
                        />
                        <text
                          x="10"
                          y="20"
                          fontWeight="800"
                          fontSize="11"
                          fill="#111827"
                        >
                          ⚡ {tree.children[1].children[0].name} (Nested)
                        </text>
                        <text
                          x="10"
                          y="36"
                          fontWeight="700"
                          fontSize="9"
                          fill="#10b981"
                        >
                          SHA: {tree.children[1].children[0].commitHash}
                        </text>
                      </g>
                    )}
                  </svg>
                </div>

                {/* Graph Legend Footer */}
                <div className="w-full pt-2 border-t border-black/10 dark:border-[#2e2924] flex flex-wrap items-center justify-between text-[11px] font-bold text-muted gap-2">
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1">
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />{" "}
                      Clean / Synced
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" />{" "}
                      Detached HEAD
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block" />{" "}
                      Uninitialized
                    </span>
                  </div>
                  <span>Dashed Lines = Pointer Registered only</span>
                </div>
              </div>
            )}

            {/* TAB 2: .gitmodules File Preview */}
            {activeTab === "gitmodules" && (
              <div className="flex-1 bg-[#1e1e1e] text-emerald-400 font-mono text-xs p-4 rounded-xl border-2 border-black overflow-auto">
                <div className="text-gray-500 pb-2 border-b border-gray-700 mb-2 font-bold flex items-center justify-between">
                  <span>📄 .gitmodules Configuration File</span>
                  <span>Read-Only Preview</span>
                </div>
                <pre className="whitespace-pre-wrap">
                  {generateGitModulesText(tree)}
                </pre>
              </div>
            )}

            {/* Inspector Panel for Selected Node */}
            {selectedNode && (
              <div className="mt-4 bg-surface-low dark:bg-[#151411] border-2 border-black dark:border-[#2e2924] rounded-xl p-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
                <div>
                  <span className="font-black text-text dark:text-[#f0ebe2] block text-sm">
                    Selected Node: {selectedNode.name}
                  </span>
                  <span className="font-mono text-muted text-[11px]">
                    URL: {selectedNode.url} • Path: {selectedNode.path}
                  </span>
                </div>
                <div className="flex items-center gap-2 font-mono">
                  <span className="bg-black/10 dark:bg-white/10 px-2 py-1 rounded font-bold">
                    HEAD: {selectedNode.commitHash}
                  </span>
                  <span
                    className={`px-2 py-1 rounded font-black text-white ${
                      !selectedNode.initialized
                        ? "bg-rose-500"
                        : selectedNode.status === "detached_head"
                          ? "bg-amber-500"
                          : "bg-emerald-500"
                    }`}
                  >
                    {selectedNode.initialized
                      ? selectedNode.status.toUpperCase()
                      : "UNINITIALIZED"}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Guided Exercises & Simulated Terminal (5 cols) */}
        <div className="lg:col-span-5 space-y-6 flex flex-col">
          {/* Guided Exercises Card */}
          <div className="bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-2xl shadow-card p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-black text-text dark:text-[#f0ebe2] flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-primary" /> Guided
                Exercises
              </h2>
              <span className="text-xs font-bold text-muted">
                Step {currentExerciseIdx + 1} of {exercises.length}
              </span>
            </div>

            {/* Exercise Task Selector / Progress */}
            {exercises[currentExerciseIdx] && (
              <div className="bg-surface-low dark:bg-[#151411] border-2 border-black dark:border-[#2e2924] rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-black text-sm text-text dark:text-[#f0ebe2]">
                    {exercises[currentExerciseIdx].title}
                  </span>
                  <span className="bg-amber-400/20 text-amber-600 dark:text-amber-400 border border-amber-500/40 text-[10px] font-black px-2 py-0.5 rounded">
                    +{exercises[currentExerciseIdx].xp} XP
                  </span>
                </div>
                <p className="text-xs font-bold text-muted dark:text-[#c4bbae]">
                  {exercises[currentExerciseIdx].description}
                </p>
                <div className="bg-black/5 dark:bg-white/5 border border-black/10 dark:border-[#2e2924] rounded-lg p-2 font-mono text-[11px] text-primary dark:text-yellow-400">
                  {exercises[currentExerciseIdx].hint}
                </div>
              </div>
            )}

            {/* Checklist of all exercises */}
            <div className="mt-4 space-y-1.5">
              {exercises.map((ex, idx) => (
                <div
                  key={ex.id}
                  onClick={() => setCurrentExerciseIdx(idx)}
                  className={`flex items-center justify-between p-2 rounded-lg border-2 text-xs font-bold cursor-pointer transition-all ${
                    idx === currentExerciseIdx
                      ? "border-black bg-primary/20 text-text dark:text-[#f0ebe2]"
                      : ex.completed
                        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                        : "border-black/10 dark:border-[#2e2924] text-muted opacity-70"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {ex.completed ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                    ) : (
                      <span className="w-4 h-4 rounded-full border border-black/30 flex items-center justify-center text-[10px]">
                        {ex.id}
                      </span>
                    )}
                    <span>{ex.title}</span>
                  </div>
                  <span className="text-[10px] font-mono">+{ex.xp} XP</span>
                </div>
              ))}
            </div>
          </div>

          {/* Interactive Simulated Terminal */}
          <div className="bg-[#181818] border-4 border-black dark:border-[#2e2924] rounded-2xl shadow-card overflow-hidden flex-1 flex flex-col min-h-[320px]">
            <div className="bg-[#252526] px-4 py-2 flex items-center justify-between border-b border-black text-xs font-bold text-gray-300">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-emerald-400" />
                <span>Simulated Submodule CLI Terminal</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setTerminalLogs([])}
                  className="text-[10px] bg-black/40 hover:bg-black px-2 py-1 rounded text-gray-400 hover:text-white"
                >
                  Clear
                </button>
              </div>
            </div>

            {/* Logs Area */}
            <div className="flex-1 p-4 font-mono text-xs text-gray-200 overflow-y-auto space-y-1.5 max-h-[260px]">
              {terminalLogs.map((log, idx) => (
                <div
                  key={idx}
                  className={
                    log.startsWith("$")
                      ? "text-yellow-400 font-bold"
                      : log.includes("✅")
                        ? "text-emerald-400 font-semibold"
                        : log.includes("❌")
                          ? "text-rose-400"
                          : "text-gray-300"
                  }
                >
                  {log}
                </div>
              ))}
            </div>

            {/* Input Line */}
            <form
              onSubmit={handleCommand}
              className="p-3 bg-[#202020] border-t border-gray-800 flex items-center gap-2"
            >
              <span className="text-emerald-400 font-mono font-bold text-xs">
                $
              </span>
              <input
                type="text"
                value={terminalInput}
                onChange={(e) => setTerminalInput(e.target.value)}
                placeholder="e.g. git submodule add <url> [path] or help"
                className="flex-1 bg-transparent font-mono text-xs text-white focus:outline-none placeholder-gray-500"
              />
              <button
                type="submit"
                className="bg-emerald-500 hover:bg-emerald-600 text-black font-black text-xs px-3 py-1.5 rounded-lg border border-black transition-all flex items-center gap-1"
              >
                Run <Play className="w-3 h-3 fill-current" />
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* Completion Modal / Celebration Overlay */}
      <AnimatePresence>
        {showCelebration && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          >
            <div className="bg-white dark:bg-[#1f1c18] border-4 border-black dark:border-[#2e2924] rounded-2xl shadow-card p-8 max-w-md w-full text-center space-y-4">
              <div className="w-16 h-16 bg-yellow-400 border-2 border-black rounded-full flex items-center justify-center mx-auto text-black shadow-card-sm">
                <Sparkles className="w-8 h-8" />
              </div>
              <h3 className="text-2xl font-black text-text dark:text-[#f0ebe2]">
                Submodule Master Badge Unlocked! 🎉
              </h3>
              <p className="text-xs font-bold text-muted dark:text-[#c4bbae]">
                Congratulations! You successfully mastered Git submodules,
                initialized child repositories, updated remote commit pointers,
                and performed recursive clones.
              </p>
              <div className="bg-primary/20 border-2 border-black p-3 rounded-xl font-black text-sm text-text dark:text-[#f0ebe2]">
                Total XP Earned: +{totalXP} XP
              </div>
              <button
                onClick={() => setShowCelebration(false)}
                className="w-full bg-primary hover:bg-primary/90 text-black font-black py-3 rounded-xl border-2 border-black shadow-card-sm transition-all"
              >
                Continue Learning 🚀
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default GitSubmoduleSimulator;
