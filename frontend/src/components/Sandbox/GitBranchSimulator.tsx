import React, { useState, useCallback } from "react";
import { GitBranch, Sparkles, BookOpen } from "lucide-react";

import type {
  BranchCommit,
  BranchSimState,
  BranchExercise,
} from "./branch/types";
import {
  BRANCH_COLORS,
  INITIAL_BRANCH_STATE,
  INITIAL_EXERCISES,
} from "./branch/types";
import { BranchGraph } from "./branch/BranchGraph";
import { BranchTerminal } from "./branch/BranchTerminal";
import { BranchExercisePanel } from "./branch/BranchExercisePanel";
import { BranchCelebrationModal } from "./branch/BranchCelebrationModal";

const BRANCH_COLOR_KEYS = [
  "#22c55e",
  "#3b82f6",
  "#a855f7",
  "#ef4444",
  "#f59e0b",
  "#06b6d4",
  "#ec4899",
  "#14b8a6",
];

function getNextColor(usedCount: number): string {
  return BRANCH_COLOR_KEYS[usedCount % BRANCH_COLOR_KEYS.length];
}

let commitCounter = 4;

export function GitBranchSimulator() {
  const [state, setState] = useState<BranchSimState>(INITIAL_BRANCH_STATE);
  const [terminalInput, setTerminalInput] = useState("");
  const [selectedCommit, setSelectedCommit] = useState<BranchCommit | null>(
    null,
  );
  const [exercises, setExercises] = useState<BranchExercise[]>(INITIAL_EXERCISES);
  const [currentExerciseIdx, setCurrentExerciseIdx] = useState(0);
  const [totalXP, setTotalXP] = useState(0);
  const [showCelebration, setShowCelebration] = useState(false);
  const [terminalLogs, setTerminalLogs] = useState<string[]>([
    "🌿 Git Branch Workflow Simulator v1.0",
    "Practice branching, merging, rebasing, cherry-picking, and stashing.",
    "Type 'help' for available commands.",
    "──────────────────────────────────────────────────",
  ]);

  const addLog = useCallback((text: string) => {
    setTerminalLogs((prev) => [...prev, text]);
  }, []);

  const checkExerciseCompletion = useCallback(
    (cmdPrefix: string) => {
      const currentEx = exercises[currentExerciseIdx];
      if (!currentEx || currentEx.completed) return;

      if (
        cmdPrefix.toLowerCase().startsWith(currentEx.requiredCmdPrefix.toLowerCase())
      ) {
        const updatedExs = [...exercises];
        updatedExs[currentExerciseIdx].completed = true;
        setExercises(updatedExs);
        setTotalXP((prev) => prev + currentEx.xp);
        addLog(`🎉 EXERCISE COMPLETE! +${currentEx.xp} XP: "${currentEx.title}"`);

        if (currentExerciseIdx + 1 < exercises.length) {
          setCurrentExerciseIdx((prev) => prev + 1);
        } else {
          setShowCelebration(true);
        }
      }
    },
    [exercises, currentExerciseIdx, addLog],
  );

  const handleCommand = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const cmd = terminalInput.trim();
      if (!cmd) return;

      addLog(`$ ${cmd}`);
      setTerminalInput("");

      const parts = cmd.split(/\s+/);
      const mainCmd = parts[0]?.toLowerCase();

      // --- Built-in commands ---
      if (cmd === "clear") {
        setTerminalLogs([]);
        return;
      }

      if (cmd === "help") {
        addLog("💡 Available Branch Workflow Commands:");
        addLog("  git branch                         - List branches");
        addLog("  git branch <name>                  - Create a new branch");
        addLog("  git checkout <branch>              - Switch to a branch");
        addLog("  git checkout -b <name>             - Create and switch to new branch");
        addLog("  git commit -m '<message>'          - Commit staged changes");
        addLog("  git merge <branch>                 - Merge a branch into current");
        addLog("  git rebase <branch>                - Rebase current branch onto another");
        addLog("  git cherry-pick <commit>           - Apply a specific commit");
        addLog("  git stash                          - Stash working changes");
        addLog("  git stash pop                      - Apply stashed changes");
        addLog("  git log                            - View commit history");
        addLog("  git status                         - View repository status");
        addLog("  reset                              - Reset simulator");
        addLog("  clear                              - Clear terminal");
        return;
      }

      if (cmd === "reset") {
        commitCounter = 4;
        setState(INITIAL_BRANCH_STATE);
        setSelectedCommit(null);
        setExercises(INITIAL_EXERCISES);
        setCurrentExerciseIdx(0);
        setTotalXP(0);
        addLog("🔄 Simulator reset to initial state.");
        return;
      }

      // --- Git commands ---
      if (mainCmd === "git") {
        const subCmd = parts[1]?.toLowerCase();

        if (!subCmd) {
          addLog("usage: git <command> [<args>]");
          return;
        }

        // git branch [name]
        if (subCmd === "branch") {
          const branchName = parts[2];
          if (!branchName) {
            // List branches
            addLog("Branches:");
            state.branches.forEach((b) => {
              const marker =
                b.isHead ? " * " : "   ";
              addLog(`${marker}${b.name}`);
            });
            return;
          }

          // Create new branch
          if (state.branches.find((b) => b.name === branchName)) {
            addLog(`fatal: A branch named '${branchName}' already exists.`);
            return;
          }

          const newColor = getNextColor(state.branches.length);
          const newBranch = {
            id: branchName,
            name: branchName,
            color: newColor,
            isHead: false,
          };

          // Register color for the branch
          BRANCH_COLORS[branchName] = newColor;

          setState((prev) => ({
            ...prev,
            branches: [...prev.branches, newBranch],
          }));
          addLog(`✅ Created branch '${branchName}'`);
          checkExerciseCompletion("git branch");
          return;
        }

        // git checkout
        if (subCmd === "checkout") {
          const isB = parts.includes("-b");
          const targetBranch = isB ? parts[3] : parts[2];

          if (!targetBranch) {
            addLog("usage: git checkout [-b] <branch>");
            return;
          }

          if (isB) {
            // Create and switch
            if (state.branches.find((b) => b.name === targetBranch)) {
              addLog(`fatal: A branch named '${targetBranch}' already exists.`);
              return;
            }

            const newColor = getNextColor(state.branches.length);
            BRANCH_COLORS[targetBranch] = newColor;

            setState((prev) => ({
              ...prev,
              branches: prev.branches.map((b) => ({
                ...b,
                isHead: b.name === targetBranch,
              })).concat({
                id: targetBranch,
                name: targetBranch,
                color: newColor,
                isHead: true,
              }),
              currentBranch: targetBranch,
              detachedHead: false,
            }));

            addLog(`✅ Switched to a new branch '${targetBranch}'`);
            checkExerciseCompletion(`git checkout -b ${targetBranch}`);
            return;
          }

          // Regular checkout
          if (targetBranch === "HEAD~1" || targetBranch.startsWith("HEAD~")) {
            addLog(`⚠️  Detached HEAD at ${targetBranch}`);
            setState((prev) => ({
              ...prev,
              detachedHead: true,
              branches: prev.branches.map((b) => ({ ...b, isHead: false })),
            }));
            return;
          }

          const exists = state.branches.find((b) => b.name === targetBranch);
          if (!exists) {
            addLog(`error: pathspec '${targetBranch}' did not match any branch`);
            return;
          }

          setState((prev) => ({
            ...prev,
            currentBranch: targetBranch,
            detachedHead: false,
            branches: prev.branches.map((b) => ({
              ...b,
              isHead: b.name === targetBranch,
            })),
          }));
          addLog(`✅ Switched to branch '${targetBranch}'`);
          checkExerciseCompletion(`git checkout ${targetBranch}`);
          return;
        }

        // git commit -m
        if (subCmd === "commit") {
          const msgFlag = parts.indexOf("-m");
          if (msgFlag === -1 || !parts[msgFlag + 1]) {
            addLog("usage: git commit -m '<message>'");
            return;
          }

          const message = parts.slice(msgFlag + 1).join(" ").replace(/^['"]|['"]$/g, "");
          const parentId = state.headCommitId;
          const parentCommit = state.commits.find((c) => c.id === parentId);
          const yOffset = state.commits.length * NODE_SPACING;

          const newCommit: BranchCommit = {
            id: `c${commitCounter++}`,
            message,
            branch: state.currentBranch,
            x: parentCommit ? parentCommit.x : 400,
            y: parentCommit ? parentCommit.y + yOffset : 60,
            parentIds: [parentId],
          };

          setState((prev) => ({
            ...prev,
            commits: [...prev.commits, newCommit],
            headCommitId: newCommit.id,
            workingChanges: [],
          }));
          addLog(`[${state.currentBranch} ${newCommit.id}] ${message}`);
          checkExerciseCompletion("git commit -m");
          return;
        }

        // git merge <branch>
        if (subCmd === "merge") {
          const targetBranch = parts[2];
          if (!targetBranch) {
            addLog("usage: git merge <branch>");
            return;
          }

          if (targetBranch === state.currentBranch) {
            addLog("Already up to date.");
            return;
          }

          const targetExists = state.branches.find(
            (b) => b.name === targetBranch,
          );
          if (!targetExists) {
            addLog(`fatal: '${targetBranch}' does not point to a commit`);
            return;
          }

          // Find latest commit on target branch
          const targetCommits = state.commits
            .filter((c) => c.branch === targetBranch)
            .sort((a, b) => b.y - a.y);
          if (targetCommits.length === 0) {
            addLog(`fatal: '${targetBranch}' has no commits to merge`);
            return;
          }

          const latestTarget = targetCommits[0];
          const headCommit = state.commits.find(
            (c) => c.id === state.headCommitId,
          );
          const yOffset = state.commits.length * NODE_SPACING;

          const mergeCommit: BranchCommit = {
            id: `c${commitCounter++}`,
            message: `Merge branch '${targetBranch}' into ${state.currentBranch}`,
            branch: state.currentBranch,
            x: headCommit ? headCommit.x : 400,
            y: headCommit ? headCommit.y + yOffset : 60,
            parentIds: [state.headCommitId],
            mergeParentIds: [latestTarget.id],
          };

          setState((prev) => ({
            ...prev,
            commits: [...prev.commits, mergeCommit],
            headCommitId: mergeCommit.id,
            branches: prev.branches.map((b) =>
              b.name === targetBranch ? { ...b, isHead: false } : b.name === state.currentBranch ? { ...b, isHead: true } : b,
            ),
          }));
          addLog(`✅ Merge made by 'ort' strategy.`);
          addLog(`   Merged ${targetBranch} into ${state.currentBranch}`);
          checkExerciseCompletion(`git merge ${targetBranch}`);
          return;
        }

        // git rebase <branch>
        if (subCmd === "rebase") {
          const targetBranch = parts[2];
          if (!targetBranch) {
            addLog("usage: git rebase <branch>");
            return;
          }

          if (targetBranch === state.currentBranch) {
            addLog("Current branch is already up to date.");
            return;
          }

          const targetExists = state.branches.find(
            (b) => b.name === targetBranch,
          );
          if (!targetExists) {
            addLog(`fatal: invalid upstream '${targetBranch}'`);
            return;
          }

          const latestTarget = state.commits
            .filter((c) => c.branch === targetBranch)
            .sort((a, b) => b.y - a.y)[0];

          if (!latestTarget) {
            addLog(`fatal: invalid upstream '${targetBranch}'`);
            return;
          }

          // Replay commits on top of target
          const branchCommits = state.commits
            .filter((c) => c.branch === state.currentBranch)
            .sort((a, b) => a.y - b.y);

          let newY = latestTarget.y;
          const replayedCommits: BranchCommit[] = [];

          branchCommits.forEach((commit) => {
            newY += NODE_SPACING;
            replayedCommits.push({
              ...commit,
              y: newY,
              parentIds:
                replayedCommits.length > 0
                  ? [replayedCommits[replayedCommits.length - 1].id]
                  : [latestTarget.id],
              branch: state.currentBranch,
            });
          });

          const newHeadId =
            replayedCommits.length > 0
              ? replayedCommits[replayedCommits.length - 1].id
              : state.headCommitId;

          setState((prev) => ({
            ...prev,
            commits: [
              ...prev.commits.filter(
                (c) => c.branch !== state.currentBranch,
              ),
              ...replayedCommits,
            ],
            headCommitId: newHeadId,
          }));
          addLog(`Successfully rebased and updated refs/heads/${state.currentBranch}.`);
          addLog(`✅ Rebased ${state.currentBranch} onto ${targetBranch}`);
          checkExerciseCompletion(`git rebase ${targetBranch}`);
          return;
        }

        // git cherry-pick
        if (subCmd === "cherry-pick") {
          const commitId = parts[2];
          if (!commitId) {
            addLog("usage: git cherry-pick <commit-hash>");
            return;
          }

          const sourceCommit = state.commits.find((c) => c.id === commitId);
          if (!sourceCommit) {
            addLog(`fatal: bad revision '${commitId}'`);
            return;
          }

          const headCommit = state.commits.find(
            (c) => c.id === state.headCommitId,
          );
          const yOffset = state.commits.length * NODE_SPACING;

          const pickedCommit: BranchCommit = {
            id: `c${commitCounter++}`,
            message: sourceCommit.message,
            branch: state.currentBranch,
            x: headCommit ? headCommit.x : 400,
            y: headCommit ? headCommit.y + yOffset : 60,
            parentIds: [state.headCommitId],
          };

          setState((prev) => ({
            ...prev,
            commits: [...prev.commits, pickedCommit],
            headCommitId: pickedCommit.id,
          }));
          addLog(`✅ [${state.currentBranch} ${pickedCommit.id}] ${sourceCommit.message}`);
          addLog(`   Cherry-picked commit ${commitId}`);
          checkExerciseCompletion("git cherry-pick");
          return;
        }

        // git stash
        if (subCmd === "stash") {
          if (state.stash.length > 0 && parts[2] !== "pop" && parts[2] !== "apply") {
            addLog("⚠️  Stash already exists. Use 'git stash pop' to apply.");
            return;
          }

          if (state.stash.length === 0 && parts[2] === "pop") {
            addLog("No stash entries to pop.");
            return;
          }

          if (parts[2] === "pop" || parts[2] === "apply") {
            if (state.stash.length === 0) {
              addLog("No stash entries to apply.");
              return;
            }
            const popped = state.stash[state.stash.length - 1];
            setState((prev) => ({
              ...prev,
              stash: prev.stash.slice(0, -1),
              workingChanges: [...prev.workingChanges, popped],
            }));
            addLog(`✅ On branch ${state.currentBranch}`);
            addLog(`Changes restored from stash: ${popped}`);
            checkExerciseCompletion("git stash pop");
            return;
          }

          if (state.workingChanges.length === 0) {
            addLog("No local changes to save.");
            return;
          }

          const changes = state.workingChanges;
          setState((prev) => ({
            ...prev,
            stash: [...prev.stash, ...changes],
            workingChanges: [],
          }));
          addLog(`✅ Saved working directory changes on ${state.currentBranch}`);
          addLog(`   Stashed ${changes.length} file(s): ${changes.join(", ")}`);
          checkExerciseCompletion("git stash");
          return;
        }

        // git log
        if (subCmd === "log") {
          const branchCommits = state.commits
            .filter((c) => c.branch === state.currentBranch)
            .sort((a, b) => b.y - a.y)
            .slice(0, 5);

          if (branchCommits.length === 0) {
            addLog("No commits on this branch yet.");
            return;
          }

          branchCommits.forEach((c, i) => {
            addLog(`commit ${c.id}`);
            addLog(`  ${c.message}`);
            addLog(`  branch: ${c.branch}`);
            if (i < branchCommits.length - 1) addLog("");
          });
          return;
        }

        // git status
        if (subCmd === "status") {
          addLog(`On branch ${state.currentBranch}`);
          if (state.workingChanges.length > 0) {
            addLog("");
            addLog("Changes not staged for commit:");
            state.workingChanges.forEach((c) => {
              addLog(`  modified:   ${c}`);
            });
          } else {
            addLog("nothing to commit, working tree clean");
          }
          if (state.stash.length > 0) {
            addLog("");
            addLog(`Stash: ${state.stash.length} entry/entries`);
          }
          return;
        }

        addLog(`git: '${subCmd}' is not a git command. Type 'help' for list.`);
        return;
      }

      addLog(`Command not recognized: '${cmd}'. Type 'help' for available commands.`);
    },
    [terminalInput, state, addLog, checkExerciseCompletion, exercises, currentExerciseIdx],
  );

  const handleResetGraph = () => {
    commitCounter = 4;
    setState(INITIAL_BRANCH_STATE);
    setSelectedCommit(null);
    addLog("🔄 Graph view refreshed.");
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="bg-surface-low dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl p-6 shadow-card flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="bg-primary text-black text-xs font-black px-2.5 py-1 rounded-md border border-black uppercase tracking-wider flex items-center gap-1">
              <GitBranch className="w-3.5 h-3.5" /> Interactive Sandbox
            </span>
            <span className="bg-accent/20 text-accent text-xs font-bold px-2.5 py-1 rounded-md border border-accent/40">
              Atelier Studio
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-black text-text dark:text-[#f0ebe2] flex items-center gap-2">
            Git Branch Workflow Simulator
          </h1>
          <p className="mt-1 text-sm font-bold text-muted dark:text-[#c4bbae] max-w-2xl">
            Master branch management, merging, rebasing, cherry-picking, and
            stashing with a live visual commit graph and guided exercises.
          </p>
        </div>

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

      {/* Quick reference */}
      <div className="bg-white dark:bg-[#0f0e0c] border-2 border-black/10 dark:border-[#2e2924] rounded-xl p-4 flex items-start gap-3">
        <BookOpen className="w-4 h-4 text-primary flex-shrink-0 mt-0.5" />
        <div className="text-[11px] font-bold text-muted dark:text-[#9b8f80] leading-relaxed">
          <strong className="text-text dark:text-[#f0ebe2]">Quick Reference:</strong>{" "}
          <code className="bg-surface-low dark:bg-[#151411] px-1.5 py-0.5 rounded text-text dark:text-[#f0ebe2]">checkout -b</code> creates + switches, {" "}
          <code className="bg-surface-low dark:bg-[#151411] px-1.5 py-0.5 rounded text-text dark:text-[#f0ebe2]">merge</code> joins branches, {" "}
          <code className="bg-surface-low dark:bg-[#151411] px-1.5 py-0.5 rounded text-text dark:text-[#f0ebe2]">rebase</code> replays commits, {" "}
          <code className="bg-surface-low dark:bg-[#151411] px-1.5 py-0.5 rounded text-text dark:text-[#f0ebe2]">cherry-pick</code> grabs single commits, {" "}
          <code className="bg-surface-low dark:bg-[#151411] px-1.5 py-0.5 rounded text-text dark:text-[#f0ebe2]">stash</code> shelves changes.
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7 space-y-6 flex flex-col">
          <BranchGraph
            state={state}
            selectedCommit={selectedCommit}
            onSelectCommit={setSelectedCommit}
            onReset={handleResetGraph}
          />
        </div>

        <div className="lg:col-span-5 space-y-6 flex flex-col">
          <BranchExercisePanel
            exercises={exercises}
            currentExerciseIdx={currentExerciseIdx}
            onSelectExercise={setCurrentExerciseIdx}
            totalXP={totalXP}
          />

          <BranchTerminal
            logs={terminalLogs}
            input={terminalInput}
            onInputChange={setTerminalInput}
            onSubmit={handleCommand}
            onClearLogs={() => setTerminalLogs([])}
            currentBranch={state.currentBranch}
          />
        </div>
      </div>

      <BranchCelebrationModal
        show={showCelebration}
        totalXP={totalXP}
        onClose={() => setShowCelebration(false)}
      />
    </div>
  );
}

const NODE_SPACING = 80;

export default GitBranchSimulator;
