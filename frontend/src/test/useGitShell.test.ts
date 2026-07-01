import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { useGitShell } from "../hooks/useGitShell";

const localStorageMock = (function () {
  let store: Record<string, string> = {};
  return {
    getItem: function (key: string) {
      return store[key] || null;
    },
    setItem: function (key: string, value: string) {
      store[key] = value.toString();
    },
    removeItem: function (key: string) {
      delete store[key];
    },
    clear: function () {
      store = {};
    },
  };
})();

Object.defineProperty(window, "localStorage", { value: localStorageMock });

describe("useGitShell - Merge Conflict Edge Cases", () => {
  it("should initialize a git repo", () => {
    const { result } = renderHook(() => useGitShell());

    act(() => {
      result.current.runCmd("git init");
    });

    expect(result.current.shellState.git.initialized).toBe(true);
  });

  it("should enter merge state and inject conflict markers on git merge conflict-branch", () => {
    const { result } = renderHook(() => useGitShell());

    act(() => {
      result.current.runCmd("git init");
    });
    act(() => {
      result.current.runCmd("git merge conflict-branch");
    });

    expect(result.current.shellState.git.mergeState).toBe(true);
    expect(Object.keys(result.current.shellState.git.unmerged || {})).toContain(
      "~/app.js",
    );

    const appJsNode = result.current.shellState.fs["~/app.js"];
    expect(appJsNode.type).toBe("file");
    expect((appJsNode as { content: string }).content).toContain(
      "<<<<<<< HEAD",
    );
  });

  it("should prevent committing if unmerged files exist", () => {
    const { result } = renderHook(() => useGitShell());

    act(() => {
      result.current.runCmd("git init");
    });
    act(() => {
      result.current.runCmd("git merge conflict-branch");
    });
    act(() => {
      result.current.runCmd("git add app.js");
    });
    act(() => {
      result.current.runCmd('git commit -m "Try to commit"');
    });

    const lines = result.current.lines;
    const lastLine = lines[lines.length - 1];

    expect(lastLine.text).toContain("error: File");
    expect(lastLine.text).toContain("still contains conflict markers");
    expect(result.current.shellState.git.mergeState).toBe(true);
  });

  it("should allow committing after conflict markers are removed via editor", () => {
    const { result } = renderHook(() => useGitShell());

    act(() => {
      result.current.runCmd("git init");
    });
    act(() => {
      result.current.runCmd("git merge conflict-branch");
    });
    act(() => {
      result.current.runCmd("nano app.js");
    });
    act(() => {
      result.current.saveEditor('console.log("Merged code");');
    });
    act(() => {
      result.current.runCmd("git add app.js");
    });
    act(() => {
      result.current.runCmd('git commit -m "Resolved conflict"');
    });

    expect(result.current.shellState.git.mergeState).toBe(false);
    expect(result.current.shellState.git.commits.length).toBe(1);
  });

  it("EDGE CASE: should prevent running git merge if already in a merge state", () => {
    const { result } = renderHook(() => useGitShell());

    act(() => {
      result.current.runCmd("git init");
    });
    act(() => {
      result.current.runCmd("git merge conflict-branch");
    });

    expect(result.current.shellState.git.mergeState).toBe(true);

    act(() => {
      result.current.runCmd("git merge conflict-branch");
    });

    const lines = result.current.lines;
    const lastLine = lines[lines.length - 1];

    expect(lastLine.text).toBe(
      "fatal: You have not concluded your merge (MERGE_HEAD exists).",
    );
  });
});
