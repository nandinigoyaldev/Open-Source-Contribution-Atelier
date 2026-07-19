/**
 * Contextual Git cheat-sheet — resolve lesson/module → focused command list.
 * Does not change the sandbox allowlist; display-only helper.
 */

export type ContextualGitCommand = {
  id: string;
  name: string;
  command: string;
  description: string;
  example?: string;
};

export type GitCheatSheetMap = {
  defaultCommandIds: string[];
  modules: Record<string, string[]>;
  lessons: Record<string, string[]>;
  slugToModule?: Record<string, string>;
};

/** Catalog of beginner-safe commands (subset of common Git; allowlist-friendly). */
export const COMMAND_CATALOG: Record<string, ContextualGitCommand> = {
  "git-init": {
    id: "git-init",
    name: "Initialize repository",
    command: "git init",
    description: "Create a new Git repository in the current directory",
    example: "git init",
  },
  "git-status": {
    id: "git-status",
    name: "Check status",
    command: "git status",
    description: "Show modified, staged, and untracked files",
    example: "git status",
  },
  "git-add": {
    id: "git-add",
    name: "Stage changes",
    command: "git add <file>",
    description: "Add file changes to the staging area",
    example: "git add .\ngit add README.md",
  },
  "git-commit": {
    id: "git-commit",
    name: "Commit changes",
    command: "git commit -m 'message'",
    description: "Save staged changes with a message",
    example: "git commit -m 'feat: add readme'",
  },
  "git-log": {
    id: "git-log",
    name: "View history",
    command: "git log",
    description: "Show commit history",
    example: "git log --oneline",
  },
  "git-diff": {
    id: "git-diff",
    name: "View changes",
    command: "git diff",
    description: "Show unstaged (or staged) differences",
    example: "git diff\ngit diff --staged",
  },
  "git-branch": {
    id: "git-branch",
    name: "List branches",
    command: "git branch",
    description: "List local branches",
    example: "git branch\ngit branch -a",
  },
  "git-switch": {
    id: "git-switch",
    name: "Switch / create branch",
    command: "git switch <branch>",
    description: "Switch branches, or create with -c",
    example: "git switch main\ngit switch -c feat/add-readme",
  },
  "git-checkout": {
    id: "git-checkout",
    name: "Checkout branch",
    command: "git checkout <branch>",
    description: "Older way to switch or create branches",
    example: "git checkout -b feat/add-readme",
  },
  "git-merge": {
    id: "git-merge",
    name: "Merge branch",
    command: "git merge <branch>",
    description: "Merge another branch into the current branch",
    example: "git merge feat/add-readme",
  },
  "git-clone": {
    id: "git-clone",
    name: "Clone repository",
    command: "git clone <url>",
    description: "Copy a remote repository to your machine",
    example: "git clone https://github.com/org/repo.git",
  },
  "git-remote": {
    id: "git-remote",
    name: "List remotes",
    command: "git remote -v",
    description: "Show remote names and URLs",
    example: "git remote -v",
  },
  "git-fetch": {
    id: "git-fetch",
    name: "Fetch updates",
    command: "git fetch",
    description: "Download remote changes without merging",
    example: "git fetch origin",
  },
  "git-pull": {
    id: "git-pull",
    name: "Pull updates",
    command: "git pull",
    description: "Fetch and integrate remote changes",
    example: "git pull origin main",
  },
  "git-push": {
    id: "git-push",
    name: "Push commits",
    command: "git push",
    description: "Upload local commits to a remote",
    example: "git push -u origin feat/my-first-pr",
  },
  "git-rebase": {
    id: "git-rebase",
    name: "Rebase branch",
    command: "git rebase <branch>",
    description: "Replay commits onto another base branch",
    example: "git rebase main",
  },
};

export function idsToCommands(ids: string[]): ContextualGitCommand[] {
  const seen = new Set<string>();
  const result: ContextualGitCommand[] = [];
  for (const id of ids) {
    if (seen.has(id)) continue;
    const cmd = COMMAND_CATALOG[id];
    if (!cmd) continue;
    seen.add(id);
    result.push(cmd);
  }
  return result;
}

export function resolveModuleId(
  lessonSlug: string | undefined,
  moduleId: string | undefined,
  map: GitCheatSheetMap,
): string | undefined {
  if (moduleId && map.modules[moduleId]) return moduleId;
  if (lessonSlug && map.slugToModule?.[lessonSlug]) {
    return map.slugToModule[lessonSlug];
  }
  return undefined;
}

/**
 * Prefer lesson-specific commands, then module defaults, then global defaults.
 */
export function resolveContextualCommands(
  lessonSlug: string | undefined,
  moduleId: string | undefined,
  map: GitCheatSheetMap,
): {
  commands: ContextualGitCommand[];
  source: "lesson" | "module" | "default";
  resolvedModuleId?: string;
} {
  if (lessonSlug && map.lessons[lessonSlug]?.length) {
    return {
      commands: idsToCommands(map.lessons[lessonSlug]),
      source: "lesson",
      resolvedModuleId: resolveModuleId(lessonSlug, moduleId, map),
    };
  }

  const resolvedModuleId = resolveModuleId(lessonSlug, moduleId, map);
  if (resolvedModuleId && map.modules[resolvedModuleId]?.length) {
    return {
      commands: idsToCommands(map.modules[resolvedModuleId]),
      source: "module",
      resolvedModuleId,
    };
  }

  return {
    commands: idsToCommands(map.defaultCommandIds),
    source: "default",
    resolvedModuleId,
  };
}

export function moduleIdFromFilePath(filePath?: string): string | undefined {
  if (!filePath) return undefined;
  const match = filePath.replace(/\\/g, "/").match(/(module-[\w-]+)/);
  return match?.[1];
}

let cachedMap: GitCheatSheetMap | null = null;

export async function loadGitCheatSheetMap(
  url = "/content/git-cheatsheet-map.json",
): Promise<GitCheatSheetMap> {
  if (cachedMap) return cachedMap;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to load git cheat-sheet map (${res.status})`);
  }
  cachedMap = (await res.json()) as GitCheatSheetMap;
  return cachedMap;
}

/** Test helper — clear fetch cache */
export function clearGitCheatSheetMapCache(): void {
  cachedMap = null;
}
