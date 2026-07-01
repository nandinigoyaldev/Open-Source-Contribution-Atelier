/**
 * useGitShell – Pure TypeScript virtual filesystem + Git state engine.
 * Simulates git init, git add, git commit, git status, git log, ls, pwd, cat, cd.
 * Designed as a WASM-compatible architecture (state is serialisable).
 */

import { useState, useCallback, useRef } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

export type FileEntry = { type: "file"; content: string };
export type DirEntry = { type: "dir"; children: Record<string, FsNode> };
export type FsNode = FileEntry | DirEntry;

export interface GitObjectEntry {
  hash: string;
  blob: string;
}

export interface GitCommit {
  hash: string;
  message: string;
  author: string;
  timestamp: string;
  tree: Record<string, string>; // filename → blob hash
  parent: string | null;
}

export interface GitRepo {
  initialized: boolean;
  currentBranch: string;
  HEAD: string | null;
  staged: Record<string, string>; // path → content
  commits: GitCommit[];
  objects: Record<string, GitObjectEntry>;
  branches: Record<string, string>; // branch → commit hash
  remotes: Record<string, string>; // name → url
  mergeState?: boolean;
  unmerged?: Record<string, boolean>;
}

export interface ShellState {
  cwd: string[]; // path segments, e.g. ["~", "myrepo"]
  fs: Record<string, FsNode>; // flat map keyed by "/"-joined path
  git: GitRepo;
  editorState?: { file: string; content: string } | null;
}

export interface TerminalLine {
  id: number;
  prompt?: string;
  text: string;
  kind: "output" | "error" | "success" | "command" | "info";
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function shortHash(): string {
  return Math.random().toString(36).slice(2, 9);
}

function joinPath(parts: string[]): string {
  return parts.join("/") || "/";
}

function getNode(
  fs: Record<string, FsNode>,
  pathParts: string[],
): FsNode | undefined {
  return fs[joinPath(pathParts)];
}

function cwdKey(cwd: string[]): string {
  return joinPath(cwd);
}

function listDir(fs: Record<string, FsNode>, cwd: string[]): string[] {
  const prefix = cwdKey(cwd) + "/";
  const root = cwdKey(cwd);
  const names = new Set<string>();
  for (const key of Object.keys(fs)) {
    if (key === root) continue;
    if (key.startsWith(prefix)) {
      const rest = key.slice(prefix.length);
      const top = rest.split("/")[0];
      if (top) names.add(top);
    }
  }
  return [...names].sort();
}

// ─── Initial State ────────────────────────────────────────────────────────────

function makeInitialState(): ShellState {
  const home: string[] = ["~"];
  return {
    cwd: home,
    fs: {
      "~": { type: "dir", children: {} },
    },
    git: {
      initialized: false,
      currentBranch: "main",
      HEAD: null,
      staged: {},
      commits: [],
      objects: {},
      branches: { main: "" },
      remotes: {},
      mergeState: false,
      unmerged: {},
    },
    editorState: null,
  };
}

// ─── Command Executor ─────────────────────────────────────────────────────────

type CommandResult = {
  lines: TerminalLine[];
  newState: ShellState;
  completed?: boolean;
};

function runCommand(
  raw: string,
  state: ShellState,
  lineId: { v: number },
): CommandResult {
  const nextId = () => lineId.v++;
  const out = (
    text: string,
    kind: TerminalLine["kind"] = "output",
  ): TerminalLine => ({
    id: nextId(),
    text,
    kind,
  });

  const s = { ...state, git: { ...state.git } };
  const trimmed = raw.trim();
  if (!trimmed) return { lines: [], newState: s };

  const argv: string[] =
    (trimmed.match(/(?:[^\s"']+|"[^"]*"|'[^']*')+/g) as string[]) ?? [];
  const cmd = argv[0]?.toLowerCase() ?? "";

  // ── pwd ──
  if (cmd === "pwd") {
    const display = s.cwd.join("/").replace("~", "/home/user");
    return { lines: [out(display)], newState: s };
  }

  // ── ls / ls -la ──
  if (cmd === "ls") {
    const entries = listDir(s.fs, s.cwd);
    if (entries.length === 0) {
      return { lines: [out("(empty directory)")], newState: s };
    }
    const showHidden =
      argv.includes("-la") || argv.includes("-a") || argv.includes("-al");
    const toShow = showHidden
      ? [...(s.git.initialized ? [".git"] : []), ...entries]
      : entries;
    return { lines: [out(toShow.join("  "))], newState: s };
  }

  // ── cd ──
  if (cmd === "cd") {
    const target = argv[1];
    if (!target || target === "~") {
      return { lines: [], newState: { ...s, cwd: ["~"] } };
    }
    if (target === "..") {
      if (s.cwd.length <= 1)
        return { lines: [out("Already at root.")], newState: s };
      return { lines: [], newState: { ...s, cwd: s.cwd.slice(0, -1) } };
    }
    const newCwd = [...s.cwd, target];
    const node = getNode(s.fs, newCwd);
    if (!node || node.type !== "dir") {
      return {
        lines: [out(`cd: ${target}: No such directory`, "error")],
        newState: s,
      };
    }
    return { lines: [], newState: { ...s, cwd: newCwd } };
  }

  // ── mkdir ──
  if (cmd === "mkdir") {
    const name = argv[1];
    if (!name)
      return { lines: [out("Usage: mkdir <dirname>", "error")], newState: s };
    const newPath = [...s.cwd, name];
    const key = joinPath(newPath);
    if (s.fs[key])
      return {
        lines: [out(`mkdir: ${name}: already exists`, "error")],
        newState: s,
      };
    const newFs = { ...s.fs, [key]: { type: "dir" as const, children: {} } };
    return { lines: [], newState: { ...s, fs: newFs } };
  }

  // ── touch ──
  if (cmd === "touch") {
    const name = argv[1];
    if (!name)
      return { lines: [out("Usage: touch <filename>", "error")], newState: s };
    const key = joinPath([...s.cwd, name]);
    const newFs = { ...s.fs, [key]: { type: "file" as const, content: "" } };
    return { lines: [], newState: { ...s, fs: newFs } };
  }

  // ── echo (with redirection) ──
  if (cmd === "echo") {
    const fullCmd = trimmed.slice(5);
    const redirIdx = fullCmd.indexOf(">");
    if (redirIdx !== -1) {
      const text = fullCmd
        .slice(0, redirIdx)
        .trim()
        .replace(/^['"]|['"]$/g, "");
      const file = fullCmd.slice(redirIdx + 1).trim();
      const key = joinPath([...s.cwd, file]);
      const newFs = {
        ...s.fs,
        [key]: { type: "file" as const, content: text + "\n" },
      };
      return { lines: [], newState: { ...s, fs: newFs } };
    }
    const text = fullCmd.trim().replace(/^['"]|['"]$/g, "");
    return { lines: [out(text)], newState: s };
  }

  // ── cat ──
  if (cmd === "cat") {
    const name = argv[1];
    if (!name)
      return { lines: [out("Usage: cat <filename>", "error")], newState: s };
    const key = joinPath([...s.cwd, name]);
    const node = s.fs[key];
    if (!node || node.type !== "file") {
      return {
        lines: [out(`cat: ${name}: No such file`, "error")],
        newState: s,
      };
    }
    return {
      lines: [out((node as FileEntry).content || "(empty file)")],
      newState: s,
    };
  }

  // ── nano / edit ──
  if (cmd === "nano" || cmd === "edit") {
    const name = argv[1];
    if (!name)
      return { lines: [out(`Usage: ${cmd} <filename>`, "error")], newState: s };
    const key = joinPath([...s.cwd, name]);
    let content = "";
    if (s.fs[key]) {
      const node = s.fs[key];
      if (node.type !== "file") {
        return {
          lines: [out(`${cmd}: ${name} is a directory`, "error")],
          newState: s,
        };
      }
      content = (node as FileEntry).content;
    }
    // Set the editorState to open the UI overlay
    return {
      lines: [],
      newState: { ...s, editorState: { file: key, content } },
    };
  }

  // ── clear ──
  if (cmd === "clear") {
    return { lines: [out("__CLEAR__", "info")], newState: s };
  }

  // ── help ──
  if (cmd === "help") {
    const helpText = [
      "Available commands:",
      "  pwd                     – print working directory",
      "  ls [-la]               – list directory contents",
      "  cd <dir>               – change directory",
      "  mkdir <dir>            – create directory",
      "  touch <file>           – create empty file",
      "  echo 'text' > file     – write text to file",
      "  cat <file>             – view file contents",
      "  nano <file>            – open simplified text editor",
      "  clear                  – clear terminal",
      "",
      "Git commands:",
      "  git init               – initialize repository",
      "  git status             – working tree status",
      "  git add <file|.>       – stage file(s)",
      "  git commit -m 'msg'    – commit staged changes",
      "  git log                – show commit history",
      "  git branch             – list branches",
      "  git switch -c <name>   – create & switch branch",
      "  git remote -v          – list remotes",
      "  git remote add <n> <url>  – add remote",
      "  git diff               – show unstaged changes",
    ].join("\n");
    return { lines: [out(helpText, "info")], newState: s };
  }

  // ── git ──
  if (cmd === "git") {
    const sub = argv[1]?.toLowerCase();

    // git init
    if (sub === "init") {
      if (s.git.initialized) {
        return {
          lines: [
            out(
              `Reinitialized existing Git repository in ${cwdKey(s.cwd)}/.git/`,
            ),
          ],
          newState: s,
        };
      }
      const newGit: GitRepo = { ...s.git, initialized: true };
      return {
        lines: [
          out(
            `Initialized empty Git repository in ${cwdKey(s.cwd)}/.git/`,
            "success",
          ),
        ],
        newState: { ...s, git: newGit },
        completed: true,
      };
    }

    if (!s.git.initialized) {
      return {
        lines: [
          out(
            "fatal: not a git repository (or any of the parent directories): .git",
            "error",
          ),
        ],
        newState: s,
      };
    }

    // git status
    if (sub === "status") {
      const allFiles: string[] = [];
      const prefix = cwdKey(s.cwd) + "/";
      for (const key of Object.keys(s.fs)) {
        if (key.startsWith(prefix) && (s.fs[key] as FsNode).type === "file") {
          allFiles.push(key.slice(prefix.length));
        }
      }
      // Bug fix #1 & #2: use slice() not replace() so paths with repeated
      // segments are stripped correctly, and compare relative names consistently.
      const stagedRelative = new Set(
        Object.keys(s.git.staged)
          .filter((k) => k.startsWith(prefix))
          .map((k) => k.slice(prefix.length)),
      );
      const untracked = allFiles.filter((f) => !stagedRelative.has(f));
      const stagedFiles = [...stagedRelative];
      const unmergedFiles = Object.keys(s.git.unmerged || {});
      const lines: TerminalLine[] = [];
      lines.push(out(`On branch ${s.git.currentBranch}`));
      if (s.git.mergeState)
        lines.push(out("You have unmerged paths.", "error"));
      if (s.git.HEAD && !s.git.mergeState) lines.push(out(""));

      if (unmergedFiles.length > 0) {
        lines.push(out("Unmerged paths:", "error"));
        lines.push(
          out('  (use "git add <file>..." to mark resolution)', "info"),
        );
        unmergedFiles.forEach((f) => {
          const relName = f.startsWith(prefix) ? f.slice(prefix.length) : f;
          lines.push(out(`  both modified:   ${relName}`, "error"));
        });
      }

      if (stagedFiles.length > 0) {
        lines.push(out("Changes to be committed:", "success"));
        stagedFiles.forEach((f) =>
          lines.push(out(`  new file:   ${f}`, "success")),
        );
      }
      if (untracked.length > 0) {
        lines.push(out("Untracked files:", "error"));
        untracked.forEach((f) => lines.push(out(`  ${f}`, "error")));
      }
      if (stagedFiles.length === 0 && untracked.length === 0) {
        lines.push(out("nothing to commit, working tree clean"));
      }
      return { lines, newState: s };
    }

    // git add
    if (sub === "add") {
      const target = argv[2];
      if (!target)
        return {
          lines: [out("Nothing specified. Did you mean 'git add .'?", "error")],
          newState: s,
        };
      const newStaged = { ...s.git.staged };
      let newlyAdded = 0;
      if (target === ".") {
        const prefix = cwdKey(s.cwd) + "/";
        for (const [k, v] of Object.entries(s.fs)) {
          if (
            k.startsWith(prefix) &&
            (v as FsNode).type === "file" &&
            !(k in s.git.staged)
          ) {
            newStaged[k] = (v as FileEntry).content;
            newlyAdded++;
          }
        }
        // Bug fix #3: also update content of already-staged files that changed
        for (const [k, v] of Object.entries(s.fs)) {
          if (
            k.startsWith(prefix) &&
            (v as FsNode).type === "file" &&
            k in s.git.staged
          ) {
            newStaged[k] = (v as FileEntry).content;
          }
        }
      } else {
        const key = joinPath([...s.cwd, target]);
        const node = s.fs[key];
        if (!node || node.type !== "file") {
          return {
            lines: [
              out(
                `fatal: pathspec '${target}' did not match any files`,
                "error",
              ),
            ],
            newState: s,
          };
        }
        if (!(key in s.git.staged)) newlyAdded++;
        newStaged[key] = (node as FileEntry).content;
      }
      // Bug fix #3: report newly-added count, not cumulative total
      const addedMsg =
        newlyAdded > 0
          ? `${newlyAdded} file(s) staged.`
          : "Nothing new to stage (already up to date).";

      const newUnmerged = { ...(s.git.unmerged || {}) };
      for (const stagedKey of Object.keys(newStaged)) {
        if (newUnmerged[stagedKey]) delete newUnmerged[stagedKey];
      }

      return {
        lines: [out(addedMsg, "success")],
        newState: {
          ...s,
          git: { ...s.git, staged: newStaged, unmerged: newUnmerged },
        },
      };
    }

    // git commit
    if (sub === "commit") {
      if (s.git.mergeState) {
        // Check if unmerged files exist
        if (Object.keys(s.git.unmerged || {}).length > 0) {
          return {
            lines: [
              out(
                "error: Committing is not possible because you have unmerged files.",
                "error",
              ),
            ],
            newState: s,
          };
        }
        // Validate that the markers are actually gone in the staged files
        for (const [key, content] of Object.entries(s.git.staged)) {
          if (content.includes("<<<<<<<")) {
            return {
              lines: [
                out(
                  `error: File '${key}' still contains conflict markers.`,
                  "error",
                ),
              ],
              newState: s,
            };
          }
        }
      }

      if (Object.keys(s.git.staged).length === 0) {
        return {
          lines: [out("nothing to commit, working tree clean", "error")],
          newState: s,
        };
      }
      const mIdx = argv.indexOf("-m");
      // Bug fix #4: take only the single next token as the message (argv tokeniser
      // already splits quoted strings into one token), instead of joining all
      // remaining args which breaks multi-flag commits like: git commit -m 'msg' --amend
      const rawMsg = mIdx !== -1 ? (argv[mIdx + 1] ?? "") : "";
      const message = rawMsg.replace(/^['"]|['"]$/g, "").trim() || "no message";
      const stagedCount = Object.keys(s.git.staged).length;
      const hash = shortHash();
      const tree: Record<string, string> = {};
      for (const k of Object.keys(s.git.staged)) {
        tree[k] = shortHash();
      }
      const commit: GitCommit = {
        hash,
        message,
        author: "learner <learner@atelier.dev>",
        timestamp: new Date().toLocaleString(),
        tree,
        parent: s.git.HEAD,
      };
      const newCommits = [...s.git.commits, commit];
      const newBranches = { ...s.git.branches, [s.git.currentBranch]: hash };
      return {
        lines: [
          out(`[${s.git.currentBranch} ${hash}] ${message}`, "success"),
          out(` ${stagedCount} file(s) changed`),
        ],
        newState: {
          ...s,
          git: {
            ...s.git,
            staged: {},
            commits: newCommits,
            HEAD: hash,
            branches: newBranches,
            mergeState: false,
            unmerged: {},
          },
        },
      };
    }

    // git log
    if (sub === "log") {
      if (s.git.commits.length === 0) {
        return {
          lines: [
            out("fatal: your current branch has no commits yet", "error"),
          ],
          newState: s,
        };
      }
      const lines: TerminalLine[] = [];
      [...s.git.commits].reverse().forEach((c) => {
        lines.push(out(`commit ${c.hash}`, "success"));
        lines.push(out(`Author: ${c.author}`));
        lines.push(out(`Date:   ${c.timestamp}`));
        lines.push(out(`\n    ${c.message}\n`));
      });
      return { lines, newState: s };
    }

    // git branch
    if (sub === "branch") {
      const newBranchName = argv[2];
      if (newBranchName) {
        const newBranches = {
          ...s.git.branches,
          [newBranchName]: s.git.HEAD ?? "",
        };
        return {
          lines: [out(`Branch '${newBranchName}' created.`, "success")],
          newState: { ...s, git: { ...s.git, branches: newBranches } },
        };
      }
      const lines = Object.keys(s.git.branches).map((b) =>
        out(b === s.git.currentBranch ? `* ${b}` : `  ${b}`),
      );
      return { lines, newState: s };
    }

    // git switch / checkout
    if (sub === "switch" || sub === "checkout") {
      const createFlag = argv.includes("-c") || argv.includes("-b");
      // Bug fix #5: find the flag index first, then take the very next token as
      // the branch name.  For plain `git switch <branch>` the name is at argv[2].
      let branchName: string | undefined;
      if (createFlag) {
        const flagIdx =
          argv.indexOf("-c") !== -1 ? argv.indexOf("-c") : argv.indexOf("-b");
        branchName = argv[flagIdx + 1];
      } else {
        // `git switch <name>` or `git checkout <name>`
        branchName = argv[2];
      }
      if (!branchName)
        return {
          lines: [out("Usage: git switch [-c] <branch-name>", "error")],
          newState: s,
        };
      if (!createFlag && !s.git.branches[branchName]) {
        return {
          lines: [
            out(
              `error: pathspec '${branchName}' did not match any branch known to git`,
              "error",
            ),
          ],
          newState: s,
        };
      }
      const newBranches = createFlag
        ? { ...s.git.branches, [branchName]: s.git.HEAD ?? "" }
        : s.git.branches;
      return {
        lines: [
          out(
            `Switched to ${createFlag ? "a new " : ""}branch '${branchName}'`,
            "success",
          ),
        ],
        newState: {
          ...s,
          git: { ...s.git, currentBranch: branchName, branches: newBranches },
        },
      };
    }

    // git remote
    // Bug fix #6: argv layout is [git, remote, <sub>, ...]
    // so argv[2] is the subcommand/flag (-v | add), argv[3] is name, argv[4] is url.
    if (sub === "remote") {
      const rsub = argv[2]; // e.g. "-v" | "add" | undefined
      if (!rsub || rsub === "-v") {
        if (Object.keys(s.git.remotes).length === 0) {
          return { lines: [out("(no remotes configured)")], newState: s };
        }
        const lines = Object.entries(s.git.remotes).flatMap(([name, url]) => [
          out(`${name}\t${url} (fetch)`),
          out(`${name}\t${url} (push)`),
        ]);
        return { lines, newState: s };
      }
      if (rsub === "add") {
        const rName = argv[3];
        const rUrl = argv[4];
        if (!rName || !rUrl) {
          return {
            lines: [out("Usage: git remote add <name> <url>", "error")],
            newState: s,
          };
        }
        const newRemotes = { ...s.git.remotes, [rName]: rUrl };
        return {
          lines: [out(`Remote '${rName}' added.`, "success")],
          newState: { ...s, git: { ...s.git, remotes: newRemotes } },
        };
      }
      return {
        lines: [out(`git remote: '${rsub}' is not a remote command.`, "error")],
        newState: s,
      };
    }

    // git diff
    if (sub === "diff") {
      const prefix = cwdKey(s.cwd) + "/";
      const unstagedFiles: string[] = [];
      for (const k of Object.keys(s.fs)) {
        if (
          k.startsWith(prefix) &&
          (s.fs[k] as FsNode).type === "file" &&
          !s.git.staged[k]
        ) {
          unstagedFiles.push(k.slice(prefix.length));
        }
      }
      if (unstagedFiles.length === 0)
        return { lines: [out("(no unstaged changes)")], newState: s };
      const lines = unstagedFiles.flatMap((f) => [
        out(`diff --git a/${f} b/${f}`, "info"),
        out(`+++ b/${f}`, "success"),
      ]);
      return { lines, newState: s };
    }

    // git push
    if (sub === "push") {
      if (Object.keys(s.git.remotes).length === 0) {
        return {
          lines: [out("fatal: No configured push destination.", "error")],
          newState: s,
        };
      }
      return {
        lines: [
          out(`Branch '${s.git.currentBranch}' pushed to remote.`, "success"),
        ],
        newState: s,
        completed: true,
      };
    }

    // git merge
    if (sub === "merge") {
      const target = argv[2];
      if (!target)
        return {
          lines: [out("Usage: git merge <branch>", "error")],
          newState: s,
        };

      if (target === "conflict-branch") {
        if (s.git.mergeState) {
          return {
            lines: [
              out(
                "fatal: You have not concluded your merge (MERGE_HEAD exists).",
                "error",
              ),
            ],
            newState: s,
          };
        }

        // Inject a simulated conflict
        const prefix = cwdKey(s.cwd) + "/";
        const conflictKey = prefix + "app.js";
        const conflictContent = `<<<<<<< HEAD\nconsole.log("Main branch initialized");\n=======\nconsole.log("Feature branch initialized");\n>>>>>>> conflict-branch\n`;
        const newFs = {
          ...s.fs,
          [conflictKey]: { type: "file" as const, content: conflictContent },
        };
        const newUnmerged = { ...(s.git.unmerged || {}), [conflictKey]: true };

        return {
          lines: [
            out(`Auto-merging app.js`),
            out(`CONFLICT (content): Merge conflict in app.js`, "error"),
            out(
              `Automatic merge failed; fix conflicts and then commit the result.`,
              "error",
            ),
          ],
          newState: {
            ...s,
            fs: newFs,
            git: {
              ...s.git,
              mergeState: true,
              unmerged: newUnmerged,
            },
          },
        };
      }

      if (!s.git.branches[target]) {
        return {
          lines: [
            out(`merge: ${target} – not something we can merge`, "error"),
          ],
          newState: s,
        };
      }
      return {
        lines: [
          out(
            `Merging '${target}' into '${s.git.currentBranch}'... Fast-forward`,
            "success",
          ),
        ],
        newState: s,
        completed: true,
      };
    }

    // git rebase
    if (sub === "rebase") {
      const target = argv[2];
      if (target === "--continue") {
        return {
          lines: [
            out(
              "Successfully rebased and updated refs/heads/" +
                s.git.currentBranch,
              "success",
            ),
          ],
          newState: s,
          completed: true,
        };
      }
      if (!target)
        return {
          lines: [out("Usage: git rebase <branch>", "error")],
          newState: s,
        };
      return {
        lines: [
          out(
            `Successfully rebased and updated refs/heads/${s.git.currentBranch}`,
            "success",
          ),
        ],
        newState: s,
        completed: true,
      };
    }

    return {
      lines: [
        out(
          `git: '${sub ?? ""}' is not a git command. See 'git help'.`,
          "error",
        ),
      ],
      newState: s,
    };
  }

  return {
    lines: [
      out(
        `${cmd}: command not found. Type 'help' for available commands.`,
        "error",
      ),
    ],
    newState: s,
  };
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export interface UseGitShellOptions {
  /** Called when a command marked completed:true is executed */
  onObjectiveComplete?: () => void;
  /** Slugs that require git init to be completed */
  requiresGitInit?: boolean;
}

export function useGitShell(options: UseGitShellOptions = {}) {
  const [shellState, setShellState] = useState<ShellState>(makeInitialState);
  const [lines, setLines] = useState<TerminalLine[]>([
    {
      id: 0,
      text: "Welcome to the Git Sandbox. Type 'help' to list commands.",
      kind: "info",
    },
  ]);
  const [history, setHistory] = useState<string[]>([]);
  const [historyIdx, setHistoryIdx] = useState(-1);
  const lineCounter = useRef(1);

  const nextId = useCallback(() => lineCounter.current++, []);

  const runCmd = useCallback(
    (raw: string) => {
      const trimmed = raw.trim();
      if (!trimmed) return;

      // Append command line
      const promptLine: TerminalLine = {
        id: nextId(),
        prompt: shellState.cwd.join("/"),
        text: trimmed,
        kind: "command",
      };

      const idRef = { v: lineCounter.current };
      const {
        lines: outputLines,
        newState,
        completed,
      } = runCommand(trimmed, shellState, idRef);
      // Bug fix #7: after runCommand, idRef.v has already been incremented for each
      // output line it produced. Use idRef.v directly as the next available ID
      // rather than re-computing from the output array length (which double-counts).
      lineCounter.current = idRef.v;

      // Handle clear
      if (outputLines.some((l) => l.text === "__CLEAR__")) {
        setLines([]);
        setShellState(newState);
        return;
      }

      setLines((prev) => [...prev, promptLine, ...outputLines]);
      setShellState(newState);
      setHistory((prev) => [trimmed, ...prev].slice(0, 100));
      setHistoryIdx(-1);

      if (completed) {
        options.onObjectiveComplete?.();
      }
    },
    [shellState, nextId, options],
  );

  const navigateHistory = useCallback(
    (dir: "up" | "down") => {
      if (dir === "up") {
        setHistoryIdx((prev) => Math.min(prev + 1, history.length - 1));
      } else {
        setHistoryIdx((prev) => Math.max(prev - 1, -1));
      }
    },
    [history.length],
  );

  const getHistoryEntry = useCallback(
    (idx: number) => (idx >= 0 ? (history[idx] ?? "") : ""),
    [history],
  );

  const resetShell = useCallback(() => {
    setShellState(makeInitialState());
    setLines([
      {
        id: nextId(),
        text: "Shell reset. Type 'help' for commands.",
        kind: "info",
      },
    ]);
    setHistory([]);
    setHistoryIdx(-1);
  }, [nextId]);

  const saveEditor = useCallback((content: string) => {
    setShellState((prev) => {
      if (!prev.editorState) return prev;
      const fileKey = prev.editorState.file;
      const newFs = {
        ...prev.fs,
        [fileKey]: { type: "file" as const, content },
      };
      return { ...prev, fs: newFs, editorState: null };
    });
  }, []);

  const closeEditor = useCallback(() => {
    setShellState((prev) => ({ ...prev, editorState: null }));
  }, []);

  return {
    lines,
    shellState,
    runCmd,
    resetShell,
    navigateHistory,
    getHistoryEntry,
    historyIdx,
    saveEditor,
    closeEditor,
  };
}
