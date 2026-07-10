import { useState, useEffect, useMemo } from "react";
import type { ShellState, FsNode } from "./useGitShell";

export interface AutocompleteSuggestion {
  text: string;
  completionText: string;
  type: "command" | "git-command" | "file" | "dir";
  description?: string;
}

const BASE_COMMANDS: Record<string, string> = {
  pwd: "print working directory",
  ls: "list directory contents",
  cd: "change directory",
  mkdir: "create directory",
  touch: "create empty file",
  echo: "write text to file",
  cat: "view file contents",
  nano: "open text editor",
  edit: "open text editor",
  clear: "clear terminal",
  help: "show help",
  git: "version control",
};

const GIT_COMMANDS: Record<string, string> = {
  init: "initialize repository",
  status: "working tree status",
  add: "stage file(s)",
  commit: "commit staged changes",
  log: "show commit history",
  branch: "list branches",
  switch: "create & switch branch",
  checkout: "switch branches or restore files",
  remote: "manage remotes",
  diff: "show unstaged changes",
  push: "push to remote",
  merge: "merge branches",
  rebase: "reapply commits",
};

function resolvePath(cwd: string[], path: string): string[] {
  if (!path) return [...cwd];
  const parts = path.split("/");
  let result = [...cwd];
  if (parts[0] === "~") {
    result = ["~"];
    parts.shift();
  }
  for (const p of parts) {
    if (p === "..") {
      if (result.length > 1) result.pop();
    } else if (p !== "." && p !== "") {
      result.push(p);
    }
  }
  return result;
}

function joinPath(parts: string[]): string {
  return parts.join("/") || "/";
}

export function useTerminalAutocomplete(
  inputVal: string,
  shellState: ShellState,
) {
  const [selectedIndex, setSelectedIndex] = useState(0);

  const suggestions = useMemo<AutocompleteSuggestion[]>(() => {
    if (!inputVal) return [];

    const words = inputVal.match(/\S+/g) || [];
    const isTrailingSpace = inputVal.endsWith(" ");
    const lastWord = isTrailingSpace ? "" : words[words.length - 1] || "";

    // Determine context
    const isFirstWord =
      words.length === 0 || (words.length === 1 && !isTrailingSpace);
    const isSecondWordGit =
      (words.length === 1 && isTrailingSpace && words[0] === "git") ||
      (words.length === 2 && !isTrailingSpace && words[0] === "git");

    const prefix = lastWord.toLowerCase();
    const results: AutocompleteSuggestion[] = [];

    if (isFirstWord) {
      Object.entries(BASE_COMMANDS).forEach(([cmd, desc]) => {
        if (cmd.startsWith(prefix)) {
          results.push({
            text: cmd,
            completionText:
              inputVal.slice(0, inputVal.length - prefix.length) + cmd + " ",
            type: "command",
            description: desc,
          });
        }
      });
    } else if (isSecondWordGit) {
      Object.entries(GIT_COMMANDS).forEach(([cmd, desc]) => {
        if (cmd.startsWith(prefix)) {
          results.push({
            text: cmd,
            completionText:
              inputVal.slice(0, inputVal.length - prefix.length) + cmd + " ",
            type: "git-command",
            description: desc,
          });
        }
      });
    } else {
      let searchDir = [...shellState.cwd];
      let searchPrefix = lastWord;

      if (lastWord.includes("/")) {
        const parts = lastWord.split("/");
        searchPrefix = parts.pop() || "";
        const dirStr = parts.join("/");
        searchDir = resolvePath(shellState.cwd, dirStr);
      }

      const cwdStr = joinPath(searchDir);
      const prefixKey = cwdStr + "/";

      const matchedNames = new Set<string>();
      const entryTypes = new Map<string, "file" | "dir">();

      if ("..".startsWith(searchPrefix) && searchDir.length > 1) {
        matchedNames.add("..");
        entryTypes.set("..", "dir");
      }

      for (const [key, node] of Object.entries(shellState.fs)) {
        if (key.startsWith(prefixKey)) {
          const rest = key.slice(prefixKey.length);
          const top = rest.split("/")[0];

          if (top && top.toLowerCase().startsWith(searchPrefix.toLowerCase())) {
            matchedNames.add(top);
            if (key === prefixKey + top) {
              entryTypes.set(top, (node as FsNode).type);
            } else {
              entryTypes.set(top, "dir");
            }
          }
        }
      }

      const cmd = words[0] || "";
      const dirsOnly = ["cd", "mkdir"].includes(cmd);

      [...matchedNames].sort().forEach((name) => {
        const type = entryTypes.get(name) || "file";
        if (dirsOnly && type !== "dir") return;

        const suffix = type === "dir" ? "/" : " ";
        results.push({
          text: name + (type === "dir" ? "/" : ""),
          completionText:
            inputVal.slice(0, inputVal.length - searchPrefix.length) +
            name +
            suffix,
          type: type,
          description: type === "dir" ? "Directory" : "File",
        });
      });
    }

    return results;
  }, [inputVal, shellState]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [suggestions]);

  return { suggestions, selectedIndex, setSelectedIndex };
}
