export interface GitCommit {
  id: string;
  message: string;
  parents: string[];
  branch: string; // The branch it was created on
}

export interface GitBranch {
  name: string;
  target: string; // commit id
}

export interface RepoState {
  commits: GitCommit[];
  branches: GitBranch[];
  HEAD: string; // branch name or commit id
  conflicts: string[]; // paths in conflict
}

export function createInitialRepo(): RepoState {
  const initialCommitId = "c1a2b3";
  return {
    commits: [
      {
        id: initialCommitId,
        message: "Initial commit",
        parents: [],
        branch: "main",
      },
    ],
    branches: [{ name: "main", target: initialCommitId }],
    HEAD: "main",
    conflicts: [],
  };
}

export function generateCommitId(): string {
  return Math.random().toString(16).substring(2, 8);
}

// Helper: Traverses the DAG to get the commit history for a specific commit ID
export function getCommitHistory(startCommitId: string, commits: GitCommit[]): GitCommit[] {
  const visited = new Set<string>();
  const queue = [startCommitId];

  while (queue.length > 0) {
    const currentId = queue.shift()!;
    if (visited.has(currentId)) continue;
    visited.add(currentId);

    const commit = commits.find((c) => c.id === currentId);
    if (commit) {
      queue.push(...commit.parents);
    }
  }

  // Preserve chronological order by filtering the main array (append-only)
  // Reversing at the end gives newest-to-oldest, matching real `git log`
  return commits.filter((c) => visited.has(c.id)).reverse();
}

// Helper: Checks if one commit is an ancestor of another
export function isAncestor(ancestorId: string, descendantId: string, commits: GitCommit[]): boolean {
  const history = getCommitHistory(descendantId, commits);
  return history.some((c) => c.id === ancestorId);
}

export function parseGitCommand(
  command: string,
  state: RepoState,
): { newState: RepoState; error?: string; output?: string } {
  const cmd = command.trim().replace(/\s+/g, " ");
  const parts = cmd.split(" ");

  if (parts[0] !== "git") {
    return { newState: state, error: "Command must start with 'git'" };
  }

  const newState: RepoState = JSON.parse(JSON.stringify(state));

  if (
    newState.conflicts.length > 0 &&
    parts[1] !== "add" &&
    parts[1] !== "commit" &&
    parts[1] !== "status"
  ) {
    return {
      newState: state,
      error: "You must resolve conflicts before executing other commands.",
    };
  }

  const headBranch = newState.branches.find((b) => b.name === newState.HEAD);
  const headCommitId = headBranch ? headBranch.target : newState.HEAD;

  switch (parts[1]) {
    case "commit": {
      let msg = "Update";
      const mIndex = parts.indexOf("-m");
      if (mIndex !== -1 && parts.length > mIndex + 1) {
        msg = parts
          .slice(mIndex + 1)
          .join(" ")
          .replace(/"/g, "")
          .replace(/'/g, "");
      }

      if (newState.conflicts.length > 0) {
        newState.conflicts = [];
      }

      const newCommitId = generateCommitId();
      const currentBranchName = headBranch ? headBranch.name : "detached";

      newState.commits.push({
        id: newCommitId,
        message: msg,
        parents: [headCommitId],
        branch: currentBranchName,
      });

      if (headBranch) {
        headBranch.target = newCommitId;
      } else {
        newState.HEAD = newCommitId;
      }

      return {
        newState,
        output: `[${currentBranchName} ${newCommitId}] ${msg}`,
      };
    }
    case "branch": {
      if (parts.length < 3) {
        const branchesList = newState.branches
          .map((b) => (b.name === newState.HEAD ? "* " : "  ") + b.name)
          .join("\n");
        return { newState, output: branchesList };
      }

      const newBranchName = parts[2];
      if (newState.branches.some((b) => b.name === newBranchName)) {
        return {
          newState: state,
          error: `fatal: A branch named '${newBranchName}' already exists.`,
        };
      }

      newState.branches.push({ name: newBranchName, target: headCommitId });
      return { newState, output: "" };
    }
    case "checkout":
    case "switch": {
      let branchName = parts[2];
      let createBranch = false;

      if (branchName === "-b" || branchName === "-c") {
        createBranch = true;
        branchName = parts[3];
      }

      if (!branchName) {
        return { newState: state, error: "fatal: Missing branch name" };
      }

      const existingBranch = newState.branches.find(
        (b) => b.name === branchName,
      );

      if (createBranch) {
        if (existingBranch) {
          return {
            newState: state,
            error: `fatal: A branch named '${branchName}' already exists.`,
          };
        }
        newState.branches.push({ name: branchName, target: headCommitId });
        newState.HEAD = branchName;
        return { newState, output: `Switched to a new branch '${branchName}'` };
      } else {
        if (!existingBranch) {
          return {
            newState: state,
            error: `error: pathspec '${branchName}' did not match any file(s) known to git`,
          };
        }
        newState.HEAD = branchName;
        return { newState, output: `Switched to branch '${branchName}'` };
      }
    }
    case "merge": {
      const targetBranchName = parts[2];
      if (!targetBranchName) return { newState: state, error: "fatal: Missing branch to merge" };
      
      const targetBranch = newState.branches.find((b) => b.name === targetBranchName);
      if (!targetBranch) return { newState: state, error: `merge: ${targetBranchName} - not something we can merge` };

      // Check for Fast-Forward or Up-to-Date
      if (isAncestor(targetBranch.target, headCommitId, newState.commits)) {
        return { newState: state, output: "Already up to date." };
      }
      
      if (isAncestor(headCommitId, targetBranch.target, newState.commits)) {
        if (headBranch) headBranch.target = targetBranch.target;
        else newState.HEAD = targetBranch.target;
        return { newState, output: `Updating ${headCommitId.substring(0,6)}..${targetBranch.target.substring(0,6)}\nFast-forward` };
      }

      // Simulate a conflict trigger
      if (targetBranchName.includes("conflict")) {
        newState.conflicts = ["index.html"];
        return {
          newState,
          error: `Auto-merging index.html\nCONFLICT (content): Merge conflict in index.html\nAutomatic merge failed; fix conflicts and then commit the result.`,
        };
      }

      // Recursive Merge
      const newCommitId = generateCommitId();
      newState.commits.push({
        id: newCommitId,
        message: `Merge branch '${targetBranchName}' into ${headBranch?.name || "detached"}`,
        parents: [headCommitId, targetBranch.target],
        branch: headBranch?.name || "detached",
      });

      if (headBranch) headBranch.target = newCommitId;
      else newState.HEAD = newCommitId;

      return { newState, output: `Merge made by the 'recursive' strategy.` };
    }
    case "rebase": {
      const targetBranchName = parts[2];
      if (!targetBranchName) return { newState: state, error: "fatal: Missing branch to rebase onto" };

      const targetBranch = newState.branches.find((b) => b.name === targetBranchName);
      if (!targetBranch) return { newState: state, error: `fatal: invalid upstream '${targetBranchName}'` };
      if (!headBranch) return { newState: state, error: "fatal: You are not on a branch." };

      if (isAncestor(headCommitId, targetBranch.target, newState.commits)) {
         return { newState: state, output: `Current branch ${headBranch.name} is up to date.` };
      }

      // Identify commits unique to the current branch
      const targetHistoryIds = new Set(getCommitHistory(targetBranch.target, newState.commits).map(c => c.id));
      const currentHistory = getCommitHistory(headCommitId, newState.commits).reverse(); // oldest to newest
      
      const commitsToRebase = currentHistory.filter(c => !targetHistoryIds.has(c.id));

      if (commitsToRebase.length === 0) {
        return { newState: state, output: `Current branch ${headBranch.name} is up to date.` };
      }

      // Simulate rebasing by rewriting commits
      let newParentId = targetBranch.target;
      for (const c of commitsToRebase) {
        const newCommitId = generateCommitId();
        newState.commits.push({
          id: newCommitId,
          message: c.message,
          parents: [newParentId],
          branch: headBranch.name,
        });
        newParentId = newCommitId;
      }

      headBranch.target = newParentId;
      return { newState, output: `Successfully rebased and updated ${headBranch.name}.` };
    }
    case "status": {
      if (newState.conflicts.length > 0) {
        return {
          newState,
          output: `On branch ${headBranch?.name}\nYou have unmerged paths.\n  (fix conflicts and run "git commit")\n\nUnmerged paths:\n  both modified:   ${newState.conflicts.join(", ")}`,
        };
      }
      return {
        newState,
        output: `On branch ${headBranch?.name}\nnothing to commit, working tree clean`,
      };
    }
    case "add": {
      return { newState, output: "" };
    }
    case "log": {
      // Log now traverses the graph properly instead of just reversing the whole array
      const history = getCommitHistory(headCommitId, newState.commits);
      const log = history
        .map((c) => `commit ${c.id}\n    ${c.message}`)
        .join("\n\n");
      return { newState, output: log };
    }
    default:
      return {
        newState: state,
        error: `git: '${parts[1]}' is not a git command.`,
      };
  }
}