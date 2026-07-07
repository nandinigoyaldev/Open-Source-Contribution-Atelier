import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { useTerminalAutocomplete } from "../hooks/useTerminalAutocomplete";
import type { ShellState } from "../hooks/useGitShell";

const mockShellState: ShellState = {
  cwd: ["~"],
  fs: {
    "~": { type: "dir", children: {} },
    "~/file.txt": { type: "file", content: "" },
    "~/folder": { type: "dir", children: {} },
    "~/folder/script.js": { type: "file", content: "" },
    "~/folder/subfolder": { type: "dir", children: {} },
    "~/app.js": { type: "file", content: "" },
    "~/app_test.js": { type: "file", content: "" },
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
  },
};

describe("useTerminalAutocomplete", () => {
  it("should return empty suggestions for empty input", () => {
    const { result } = renderHook(() =>
      useTerminalAutocomplete("", mockShellState)
    );
    expect(result.current.suggestions).toEqual([]);
  });

  it("should suggest base commands when typing the first word", () => {
    const { result } = renderHook(() =>
      useTerminalAutocomplete("c", mockShellState)
    );
    const texts = result.current.suggestions.map((s) => s.text);
    expect(texts).toContain("cd");
    expect(texts).toContain("cat");
    expect(texts).toContain("clear");
    expect(result.current.suggestions[0].type).toBe("command");
  });

  it("should suggest git commands when typing 'git '", () => {
    const { result } = renderHook(() =>
      useTerminalAutocomplete("git ", mockShellState)
    );
    const texts = result.current.suggestions.map((s) => s.text);
    expect(texts).toContain("status");
    expect(texts).toContain("commit");
    expect(result.current.suggestions[0].type).toBe("git-command");
  });

  it("should filter git commands based on prefix", () => {
    const { result } = renderHook(() =>
      useTerminalAutocomplete("git s", mockShellState)
    );
    const texts = result.current.suggestions.map((s) => s.text);
    expect(texts).toContain("status");
    expect(texts).toContain("switch");
    expect(texts).not.toContain("commit");
  });

  it("should suggest files and directories for generic commands like 'cat '", () => {
    const { result } = renderHook(() =>
      useTerminalAutocomplete("cat ", mockShellState)
    );
    const texts = result.current.suggestions.map((s) => s.text);
    expect(texts).toContain("file.txt");
    expect(texts).toContain("folder/");
    expect(texts).toContain("app.js");
  });

  it("should filter files based on prefix", () => {
    const { result } = renderHook(() =>
      useTerminalAutocomplete("cat app", mockShellState)
    );
    const texts = result.current.suggestions.map((s) => s.text);
    expect(texts).toEqual(["app.js", "app_test.js"]);
    
    // Check completion text
    expect(result.current.suggestions[0].completionText).toBe("cat app.js ");
  });

  it("should only suggest directories for 'cd ' command", () => {
    const { result } = renderHook(() =>
      useTerminalAutocomplete("cd ", mockShellState)
    );
    const texts = result.current.suggestions.map((s) => s.text);
    expect(texts).toContain("folder/");
    expect(texts).not.toContain("file.txt");
  });

  it("should suggest children when path contains a slash", () => {
    const { result } = renderHook(() =>
      useTerminalAutocomplete("cat folder/", mockShellState)
    );
    const texts = result.current.suggestions.map((s) => s.text);
    expect(texts).toContain("script.js");
    expect(texts).toContain("subfolder/");
  });

  it("should resolve '..' in paths correctly", () => {
    const deepState = { ...mockShellState, cwd: ["~", "folder", "subfolder"] };
    const { result } = renderHook(() =>
      useTerminalAutocomplete("cat ../", deepState)
    );
    const texts = result.current.suggestions.map((s) => s.text);
    expect(texts).toContain("script.js");
    expect(texts).toContain("subfolder/");
    // Also tests completion text replacement
    const scriptSugg = result.current.suggestions.find(s => s.text === "script.js");
    expect(scriptSugg?.completionText).toBe("cat ../script.js ");
  });

  it("should include '..' for directories when nested", () => {
    const deepState = { ...mockShellState, cwd: ["~", "folder"] };
    const { result } = renderHook(() =>
      useTerminalAutocomplete("cd .", deepState)
    );
    const texts = result.current.suggestions.map((s) => s.text);
    expect(texts).toContain("../");
  });

  it("should handle absolute paths from ~", () => {
    const deepState = { ...mockShellState, cwd: ["~", "folder"] };
    const { result } = renderHook(() =>
      useTerminalAutocomplete("cat ~/a", deepState)
    );
    const texts = result.current.suggestions.map((s) => s.text);
    expect(texts).toContain("app.js");
    expect(texts).toContain("app_test.js");
  });
});
