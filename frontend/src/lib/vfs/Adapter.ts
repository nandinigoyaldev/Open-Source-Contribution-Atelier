import { VfsState, VfsDir, VfsFile } from "./types";

export class VfsAdapter {
  // Convert tree VFS to flat VFS for legacy Git parser
  static toFlat(
    state: VfsState,
  ): Record<
    string,
    { type: "file"; content: string } | { type: "dir"; children: any }
  > {
    const flat: Record<string, any> = {};

    const traverse = (node: VfsDir, currentPath: string) => {
      flat[currentPath] = { type: "dir", children: {} };
      for (const [name, child] of Object.entries(node.children)) {
        const path =
          currentPath === "~" ? `~/${name}` : `${currentPath}/${name}`;
        if (child.type === "file") {
          flat[path] = { type: "file", content: child.content };
        } else {
          traverse(child as VfsDir, path);
        }
      }
    };

    traverse(state.root, "~");
    return flat;
  }
}
