export interface VfsFile {
  type: "file";
  content: string;
  size: number;
  created: number;
  modified: number;
}

export interface VfsDir {
  type: "dir";
  children: Record<string, VfsNode>;
  created: number;
  modified: number;
}

export type VfsNode = VfsFile | VfsDir;

export interface VfsState {
  root: VfsDir;
  cwd: string[]; // e.g. ["~", "docs"]
}

export class VfsError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "VfsError";
  }
}
