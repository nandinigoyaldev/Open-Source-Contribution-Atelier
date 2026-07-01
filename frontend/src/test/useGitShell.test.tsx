import { renderHook, act } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { useGitShell } from "../hooks/useGitShell";

describe("useGitShell hook", () => {
  it("initializes with home directory and git uninitialized", () => {
    const { result } = renderHook(() => useGitShell());

    expect(result.current.shellState.cwd).toEqual(["~"]);
    expect(result.current.shellState.git.initialized).toBe(false);
  });

  it("handles basic commands: pwd, mkdir, touch, ls, cd, cat", () => {
    const { result } = renderHook(() => useGitShell());

    // pwd
    act(() => {
      result.current.runCmd("pwd");
    });
    expect(
      result.current.lines.some((l) => l.text.includes("/home/user")),
    ).toBe(true);

    // mkdir testdir
    act(() => {
      result.current.runCmd("mkdir testdir");
    });

    // cd testdir
    act(() => {
      result.current.runCmd("cd testdir");
    });
    expect(result.current.shellState.cwd).toEqual(["~", "testdir"]);

    // touch readme.md
    act(() => {
      result.current.runCmd("touch readme.md");
    });

    // ls
    act(() => {
      result.current.runCmd("ls");
    });
    expect(result.current.lines.some((l) => l.text.includes("readme.md"))).toBe(
      true,
    );

    // echo content > readme.md
    act(() => {
      result.current.runCmd("echo 'Hello Open Source' > readme.md");
    });

    // cat readme.md
    act(() => {
      result.current.runCmd("cat readme.md");
    });
    expect(
      result.current.lines.some((l) => l.text.includes("Hello Open Source")),
    ).toBe(true);
  });

  it("fails git commands if not initialized", () => {
    const { result } = renderHook(() => useGitShell());

    act(() => {
      result.current.runCmd("git status");
    });
    expect(
      result.current.lines.some((l) =>
        l.text.includes("fatal: not a git repository"),
      ),
    ).toBe(true);
  });

  it("handles git init, add, commit, branch, switch, and checkout", () => {
    const { result } = renderHook(() => useGitShell());

    // git init
    act(() => {
      result.current.runCmd("git init");
    });
    expect(result.current.shellState.git.initialized).toBe(true);
    expect(
      result.current.lines.some((l) =>
        l.text.includes("Initialized empty Git repository"),
      ),
    ).toBe(true);

    // git status when empty
    act(() => {
      result.current.runCmd("git status");
    });
    expect(
      result.current.lines.some((l) =>
        l.text.includes("nothing to commit, working tree clean"),
      ),
    ).toBe(true);

    // touch a.txt
    act(() => {
      result.current.runCmd("touch a.txt");
    });

    // git status shows untracked
    act(() => {
      result.current.runCmd("git status");
    });
    expect(
      result.current.lines.some((l) => l.text.includes("Untracked files:")),
    ).toBe(true);
    expect(result.current.lines.some((l) => l.text.includes("a.txt"))).toBe(
      true,
    );

    // git add a.txt
    act(() => {
      result.current.runCmd("git add a.txt");
    });
    expect(
      result.current.lines.some((l) => l.text.includes("1 file(s) staged")),
    ).toBe(true);

    // git status shows staged
    act(() => {
      result.current.runCmd("git status");
    });
    expect(
      result.current.lines.some((l) =>
        l.text.includes("Changes to be committed:"),
      ),
    ).toBe(true);
    expect(
      result.current.lines.some((l) => l.text.includes("new file:   a.txt")),
    ).toBe(true);

    // git commit -m "initial commit"
    act(() => {
      result.current.runCmd("git commit -m 'initial commit'");
    });
    expect(result.current.shellState.git.commits.length).toBe(1);
    expect(result.current.shellState.git.commits[0].message).toBe(
      "initial commit",
    );

    // git status shows clean again
    act(() => {
      result.current.runCmd("git status");
    });
    expect(
      result.current.lines.some((l) =>
        l.text.includes("nothing to commit, working tree clean"),
      ),
    ).toBe(true);

    // git branch feat
    act(() => {
      result.current.runCmd("git branch feat");
    });
    expect(result.current.shellState.git.branches.feat).toBeDefined();

    // git switch feat
    act(() => {
      result.current.runCmd("git switch feat");
    });
    expect(result.current.shellState.git.currentBranch).toBe("feat");

    // git switch -c feat2
    act(() => {
      result.current.runCmd("git switch -c feat2");
    });
    expect(result.current.shellState.git.currentBranch).toBe("feat2");
    expect(result.current.shellState.git.branches.feat2).toBeDefined();
  });
});
