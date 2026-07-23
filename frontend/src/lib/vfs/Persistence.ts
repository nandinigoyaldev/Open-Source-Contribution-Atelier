import { VfsState } from "./types";
import { VirtualFileSystem } from "./FileSystem";

export class VfsPersistence {
  static readonly STORAGE_KEY = "sandbox_vfs_state_v2";

  static save(state: VfsState): void {
    try {
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(state));
    } catch (e) {
      console.warn("Failed to save VFS state to localStorage:", e);
    }
  }

  static load(): VfsState {
    try {
      const data = localStorage.getItem(this.STORAGE_KEY);
      if (data) {
        return JSON.parse(data) as VfsState;
      }
    } catch (e) {
      console.warn("Failed to load VFS state from localStorage:", e);
    }
    return VirtualFileSystem.createInitialState();
  }
}
