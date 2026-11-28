import React, { useState, useEffect } from "react";
import {
  GitBranch,
  GitCommit,
  Play,
  CheckCircle2,
  Terminal,
  Zap,
  RotateCcw,
  RotateCw,
} from "lucide-react";
import {
  RebaseCommitGraph,
  RebaseCommit,
} from "../components/Sandbox/RebaseCommitGraph";
import { RebaseControlsModal } from "../components/Sandbox/RebaseControlsModal";
import toast from "react-hot-toast";
import { shortcutsSuspended } from "../features/shortcuts/store";

interface RebaseScenario {
  id: string;
  title: string;
  difficulty: "Beginner" | "Intermediate" | "Advanced";
  xp_reward: number;
  description: string;
  base_branch: string;
  initial_commits: RebaseCommit[];
  conflicts?: { commit_hash: string; file: string; conflict_hunk: string }[];
}

const REAL_WORLD_SCENARIOS: RebaseScenario[] = [
  {
    id: "squash-wip",
    title: "1. Squash 5 'WIP' Commits Before PR Review",
    difficulty: "Beginner",
    xp_reward: 150,
    description:
      "You pushed 5 small draft commits while working on your feature PR. Maintainers requested squashing them into 1 single clean commit.",
    base_branch: "main",
    initial_commits: [
      {
        hash: "a1b2c3d",
        message: "feat(auth): implement user login API route",
        author: "contributor",
        files_changed: ["src/auth.ts"],
        action: "pick",
      },
      {
        hash: "e4f5g6h",
        message: "wip fix typo in auth validator",
        author: "contributor",
        files_changed: ["src/auth.ts"],
        action: "squash",
      },
      {
        hash: "i7j8k9l",
        message: "wip add regex password check",
        author: "contributor",
        files_changed: ["src/auth.ts"],
        action: "squash",
      },
      {
        hash: "m0n1o2p",
        message: "wip fix linter warnings",
        author: "contributor",
        files_changed: ["src/auth.ts"],
        action: "squash",
      },
      {
        hash: "q3r4s5t",
        message: "wip remove console.log",
        author: "contributor",
        files_changed: ["src/auth.ts"],
        action: "squash",
      },
    ],
  },
  {
    id: "reword-and-drop",
    title: "2. Reword Vague Messages & Drop Debug Code",
    difficulty: "Intermediate",
    xp_reward: 200,
    description:
      "Fix non-descriptive commit titles with 'reword' and drop temporary debug print commits ('TEMP debug statement') with 'drop'.",
    base_branch: "main",
    initial_commits: [
      {
        hash: "b8c9d0e",
        message: "add stuff for api",
        author: "contributor",
        files_changed: ["src/api.ts"],
        action: "reword",
        new_message: "feat(api): implement exponential retry backoff",
      },
      {
        hash: "f1g2h3i",
        message: "TEMP: console.log response data",
        author: "contributor",
        files_changed: ["src/api.ts"],
        action: "drop",
      },
      {
        hash: "j4k5l6m",
        message: "feat(ws): connect real-time WebSocket client",
        author: "contributor",
        files_changed: ["src/ws.ts"],
        action: "pick",
      },
    ],
  },
  {
    id: "rebase-conflict",
    title: "3. Resolve Rebase Conflicts with Main Branch",
    difficulty: "Advanced",
    xp_reward: 300,
    description:
      "Main branch moved forward while your PR was open. Rebase your feature onto main and resolve the conflict hunk in src/config.ts.",
    base_branch: "main",
    initial_commits: [
      {
        hash: "c3d4e5f",
        message: "feat(config): update environment port defaults",
        author: "contributor",
        files_changed: ["src/config.ts"],
        action: "pick",
      },
      {
        hash: "g7h8i9j",
        message: "docs: update deployment instructions",
        author: "contributor",
        files_changed: ["README.md"],
        action: "pick",
      },
    ],
    conflicts: [
      {
        commit_hash: "c3d4e5f",
        file: "src/config.ts",
        conflict_hunk: `<<<<<<< HEAD (main branch)
export const PORT = process.env.PORT || 8080;
=======
export const PORT = process.env.PORT || 3000;
>>>>>>> c3d4e5f (feat(config): update environment port defaults)`,
      },
    ],
  },
];

export function GitRebaseVisualizerPage() {
  const [scenarios] = useState<RebaseScenario[]>(REAL_WORLD_SCENARIOS);
  const [activeScenario, setActiveScenario] = useState<RebaseScenario>(
    REAL_WORLD_SCENARIOS[0],
  );
  const [commits, setCommits] = useState<RebaseCommit[]>(
    REAL_WORLD_SCENARIOS[0].initial_commits,
  );
  const [past, setPast] = useState<RebaseCommit[][]>([]);
  const [future, setFuture] = useState<RebaseCommit[][]>([]);

  const [executionLogs, setExecutionLogs] = useState<string[]>([]);
  const [showConflictModal, setShowConflictModal] = useState<boolean>(false);
  const [isCompleted, setIsCompleted] = useState<boolean>(false);
  const [earnedXP, setEarnedXP] = useState<number>(0);
  const [isExecuting, setIsExecuting] = useState<boolean>(false);

  const handleSelectScenario = (sc: RebaseScenario) => {
    setActiveScenario(sc);
    setCommits(sc.initial_commits);
    setPast([]);
    setFuture([]);
    setExecutionLogs([]);
    setIsCompleted(false);
  };

  const updateCommitsWithHistory = (newCommits: RebaseCommit[]) => {
    setPast((prevPast) => [...prevPast, commits]);
    setCommits(newCommits);
    setFuture([]);
  };

  const handleCommitActionChange = (
    index: number,
    action: RebaseCommit["action"],
    newMessage?: string,
  ) => {
    const updated = commits.map((c, i) =>
      i === index
        ? { ...c, action, new_message: newMessage || c.new_message }
        : c,
    );
    updateCommitsWithHistory(updated);
  };

  const handleMoveCommit = (fromIndex: number, toIndex: number) => {
    if (toIndex < 0 || toIndex >= commits.length) return;
    const updated = [...commits];
    const [moved] = updated.splice(fromIndex, 1);
    updated.splice(toIndex, 0, moved);
    updateCommitsWithHistory(updated);
  };

  const handleUndo = () => {
    if (past.length === 0) return;
    const previous = past[past.length - 1];
    const newPast = past.slice(0, past.length - 1);
    setFuture((prevFuture) => [commits, ...prevFuture]);
    setPast(newPast);
    setCommits(previous);
  };

  const handleRedo = () => {
    if (future.length === 0) return;
    const next = future[0];
    const newFuture = future.slice(1);
    setPast((prevPast) => [...prevPast, commits]);
    setFuture(newFuture);
    setCommits(next);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // The shortcut editor is open, so undo and redo stay off too.
      if (shortcutsSuspended()) return;
      const target = e.target as HTMLElement;
      if (
        target &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA")
      ) {
        return;
      }

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        if (e.shiftKey) {
          e.preventDefault();
          handleRedo();
        } else {
          e.preventDefault();
          handleUndo();
        }
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") {
        e.preventDefault();
        handleRedo();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [past, future, commits]);

  const handleExecuteRebase = () => {
    setIsExecuting(true);
    setExecutionLogs([
      "$ git rebase -i origin/main",
      "Parsing commit TODO list...",
    ]);

    setTimeout(() => {
      if (activeScenario.conflicts && activeScenario.conflicts.length > 0) {
        setExecutionLogs((prev) => [
          ...prev,
          "Applying: " + commits[0]?.message,
          "CONFLICT (content): Merge conflict in " +
            activeScenario.conflicts![0].file,
          "error: Failed to merge in the changes.",
          "Patch failed at " + commits[0]?.hash.substring(0, 7),
          "Fix conflicts and then run 'git rebase --continue'.",
        ]);
        setShowConflictModal(true);
        setIsExecuting(false);
      } else {
        const logs = commits.map((c) => {
          const act = (c.action || "pick").toUpperCase();
          if (act === "DROP")
            return `[DROPPED] ${c.hash.substring(0, 7)} - ${c.message}`;
          if (act === "SQUASH")
            return `[SQUASHED] into previous commit: ${c.message}`;
          return `[APPLIED] ${c.hash.substring(0, 7)} - ${c.new_message || c.message}`;
        });

        setExecutionLogs((prev) => [
          ...prev,
          ...logs,
          "Successfully rebased and updated refs/heads/feature.",
        ]);
        setIsCompleted(true);
        setEarnedXP(activeScenario.xp_reward);
        setIsExecuting(false);
        toast.success(`Scenario Mastered! +${activeScenario.xp_reward} XP`);
      }
    }, 600);
  };

  return (
    <main
      id="main-content"
      className="w-full max-w-[1600px] mx-auto space-y-6 text-text dark:text-[#f0ebe2] px-2 sm:px-4 lg:px-6"
    >
      {/* Header Banner Deck - Clean 2-Row Neo-Brutalist Layout */}
      <div className="w-full bg-white dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-3xl p-6 shadow-card space-y-5">
        {/* Row 1: Icon, Title & Subtitle */}
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-2xl bg-[#C3C0FF] border-2 border-black flex items-center justify-center shrink-0 text-black shadow-card-sm">
            <GitBranch className="w-6 h-6 sm:w-7 sm:h-7" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xl sm:text-3xl font-display font-black uppercase tracking-tight text-black dark:text-white">
                Git Interactive Rebase Studio
              </h1>
              <span className="text-[10px] font-mono font-black uppercase px-2.5 py-0.5 rounded-md bg-[#C3C0FF] text-black border-2 border-black">
                Interactive Lab
              </span>
            </div>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 font-bold mt-1">
              Master{" "}
              <code className="font-mono text-black dark:text-white bg-amber-300 px-1.5 py-0.5 rounded border border-black font-black">
                git rebase -i
              </code>{" "}
              in real-life open source scenarios. Squash WIP commits, reword
              titles, and resolve conflicts.
            </p>
          </div>
        </div>

        {/* Row 2: Scenario Selection Deck (Fits 100% inside card bounds) */}
        <div className="w-full bg-surface-low dark:bg-[#0a0a0f] p-2 rounded-2xl border-2 border-black dark:border-[#2e2924] flex flex-wrap items-center gap-2 overflow-hidden">
          {scenarios.map((sc) => (
            <button
              key={sc.id}
              onClick={() => handleSelectScenario(sc)}
              className={`px-3.5 py-2 text-xs font-black rounded-xl transition-all border-2 border-black ${
                activeScenario.id === sc.id
                  ? "bg-[#C3C0FF] text-black shadow-card-sm"
                  : "bg-white dark:bg-[#151411] text-text dark:text-white hover:bg-gray-100 dark:hover:bg-[#1f1c18]"
              }`}
            >
              {sc.title}
            </button>
          ))}
        </div>
      </div>

      {/* Challenge Goal & Action Bar */}
      <div className="bg-white dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-card">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-black uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Active Scenario:
            </span>
            <span className="px-2.5 py-0.5 text-[10px] font-mono font-black text-black bg-amber-300 border-2 border-black rounded-md">
              +{activeScenario.xp_reward} Contributor XP
            </span>
          </div>
          <p className="text-xs sm:text-sm font-black text-black dark:text-[#f0ebe2]">
            {activeScenario.description}
          </p>
        </div>

        <button
          onClick={handleExecuteRebase}
          disabled={isExecuting}
          className="px-6 py-3 bg-[#C3C0FF] hover:bg-[#b0adff] text-black border-2 border-black text-xs font-black rounded-xl shadow-card transition-all flex items-center justify-center gap-2 shrink-0 active:translate-y-0.5"
        >
          <Play className="w-4 h-4 fill-black" />
          {isExecuting ? "Executing Rebase..." : "Run Rebase (git rebase -i)"}
        </button>
      </div>

      {/* Completion Celebration Alert */}
      {isCompleted && (
        <div className="p-5 bg-emerald-400 text-black border-4 border-black rounded-2xl flex items-center justify-between shadow-card animate-fadeIn">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-black text-white rounded-xl">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-black uppercase">
                Rebase Scenario Mastered!
              </h3>
              <p className="text-xs font-bold">
                You successfully mastered this open-source Git workflow and
                earned <strong>+{earnedXP} Contributor XP</strong>.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Interactive Rebase Workspace - 100% Fluid Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Interactive Commit TODO List */}
        <div className="lg:col-span-7 space-y-4 bg-white dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl p-5 shadow-card">
          <div className="flex items-center justify-between pb-3 border-b-2 border-black dark:border-[#2e2924]">
            <h2 className="text-sm font-black text-black dark:text-[#f0ebe2] uppercase tracking-wider flex items-center gap-2">
              <GitCommit className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />{" "}
              Interactive Commit TODO List
            </h2>
            <div className="flex items-center gap-3">
              <span className="text-xs font-mono font-bold text-slate-500 hidden sm:inline">
                Pick / Reword / Squash / Drop
              </span>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={handleUndo}
                  disabled={past.length === 0}
                  title="Undo step (Ctrl+Z)"
                  aria-label="Undo"
                  className="p-1.5 bg-gray-100 dark:bg-slate-800 text-black dark:text-white rounded-lg border border-black dark:border-slate-700 hover:bg-gray-200 dark:hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={handleRedo}
                  disabled={future.length === 0}
                  title="Redo step (Ctrl+Y)"
                  aria-label="Redo"
                  className="p-1.5 bg-gray-100 dark:bg-slate-800 text-black dark:text-white rounded-lg border border-black dark:border-slate-700 hover:bg-gray-200 dark:hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                >
                  <RotateCw className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>

          <RebaseCommitGraph
            commits={commits}
            onCommitActionChange={handleCommitActionChange}
            onMoveCommit={handleMoveCommit}
          />
        </div>

        {/* Terminal Execution Log & Guide */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-[#0f0e0c] border-4 border-black dark:border-[#2e2924] rounded-2xl p-4 font-mono text-xs shadow-card text-[#f0ebe2] space-y-3">
            <div className="flex items-center justify-between border-b border-white/10 pb-2">
              <span className="text-xs font-black text-amber-400 uppercase flex items-center gap-2">
                <Terminal className="w-4 h-4" /> Terminal Rebase Log
              </span>
              <span className="text-[10px] text-slate-500">CLI Simulator</span>
            </div>

            <div className="h-[320px] overflow-y-auto space-y-2 pr-1 custom-scrollbar">
              <p className="text-slate-500">
                # Interactive Rebase instruction Todo list
              </p>
              {commits.map((c, i) => (
                <div key={i} className="text-slate-400 flex items-center gap-2">
                  <span className="text-amber-400 font-bold uppercase text-[10px] w-14 shrink-0">
                    {c.action || "pick"}
                  </span>
                  <span className="text-indigo-400 shrink-0">
                    {c.hash.substring(0, 7)}
                  </span>
                  <span className="truncate">{c.new_message || c.message}</span>
                </div>
              ))}

              <div className="pt-3 border-t border-white/10 space-y-1">
                {executionLogs.map((log, idx) => (
                  <p key={idx} className="text-emerald-400 font-bold">
                    {log}
                  </p>
                ))}
              </div>
            </div>
          </div>

          {/* Educational Command Guide Card */}
          <div className="p-5 bg-white dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl space-y-3 shadow-card">
            <h3 className="font-black text-sm text-black dark:text-white flex items-center gap-2 uppercase">
              <Zap className="w-4 h-4 text-amber-500" /> Real-World Git Rebase
              Commands
            </h3>
            <ul className="space-y-2 text-xs font-bold text-slate-700 dark:text-slate-300">
              <li className="flex items-start gap-2">
                <span className="font-mono font-black text-emerald-600 bg-emerald-100 dark:bg-emerald-950 px-1.5 py-0.5 rounded border border-black shrink-0">
                  pick
                </span>
                <span>Keep the commit as-is in history.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="font-mono font-black text-purple-600 bg-purple-100 dark:bg-purple-950 px-1.5 py-0.5 rounded border border-black shrink-0">
                  squash
                </span>
                <span>
                  Combine commit into previous commit and merge commit messages.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="font-mono font-black text-cyan-600 bg-cyan-100 dark:bg-cyan-950 px-1.5 py-0.5 rounded border border-black shrink-0">
                  reword
                </span>
                <span>Keep commit changes but rewrite title/message.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="font-mono font-black text-rose-600 bg-rose-100 dark:bg-rose-950 px-1.5 py-0.5 rounded border border-black shrink-0">
                  drop
                </span>
                <span>Completely delete commit from branch history.</span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* Conflict Resolution Modal */}
      {showConflictModal && (
        <RebaseControlsModal
          commits={commits}
          conflicts={activeScenario.conflicts || []}
          onClose={() => setShowConflictModal(false)}
          onResolveConflict={() => {
            setShowConflictModal(false);
            setExecutionLogs((prev) => [
              ...prev,
              "$ git add src/config.ts",
              "$ git rebase --continue",
              "Applying: feat(config): update environment port defaults",
              "Successfully rebased and updated refs/heads/feature.",
            ]);
            setIsCompleted(true);
            setEarnedXP(activeScenario.xp_reward);
            toast.success(
              `Conflict Resolved & Scenario Mastered! +${activeScenario.xp_reward} XP`,
            );
          }}
        />
      )}
    </main>
  );
}

export default GitRebaseVisualizerPage;
