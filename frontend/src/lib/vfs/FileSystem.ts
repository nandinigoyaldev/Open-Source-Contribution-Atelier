import { VfsState, VfsDir, VfsFile, VfsNode, VfsError } from "./types";

export class VirtualFileSystem {
  static createInitialState(): VfsState {
    const now = Date.now();
    return {
      cwd: ["~"],
      root: { type: "dir", children: {}, created: now, modified: now },
    };
  }

  static cloneNode(node: VfsNode): VfsNode {
    if (node.type === "file") return { ...node };
    const newChildren: Record<string, VfsNode> = {};
    for (const [k, v] of Object.entries(node.children)) {
      newChildren[k] = this.cloneNode(v);
    }
    return { ...node, children: newChildren };
  }

  static resolvePath(cwd: string[], path: string): string[] {
    const parts = path.split("/").filter(Boolean);
    const result = path.startsWith("~") ? [] : [...cwd];

    for (const part of parts) {
      if (part === "~") {
        result.length = 0;
        result.push("~");
      } else if (part === ".") continue;
      else if (part === "..") {
        if (result.length > 1) result.pop(); // Prevent going above ~
      } else result.push(part);
    }
    return result.length === 0 ? ["~"] : result;
  }

  static getNode(state: VfsState, pathParts: string[]): VfsNode | null {
    let curr: VfsNode = state.root;
    for (const seg of pathParts) {
      if (seg === "~") continue;
      if (curr.type !== "dir") return null;
      curr = curr.children[seg];
      if (!curr) return null;
    }
    return curr;
  }

  static setNode(
    state: VfsState,
    pathParts: string[],
    node: VfsNode | null,
  ): VfsState {
    if (pathParts.length === 1 && pathParts[0] === "~") {
      if (!node || node.type !== "dir")
        throw new VfsError("Cannot overwrite root directory");
      return { ...state, root: node };
    }

    const newRoot = this.cloneNode(state.root) as VfsDir;
    let curr = newRoot;

    for (let i = 0; i < pathParts.length - 1; i++) {
      const seg = pathParts[i];
      if (seg === "~") continue;
      if (!curr.children[seg] || curr.children[seg].type !== "dir") {
        throw new VfsError(`No such directory: ${seg}`);
      }
      curr = curr.children[seg] as VfsDir;
    }

    const lastSeg = pathParts[pathParts.length - 1];
    if (node === null) {
      delete curr.children[lastSeg];
    } else {
      curr.children[lastSeg] = node;
    }
    curr.modified = Date.now();

    return { ...state, root: newRoot };
  }

  // --- Core FS Operations ---

  static mkdir(state: VfsState, path: string): VfsState {
    const resolved = this.resolvePath(state.cwd, path);
    if (this.getNode(state, resolved))
      throw new VfsError(`mkdir: ${path}: already exists`);

    // Ensure parent exists
    const parentPath = resolved.slice(0, -1);
    const parent = this.getNode(state, parentPath);
    if (!parent || parent.type !== "dir")
      throw new VfsError(`mkdir: ${path}: No such file or directory`);

    const now = Date.now();
    return this.setNode(state, resolved, {
      type: "dir",
      children: {},
      created: now,
      modified: now,
    });
  }

  static touch(state: VfsState, path: string): VfsState {
    const resolved = this.resolvePath(state.cwd, path);
    const existing = this.getNode(state, resolved);
    const now = Date.now();

    if (existing) {
      return this.setNode(state, resolved, { ...existing, modified: now });
    }

    // Ensure parent exists
    const parentPath = resolved.slice(0, -1);
    const parent = this.getNode(state, parentPath);
    if (!parent || parent.type !== "dir")
      throw new VfsError(`touch: ${path}: No such file or directory`);

    return this.setNode(state, resolved, {
      type: "file",
      content: "",
      size: 0,
      created: now,
      modified: now,
    });
  }

  static write(state: VfsState, path: string, content: string): VfsState {
    const resolved = this.resolvePath(state.cwd, path);
    const existing = this.getNode(state, resolved);
    const now = Date.now();

    if (existing && existing.type === "dir")
      throw new VfsError(`write: ${path}: is a directory`);

    return this.setNode(state, resolved, {
      type: "file",
      content,
      size: content.length,
      created: existing ? (existing as VfsFile).created : now,
      modified: now,
    });
  }

  static rm(state: VfsState, path: string, recursive: boolean): VfsState {
    const resolved = this.resolvePath(state.cwd, path);
    if (resolved.length === 1 && resolved[0] === "~")
      throw new VfsError(`rm: cannot remove root directory`);

    const target = this.getNode(state, resolved);
    if (!target) throw new VfsError(`rm: ${path}: No such file or directory`);

    if (target.type === "dir" && !recursive)
      throw new VfsError(`rm: ${path}: is a directory`);

    return this.setNode(state, resolved, null);
  }

  static cp(
    state: VfsState,
    src: string,
    dest: string,
    recursive: boolean,
  ): VfsState {
    const srcResolved = this.resolvePath(state.cwd, src);
    const destResolved = this.resolvePath(state.cwd, dest);

    const srcNode = this.getNode(state, srcResolved);
    if (!srcNode) throw new VfsError(`cp: ${src}: No such file or directory`);

    if (srcNode.type === "dir" && !recursive)
      throw new VfsError(`cp: -r not specified; omitting directory '${src}'`);

    const destNode = this.getNode(state, destResolved);
    if (destNode && destNode.type === "dir") {
      destResolved.push(srcResolved[srcResolved.length - 1]);
    }

    // Check self-copy
    const srcStr = srcResolved.join("/");
    const destStr = destResolved.join("/");
    if (destStr === srcStr || destStr.startsWith(srcStr + "/")) {
      throw new VfsError(
        `cp: cannot copy '${src}' to a subdirectory of itself`,
      );
    }

    const cloned = this.cloneNode(srcNode);
    // Update timestamps recursively
    const updateTimes = (n: VfsNode) => {
      const now = Date.now();
      n.created = now;
      n.modified = now;
      if (n.type === "dir") {
        for (const child of Object.values(n.children)) updateTimes(child);
      }
    };
    updateTimes(cloned);

    return this.setNode(state, destResolved, cloned);
  }

  static mv(state: VfsState, src: string, dest: string): VfsState {
    const srcResolved = this.resolvePath(state.cwd, src);
    const destResolved = this.resolvePath(state.cwd, dest);

    const srcNode = this.getNode(state, srcResolved);
    if (!srcNode) throw new VfsError(`mv: ${src}: No such file or directory`);

    const destNode = this.getNode(state, destResolved);
    if (destNode && destNode.type === "dir") {
      destResolved.push(srcResolved[srcResolved.length - 1]);
    }

    // Check self-move
    const srcStr = srcResolved.join("/");
    const destStr = destResolved.join("/");
    if (destStr === srcStr || destStr.startsWith(srcStr + "/")) {
      throw new VfsError(
        `mv: cannot move '${src}' to a subdirectory of itself`,
      );
    }

    const cloned = this.cloneNode(srcNode);
    cloned.modified = Date.now();
    let nextState = this.setNode(state, destResolved, cloned);
    nextState = this.setNode(nextState, srcResolved, null);
    return nextState;
  }
}
