import { describe, it, expect, beforeEach } from "vitest";
import { createInitialRepo, parseGitCommand, RepoState } from "./gitSimulator";

describe("gitSimulator", () => {
  let state: RepoState;

  beforeEach(() => {
    state = createInitialRepo();
  });

  it("should initialize with correct default state", () => {
    expect(state.commits.length).toBe(1);
    expect(state.commits[0].message).toBe("Initial commit");
    expect(state.branches.length).toBe(1);
    expect(state.branches[0].name).toBe("main");
    expect(state.HEAD).toBe("main");
    expect(state.conflicts.length).toBe(0);
  });

  it('should handle "git branch <name>"', () => {
    const result = parseGitCommand("git branch feature", state);
    expect(result.error).toBeUndefined();
    expect(result.newState.branches.length).toBe(2);
    expect(result.newState.branches[1].name).toBe("feature");
    expect(result.newState.branches[1].target).toBe(state.commits[0].id);
  });

  it("should error when creating an existing branch", () => {
    parseGitCommand("git branch feature", state);
    // Have to simulate applying state iteratively
    const res1 = parseGitCommand("git branch feature", state);
    const res2 = parseGitCommand("git branch feature", res1.newState);
    expect(res2.error).toContain("already exists");
  });

  it('should handle "git checkout <name>"', () => {
    const s1 = parseGitCommand("git branch feature", state).newState;
    const s2 = parseGitCommand("git checkout feature", s1).newState;
    expect(s2.HEAD).toBe("feature");
  });

  it('should handle "git checkout -b <name>"', () => {
    const result = parseGitCommand("git checkout -b new-feat", state);
    expect(result.error).toBeUndefined();
    expect(result.newState.branches.length).toBe(2);
    expect(result.newState.HEAD).toBe("new-feat");
  });

  it('should handle "git commit -m <msg>"', () => {
    const result = parseGitCommand('git commit -m "added stuff"', state);
    expect(result.error).toBeUndefined();
    expect(result.newState.commits.length).toBe(2);
    expect(result.newState.commits[1].message).toBe("added stuff");
    // Verify branch moved forward
    expect(result.newState.branches[0].target).toBe(
      result.newState.commits[1].id,
    );
  });

  it('should handle "git merge <branch>" without conflicts', () => {
    let current = state;
    current = parseGitCommand("git checkout -b feature", current).newState;
    current = parseGitCommand(
      'git commit -m "feature commit"',
      current,
    ).newState;
    current = parseGitCommand("git checkout main", current).newState;
    current = parseGitCommand("git merge feature", current).newState;

    expect(current.commits.length).toBe(3); // Initial, feature commit, merge commit
    expect(current.commits[2].message).toContain("Merge branch 'feature'");
  });

  it('should handle "git merge <branch>" with conflicts', () => {
    let current = state;
    current = parseGitCommand(
      "git checkout -b conflict-test",
      current,
    ).newState;
    current = parseGitCommand("git checkout main", current).newState;
    const mergeRes = parseGitCommand("git merge conflict-test", current); // merging into main

    expect(mergeRes.error).toContain("Automatic merge failed");
    expect(mergeRes.newState.conflicts.length).toBe(1);
    expect(mergeRes.newState.conflicts[0]).toBe("index.html");
  });

  it("should block commands when in conflict state", () => {
    let current = state;
    current = parseGitCommand(
      "git checkout -b conflict-test",
      current,
    ).newState;
    current = parseGitCommand("git checkout main", current).newState;
    const mergeRes = parseGitCommand("git merge conflict-test", current);

    expect(mergeRes.newState.conflicts.length).toBeGreaterThan(0);

    const blockedRes = parseGitCommand(
      "git checkout feature",
      mergeRes.newState,
    );
    expect(blockedRes.error).toBe(
      "You must resolve conflicts before executing other commands.",
    );
  });

  it("should resolve conflicts when committing", () => {
    let current = state;
    current = parseGitCommand(
      "git checkout -b conflict-test",
      current,
    ).newState;
    current = parseGitCommand("git checkout main", current).newState;
    current = parseGitCommand("git merge conflict-test", current).newState;

    expect(current.conflicts.length).toBeGreaterThan(0);

    // Simulating git add and git commit to resolve
    current = parseGitCommand("git add .", current).newState;
    const resolveRes = parseGitCommand('git commit -m "resolved"', current);

    expect(resolveRes.newState.conflicts.length).toBe(0);
  });
});
