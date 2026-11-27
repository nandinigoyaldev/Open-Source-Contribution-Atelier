import * as Y from "yjs";
import { openDB, CRDT_DOC_STORE, CRDT_DELTA_STORE } from "./offlineDB";
import { eventBus } from "../core/events";

/**
 * Three standard sync lifecycle states exposed in the UI and indicators.
 */
export type SyncState = "synced" | "syncing" | "offline-buffered";

export interface CRDTDeltaOperation {
  id: string;
  docId: string;
  clientId: string;
  timestamp: number;
  lamportClock: number;
  operationType: "set" | "delete" | "merge" | "update";
  keyPath: string[];
  payload: unknown;
  delta?: Record<string, any>;
  encodedUpdate?: string; // base64 encoded binary Yjs update
  vectorClock?: Record<string, number>;
  applied?: boolean;
}

export interface CRDTDocumentRecord {
  docId: string;
  clientId: string;
  stateVector: Record<string, number>;
  encodedState: string; // base64 encoded Yjs document state
  updatedAt: number;
  version: number;
  snapshot: Record<string, any>;
}

export interface ThreeWayMergeResult<T = Record<string, any>> {
  merged: T;
  hasStructuralCollision: boolean;
  collisionReason?: string;
  conflictingKeys?: string[];
  resolvedKeys?: string[];
}

function uint8ArrayToBase64(bytes: Uint8Array): string {
  let binary = "";
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function base64ToUint8Array(base64: string): Uint8Array {
  const binary = atob(base64);
  const len = binary.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

class CRDTSyncEngine {
  private clientId: string;
  private lamportClock = 0;
  private vectorClock: Record<string, number> = {};
  private activeDocs = new Map<string, Y.Doc>();
  private inMemoryDeltas = new Map<string, CRDTDeltaOperation>();
  private inMemorySnapshots = new Map<string, Record<string, any>>();
  private syncState: SyncState = "synced";
  private syncListeners = new Set<(state: SyncState) => void>();

  constructor() {
    this.clientId = this.initClientId();
    this.initClock();
    this.initNetworkListeners();
  }

  private initClientId(): string {
    const key = "atelier_crdt_client_id";
    try {
      const stored = localStorage.getItem(key);
      if (stored) return stored;
      const c = globalThis.crypto;
      const nextId =
        c && typeof c.randomUUID === "function"
          ? c.randomUUID()
          : `client-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
      localStorage.setItem(key, nextId);
      return nextId;
    } catch {
      return `client-${Date.now().toString(36)}`;
    }
  }

  private initClock() {
    try {
      const stored = localStorage.getItem("atelier_crdt_clock");
      if (stored) {
        const val = parseInt(stored, 10);
        if (!isNaN(val)) this.lamportClock = val;
      }
    } catch {
      // ignore
    }
  }

  private persistClock() {
    try {
      localStorage.setItem("atelier_crdt_clock", String(this.lamportClock));
    } catch {
      // ignore
    }
  }

  public getClientId(): string {
    return this.clientId;
  }

  public getLamportClock(): number {
    return this.lamportClock;
  }

  public tickClock(received?: number): number {
    this.lamportClock = Math.max(this.lamportClock, received ?? 0) + 1;
    this.vectorClock[this.clientId] = this.lamportClock;
    this.persistClock();
    return this.lamportClock;
  }

  public getVectorClock(): Record<string, number> {
    return { ...this.vectorClock, [this.clientId]: this.lamportClock };
  }

  private initNetworkListeners() {
    if (typeof window === "undefined") return;

    window.addEventListener("online", () => {
      this.recalculateSyncState();
    });

    window.addEventListener("offline", () => {
      this.recalculateSyncState();
    });

    eventBus.on("sync:results", () => {
      this.recalculateSyncState();
    });
  }

  /**
   * Returns current sync lifecycle state.
   */
  public getSyncState(): SyncState {
    return this.syncState;
  }

  /**
   * Updates and broadcasts the sync state if changed.
   */
  public setSyncState(state: SyncState) {
    if (this.syncState === state) return;
    this.syncState = state;
    this.syncListeners.forEach((fn) => {
      try {
        fn(state);
      } catch (e) {
        console.error("[CRDTSyncEngine] Error in sync listener:", e);
      }
    });
    eventBus.emit("sync:state_change", { state });
  }

  /**
   * Recalculates state based on network connectivity and pending buffer.
   */
  public recalculateSyncState() {
    if (typeof navigator !== "undefined" && !navigator.onLine) {
      this.setSyncState("offline-buffered");
      return;
    }

    try {
      const pendingRaw = localStorage.getItem("atelier_pending_sync") || "[]";
      const pending = JSON.parse(pendingRaw);
      if (Array.isArray(pending) && pending.length > 0) {
        this.setSyncState(
          this.syncState === "syncing" ? "syncing" : "offline-buffered",
        );
        return;
      }
    } catch {
      // fallback
    }

    this.setSyncState("synced");
  }

  public subscribeSyncState(listener: (state: SyncState) => void): () => void {
    this.syncListeners.add(listener);
    listener(this.syncState);
    return () => {
      this.syncListeners.delete(listener);
    };
  }

  /**
   * Retrieves or initializes an active Y.Doc CRDT instance for the given document ID.
   */
  public async getDoc(docId: string): Promise<Y.Doc> {
    if (this.activeDocs.has(docId)) {
      return this.activeDocs.get(docId)!;
    }

    const doc = new Y.Doc();
    this.activeDocs.set(docId, doc);

    // Try loading persisted state from IndexedDB
    try {
      const db = await openDB();
      const tx = db.transaction(CRDT_DOC_STORE, "readonly");
      const store = tx.objectStore(CRDT_DOC_STORE);
      const req = store.get(docId);

      await new Promise<void>((resolve) => {
        req.onsuccess = () => {
          const record = req.result as CRDTDocumentRecord | undefined;
          if (record && record.encodedState) {
            try {
              const update = base64ToUint8Array(record.encodedState);
              Y.applyUpdate(doc, update);
              if (record.snapshot) {
                this.inMemorySnapshots.set(docId, record.snapshot);
              }
            } catch (err) {
              console.warn(
                `[CRDTSyncEngine] Error applying stored update for ${docId}:`,
                err,
              );
            }
          }
          resolve();
        };
        req.onerror = () => resolve();
      });
    } catch (err) {
      console.warn(
        `[CRDTSyncEngine] Failed to load ${docId} from IndexedDB:`,
        err,
      );
    }

    return doc;
  }

  /**
   * Records a timestamped delta operation backed by Yjs and IndexedDB.
   */
  public async recordDelta(
    docId: string,
    keyPath: string[],
    payload: unknown,
    operationType: "set" | "delete" | "merge" | "update" = "set",
    deltaData?: Record<string, any>,
  ): Promise<CRDTDeltaOperation> {
    const clock = this.tickClock();
    const timestamp = Date.now();
    const id = `delta-${timestamp}-${clock}-${Math.random().toString(36).slice(2, 7)}`;

    const doc = await this.getDoc(docId);
    const map = doc.getMap<unknown>("state");

    let encodedUpdate = "";
    try {
      doc.transact(() => {
        const rootKey = keyPath[0] || "root";
        if (operationType === "delete") {
          map.delete(rootKey);
        } else if (
          operationType === "merge" &&
          typeof payload === "object" &&
          payload !== null
        ) {
          const current = (map.get(rootKey) as Record<string, any>) || {};
          map.set(rootKey, { ...current, ...(payload as Record<string, any>) });
        } else {
          map.set(rootKey, payload);
        }
      });

      const updateBytes = Y.encodeStateAsUpdate(doc);
      encodedUpdate = uint8ArrayToBase64(updateBytes);
    } catch (e) {
      console.warn(
        `[CRDTSyncEngine] Yjs update encoding error for ${docId}:`,
        e,
      );
    }

    const delta: CRDTDeltaOperation = {
      id,
      docId,
      clientId: this.clientId,
      timestamp,
      lamportClock: clock,
      operationType,
      keyPath,
      payload,
      delta:
        deltaData ||
        (typeof payload === "object" && payload !== null
          ? (payload as Record<string, any>)
          : { value: payload }),
      encodedUpdate,
      vectorClock: this.getVectorClock(),
      applied: false,
    };

    // Store in-memory
    this.inMemoryDeltas.set(id, delta);

    // Persist to IndexedDB
    try {
      const db = await openDB();
      const tx = db.transaction(
        [CRDT_DELTA_STORE, CRDT_DOC_STORE],
        "readwrite",
      );
      const deltaStore = tx.objectStore(CRDT_DELTA_STORE);
      const docStore = tx.objectStore(CRDT_DOC_STORE);

      deltaStore.put(delta);

      // Update doc snapshot
      const snapshot = map.toJSON();
      this.inMemorySnapshots.set(docId, snapshot);

      const docRecord: CRDTDocumentRecord = {
        docId,
        clientId: this.clientId,
        stateVector: this.getVectorClock(),
        encodedState: encodedUpdate,
        updatedAt: timestamp,
        version: clock,
        snapshot,
      };
      docStore.put(docRecord);
    } catch (err) {
      console.warn(
        `[CRDTSyncEngine] Failed to persist delta to IndexedDB:`,
        err,
      );
    }

    // When offline, transition state to offline-buffered
    this.recalculateSyncState();

    return delta;
  }

  /**
   * Retrieves pending unapplied deltas.
   */
  public async getPendingDeltas(docId?: string): Promise<CRDTDeltaOperation[]> {
    try {
      const db = await openDB();
      const tx = db.transaction(CRDT_DELTA_STORE, "readonly");
      const store = tx.objectStore(CRDT_DELTA_STORE);

      const records: CRDTDeltaOperation[] = await new Promise((resolve) => {
        const req = store.getAll();
        req.onsuccess = () =>
          resolve((req.result as CRDTDeltaOperation[]) || []);
        req.onerror = () => resolve([]);
      });

      const filtered = records.filter(
        (d) => !d.applied && (!docId || d.docId === docId),
      );
      return filtered.sort(
        (a, b) => a.timestamp - b.timestamp || a.lamportClock - b.lamportClock,
      );
    } catch {
      // In-memory fallback
      return Array.from(this.inMemoryDeltas.values()).filter(
        (d) => !d.applied && (!docId || d.docId === docId),
      );
    }
  }

  /**
   * Marks given delta operations as applied after successful sync.
   */
  public async markDeltasApplied(deltaIds: string[]): Promise<void> {
    const idSet = new Set(deltaIds);
    for (const id of deltaIds) {
      const mem = this.inMemoryDeltas.get(id);
      if (mem) mem.applied = true;
    }

    try {
      const db = await openDB();
      const tx = db.transaction(CRDT_DELTA_STORE, "readwrite");
      const store = tx.objectStore(CRDT_DELTA_STORE);

      for (const id of deltaIds) {
        store.delete(id);
      }
    } catch (err) {
      console.warn(
        "[CRDTSyncEngine] Error removing settled deltas from IndexedDB:",
        err,
      );
    }
  }

  /**
   * Saves baseline snapshot for a document.
   */
  public async saveBaseSnapshot(
    docId: string,
    snapshot: Record<string, any>,
  ): Promise<void> {
    this.inMemorySnapshots.set(docId, snapshot);
    try {
      const db = await openDB();
      const tx = db.transaction(CRDT_DOC_STORE, "readwrite");
      const store = tx.objectStore(CRDT_DOC_STORE);
      const req = store.get(docId);
      req.onsuccess = () => {
        const existing = (req.result as CRDTDocumentRecord) || {
          docId,
          clientId: this.clientId,
          stateVector: this.getVectorClock(),
          encodedState: "",
          updatedAt: Date.now(),
          version: 1,
          snapshot,
        };
        existing.snapshot = snapshot;
        existing.updatedAt = Date.now();
        store.put(existing);
      };
    } catch {
      // fallback
    }
  }

  /**
   * Retrieves stored baseline snapshot for a document.
   */
  public async getBaseSnapshot(
    docId: string,
  ): Promise<Record<string, any> | null> {
    if (this.inMemorySnapshots.has(docId)) {
      return this.inMemorySnapshots.get(docId)!;
    }

    try {
      const db = await openDB();
      const tx = db.transaction(CRDT_DOC_STORE, "readonly");
      const store = tx.objectStore(CRDT_DOC_STORE);
      return new Promise((resolve) => {
        const req = store.get(docId);
        req.onsuccess = () => {
          const result = req.result as CRDTDocumentRecord | undefined;
          resolve(result?.snapshot || null);
        };
        req.onerror = () => resolve(null);
      });
    } catch {
      return null;
    }
  }

  /**
   * Automatic Three-Way Merge Engine
   *
   * Compares base state, local offline state, and remote server state.
   * Performs automatic deterministic conflict-free merge without user prompting
   * using CRDT properties unless an irreconcilable structural collision occurs.
   */
  public threeWayMerge<T extends Record<string, any>>(
    base: T | null | undefined,
    local: T,
    remote: T,
  ): ThreeWayMergeResult<T> {
    const baseObj = (base || {}) as Record<string, any>;
    const localObj = (local || {}) as Record<string, any>;
    const remoteObj = (remote || {}) as Record<string, any>;

    const merged: Record<string, any> = {};
    const conflictingKeys: string[] = [];
    const resolvedKeys: string[] = [];
    let hasStructuralCollision = false;
    let collisionReason: string | undefined;

    const allKeys = new Set([
      ...Object.keys(baseObj),
      ...Object.keys(localObj),
      ...Object.keys(remoteObj),
    ]);

    for (const key of allKeys) {
      const b = baseObj[key];
      const l = localObj[key];
      const r = remoteObj[key];

      // 1. If local and remote match, unanimous decision
      if (this.isDeepEqual(l, r)) {
        merged[key] = l !== undefined ? l : r;
        resolvedKeys.push(key);
        continue;
      }

      // 2. Local modified, remote unchanged from base -> take local
      if (!this.isDeepEqual(l, b) && this.isDeepEqual(r, b)) {
        merged[key] = l;
        resolvedKeys.push(key);
        continue;
      }

      // 3. Remote modified, local unchanged from base -> take remote
      if (this.isDeepEqual(l, b) && !this.isDeepEqual(r, b)) {
        merged[key] = r;
        resolvedKeys.push(key);
        continue;
      }

      // 4. Both changed concurrently: attempt automatic CRDT resolution
      // Case 4A: Numbers (e.g. score, xp, points, sequence) -> Monotonic Max
      if (typeof l === "number" && typeof r === "number") {
        merged[key] = Math.max(l, r);
        resolvedKeys.push(key);
        continue;
      }

      // Case 4B: Booleans (e.g. completed, verified) -> Monotonic OR (Grow-Only)
      if (typeof l === "boolean" && typeof r === "boolean") {
        merged[key] = l || r;
        resolvedKeys.push(key);
        continue;
      }

      // Case 4C: Arrays/Sets (e.g. tags, bookmarks, unlocked features) -> Set union
      if (Array.isArray(l) && Array.isArray(r)) {
        const set = new Set([...l, ...r]);
        merged[key] = Array.from(set);
        resolvedKeys.push(key);
        continue;
      }

      // Case 4D: Nested objects -> Recursive three-way merge
      if (
        this.isPlainObject(l) &&
        this.isPlainObject(r) &&
        (b === undefined || this.isPlainObject(b))
      ) {
        const nestedResult = this.threeWayMerge(b, l, r);
        merged[key] = nestedResult.merged;
        if (nestedResult.hasStructuralCollision) {
          hasStructuralCollision = true;
          conflictingKeys.push(key);
          collisionReason = nestedResult.collisionReason;
        } else {
          resolvedKeys.push(key);
        }
        continue;
      }

      // Case 4E: Timestamped objects / Last-Write-Wins (LWW)
      const lTime = l?.updated_at || l?.timestamp;
      const rTime = r?.updated_at || r?.timestamp;
      if (typeof lTime === "number" && typeof rTime === "number") {
        merged[key] = lTime >= rTime ? l : r;
        resolvedKeys.push(key);
        continue;
      }

      // Case 4F: Structural Collision Detection
      // Type mismatch or irreconcilable contradictory values
      const typeL = typeof l;
      const typeR = typeof r;

      if (typeL !== typeR || Array.isArray(l) !== Array.isArray(r)) {
        hasStructuralCollision = true;
        conflictingKeys.push(key);
        collisionReason = `Structural type mismatch on field '${key}': local is ${typeL}, remote is ${typeR}`;
        merged[key] = l; // keep local as fallback
        continue;
      }

      // If primitive values collide (e.g. contradictory non-numeric edits on same string)
      hasStructuralCollision = true;
      conflictingKeys.push(key);
      collisionReason = `Irreconcilable structural collision on property '${key}'`;
      merged[key] = l;
    }

    return {
      merged: merged as T,
      hasStructuralCollision,
      collisionReason,
      conflictingKeys,
      resolvedKeys,
    };
  }

  private isPlainObject(item: unknown): item is Record<string, any> {
    return (
      item !== null &&
      typeof item === "object" &&
      !Array.isArray(item) &&
      !(item instanceof Uint8Array) &&
      !(item instanceof Date)
    );
  }

  private isDeepEqual(a: unknown, b: unknown): boolean {
    if (a === b) return true;
    if (a === undefined && b === undefined) return true;
    if (a === null && b === null) return true;
    if (typeof a !== typeof b) return false;
    if (typeof a !== "object" || a === null || b === null) return false;

    if (Array.isArray(a) && Array.isArray(b)) {
      if (a.length !== b.length) return false;
      for (let i = 0; i < a.length; i++) {
        if (!this.isDeepEqual(a[i], b[i])) return false;
      }
      return true;
    }

    const keysA = Object.keys(a as Record<string, any>);
    const keysB = Object.keys(b as Record<string, any>);
    if (keysA.length !== keysB.length) return false;

    for (const key of keysA) {
      if (
        !this.isDeepEqual(
          (a as Record<string, any>)[key],
          (b as Record<string, any>)[key],
        )
      ) {
        return false;
      }
    }

    return true;
  }
}

export const crdtSyncEngine = new CRDTSyncEngine();
export default crdtSyncEngine;
