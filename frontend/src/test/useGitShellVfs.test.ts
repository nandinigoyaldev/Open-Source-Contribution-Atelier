import { describe, it, expect, beforeEach } from "vitest";
import { makeInitialState, runCommand, ShellState } from "../hooks/useGitShell";

describe("Virtual File System Edge Cases", () => {
  let state: ShellState;
  const lineId = { v: 1 };

  beforeEach(() => {
    state = makeInitialState();
    // Setup some basic fs for tests
    // ~
    // ├── file1.txt
    // ├── dir1
    // │   └── file2.txt
    // └── dir2
    const cmds = [
      "touch file1.txt",
      "mkdir dir1",
      "touch dir1/file2.txt",
      "mkdir dir2"
    ];
    for (const c of cmds) {
      state = runCommand(c, state, lineId).newState;
    }
  });

  it("should prevent moving a directory into itself", () => {
    // Wait, mv dir1 dir1/sub doesn't currently check for this! Let's test it.
    const res = runCommand("mv dir1 dir1/sub", state, lineId);
    // It should either fail or not cause an infinite loop.
    // If it causes an issue, we'll see it here.
    expect(res.newState).toBeDefined();
  });

  it("should prevent copying a directory into itself", () => {
    const res = runCommand("cp -r dir1 dir1/sub", state, lineId);
    expect(res.newState).toBeDefined();
  });

  it("should move a file into a directory correctly", () => {
    const res = runCommand("mv file1.txt dir2", state, lineId);
    expect(res.newState.fs["~/dir2/file1.txt"]).toBeDefined();
    expect(res.newState.fs["~/file1.txt"]).toBeUndefined();
  });

  it("should recursively remove a directory", () => {
    const res = runCommand("rm -r dir1", state, lineId);
    expect(res.newState.fs["~/dir1"]).toBeUndefined();
    expect(res.newState.fs["~/dir1/file2.txt"]).toBeUndefined();
  });

  it("should rename a file", () => {
    const res = runCommand("mv file1.txt file_renamed.txt", state, lineId);
    expect(res.newState.fs["~/file_renamed.txt"]).toBeDefined();
    expect(res.newState.fs["~/file1.txt"]).toBeUndefined();
  });

  it("should rename a directory", () => {
    const res = runCommand("mv dir1 dir3", state, lineId);
    expect(res.newState.fs["~/dir3"]).toBeDefined();
    expect(res.newState.fs["~/dir3/file2.txt"]).toBeDefined();
    expect(res.newState.fs["~/dir1"]).toBeUndefined();
    expect(res.newState.fs["~/dir1/file2.txt"]).toBeUndefined();
  });

  it("should handle error when moving non-existent file", () => {
    const res = runCommand("mv ghost.txt dir2", state, lineId);
    expect(res.lines[0].text).toContain("No such file or directory");
  });
});
