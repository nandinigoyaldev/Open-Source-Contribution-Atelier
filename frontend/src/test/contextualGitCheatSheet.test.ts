import { describe, expect, it } from "vitest";
import {
  resolveContextualCommands,
  resolveModuleId,
  moduleIdFromFilePath,
  idsToCommands,
  type GitCheatSheetMap,
} from "../lib/contextualGitCheatSheet";

const SAMPLE_MAP: GitCheatSheetMap = {
  defaultCommandIds: ["git-status", "git-init"],
  modules: {
    "module-2": ["git-init", "git-status", "git-branch", "git-switch"],
    "module-3": ["git-clone", "git-remote", "git-push"],
  },
  lessons: {
    branches: ["git-branch", "git-switch", "git-status"],
    remotes: ["git-remote", "git-push", "git-pull"],
  },
  slugToModule: {
    branches: "module-2",
    remotes: "module-2",
    "github-repositories": "module-3",
  },
};

describe("idsToCommands", () => {
  it("maps known ids and skips unknown", () => {
    const cmds = idsToCommands(["git-status", "nope", "git-init"]);
    expect(cmds.map((c) => c.id)).toEqual(["git-status", "git-init"]);
  });
});

describe("moduleIdFromFilePath", () => {
  it("extracts module id from curriculum filePath", () => {
    expect(moduleIdFromFilePath("module-2/branches.md")).toBe("module-2");
    expect(moduleIdFromFilePath("module-3/forks.md")).toBe("module-3");
  });
});

describe("resolveModuleId", () => {
  it("prefers explicit moduleId", () => {
    expect(resolveModuleId("branches", "module-3", SAMPLE_MAP)).toBe(
      "module-3",
    );
  });

  it("falls back to slugToModule", () => {
    expect(resolveModuleId("github-repositories", undefined, SAMPLE_MAP)).toBe(
      "module-3",
    );
  });
});

describe("resolveContextualCommands", () => {
  it("uses lesson-specific commands when available", () => {
    const result = resolveContextualCommands(
      "branches",
      "module-2",
      SAMPLE_MAP,
    );
    expect(result.source).toBe("lesson");
    expect(result.commands.map((c) => c.command)).toEqual([
      "git branch",
      "git switch <branch>",
      "git status",
    ]);
  });

  it("falls back to module commands", () => {
    const result = resolveContextualCommands(
      "github-repositories",
      undefined,
      SAMPLE_MAP,
    );
    expect(result.source).toBe("module");
    expect(result.resolvedModuleId).toBe("module-3");
    expect(result.commands.some((c) => c.id === "git-clone")).toBe(true);
  });

  it("falls back to defaults", () => {
    const result = resolveContextualCommands(
      "unknown-lesson",
      undefined,
      SAMPLE_MAP,
    );
    expect(result.source).toBe("default");
    expect(result.commands.map((c) => c.id)).toEqual([
      "git-status",
      "git-init",
    ]);
  });

  it("module-2 vs module-3 return different focused sets", () => {
    const m2 = resolveContextualCommands(undefined, "module-2", SAMPLE_MAP);
    const m3 = resolveContextualCommands(undefined, "module-3", SAMPLE_MAP);
    expect(m2.commands.map((c) => c.id)).not.toEqual(
      m3.commands.map((c) => c.id),
    );
    expect(m2.commands.some((c) => c.id === "git-branch")).toBe(true);
    expect(m3.commands.some((c) => c.id === "git-remote")).toBe(true);
  });
});
