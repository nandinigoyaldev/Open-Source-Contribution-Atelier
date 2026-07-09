import { VirtualFileSystem } from "./FileSystem";
import { VfsState, TerminalLine, VfsError, VfsDir, VfsFile } from "./types";

export class CommandParser {
  static nextLineId = 1;

  static out(text: string, kind: TerminalLine["kind"] = "output"): TerminalLine {
    return { id: this.nextLineId++, text, kind };
  }

  static parse(raw: string, state: VfsState): { lines: TerminalLine[]; newState: VfsState } {
    const trimmed = raw.trim();
    if (!trimmed) return { lines: [], newState: state };

    const argv = trimmed.match(/(?:[^\s"']+|"[^"]*"|'[^']*')+/g) || [];
    const cmd = argv[0]?.toLowerCase();

    try {
      switch (cmd) {
        case "pwd": {
          const display = state.cwd.join("/").replace("~", "/home/user");
          return { lines: [this.out(display)], newState: state };
        }
        case "cd": {
          const target = argv[1];
          if (!target || target === "~") return { lines: [], newState: { ...state, cwd: ["~"] } };
          const resolved = VirtualFileSystem.resolvePath(state.cwd, target);
          const node = VirtualFileSystem.getNode(state, resolved);
          if (!node || node.type !== "dir") throw new VfsError(`cd: ${target}: No such file or directory`);
          return { lines: [], newState: { ...state, cwd: resolved } };
        }
        case "mkdir": {
          if (!argv[1]) throw new VfsError("Usage: mkdir <dirname>");
          return { lines: [], newState: VirtualFileSystem.mkdir(state, argv[1]) };
        }
        case "touch": {
          if (!argv[1]) throw new VfsError("Usage: touch <filename>");
          return { lines: [], newState: VirtualFileSystem.touch(state, argv[1]) };
        }
        case "echo": {
          const fullCmd = trimmed.slice(5);
          const redirIdx = fullCmd.indexOf(">");
          if (redirIdx !== -1) {
            const text = fullCmd.slice(0, redirIdx).trim().replace(/^['"]|['"]$/g, "");
            const file = fullCmd.slice(redirIdx + 1).trim();
            return { lines: [], newState: VirtualFileSystem.write(state, file, text + "\n") };
          }
          const text = fullCmd.trim().replace(/^['"]|['"]$/g, "");
          return { lines: [this.out(text)], newState: state };
        }
        case "cat": {
          const target = argv[1];
          if (!target) throw new VfsError("Usage: cat <filename>");
          const resolved = VirtualFileSystem.resolvePath(state.cwd, target);
          const node = VirtualFileSystem.getNode(state, resolved);
          if (!node || node.type !== "file") throw new VfsError(`cat: ${target}: No such file`);
          return { lines: [this.out((node as VfsFile).content || "(empty file)")], newState: state };
        }
        case "rm": {
          const isRecursive = argv.includes("-r") || argv.includes("-rf");
          const targets = argv.filter((a) => a !== "rm" && !a.startsWith("-"));
          if (targets.length === 0) throw new VfsError("Usage: rm [-r] <file...>");
          let newState = state;
          const lines: TerminalLine[] = [];
          for (const target of targets) {
            try {
              newState = VirtualFileSystem.rm(newState, target, isRecursive);
            } catch (e: any) {
              lines.push(this.out(e.message, "error"));
            }
          }
          return { lines, newState };
        }
        case "cp": {
          const isRecursive = argv.includes("-r") || argv.includes("-R");
          const args = argv.filter((a) => a !== "cp" && !a.startsWith("-"));
          if (args.length !== 2) throw new VfsError("Usage: cp [-r] <source> <destination>");
          return { lines: [], newState: VirtualFileSystem.cp(state, args[0], args[1], isRecursive) };
        }
        case "mv": {
          const args = argv.filter((a) => a !== "mv" && !a.startsWith("-"));
          if (args.length !== 2) throw new VfsError("Usage: mv <source> <destination>");
          return { lines: [], newState: VirtualFileSystem.mv(state, args[0], args[1]) };
        }
        case "ls": {
          const showHidden = argv.includes("-la") || argv.includes("-a") || argv.includes("-al");
          const showLong = argv.includes("-la") || argv.includes("-al") || argv.includes("-l");
          const target = argv.filter(a => a !== "ls" && !a.startsWith("-"))[0] || ".";
          
          const resolved = VirtualFileSystem.resolvePath(state.cwd, target);
          const node = VirtualFileSystem.getNode(state, resolved);
          if (!node || node.type !== "dir") throw new VfsError(`ls: ${target}: No such file or directory`);
          
          let entries = Object.keys((node as VfsDir).children).sort();
          if (showHidden) entries = [".git", ...entries];

          if (entries.length === 0) return { lines: [this.out("(empty directory)")], newState: state };

          if (showLong) {
            const lines = entries.map(name => {
              if (name === ".git") return this.out(`drwxr-xr-x  -  learner  -  -  .git`);
              const child = (node as VfsDir).children[name];
              const typeStr = child.type === "dir" ? "d" : "-";
              const size = child.type === "file" ? child.size || 0 : 0;
              const date = new Date(child.modified || Date.now());
              const dateStr = `${date.toLocaleString("default", { month: "short" })} ${date.getDate().toString().padStart(2, " ")} ${date.getHours().toString().padStart(2, "0")}:${date.getMinutes().toString().padStart(2, "0")}`;
              return this.out(`${typeStr}rw-r--r--  1  learner  learner  ${size.toString().padStart(4, " ")}  ${dateStr}  ${name}`);
            });
            return { lines, newState: state };
          }
          return { lines: [this.out(entries.join("  "))], newState: state };
        }
        case "clear":
          return { lines: [this.out("__CLEAR__", "info")], newState: state };
        default:
          return { lines: [this.out(`${cmd}: command not found`, "error")], newState: state };
      }
    } catch (e: any) {
      if (e instanceof VfsError) {
        return { lines: [this.out(e.message, "error")], newState: state };
      }
      return { lines: [this.out(`Unexpected error: ${e.message}`, "error")], newState: state };
    }
  }
}
