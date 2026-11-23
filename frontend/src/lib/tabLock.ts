import { useState, useEffect, useCallback } from 'react';

/**
 * TabLockManager - Cross-tab synchronized session lock using BroadcastChannel
 * and Web Locks API (navigator.locks) to prevent concurrent assessment/quiz attempts.
 */

export interface LockConflictInfo {
  challengeId: string;
  holderTabId: string;
  acquiredAt: number;
}

export type TabLockMessageType =
  | 'LOCK_QUERY'
  | 'LOCK_HEARTBEAT'
  | 'LOCK_ACQUIRED'
  | 'LOCK_RELEASED';

export interface TabLockMessage {
  type: TabLockMessageType;
  challengeId: string;
  tabId: string;
  timestamp: number;
}

const CHANNEL_NAME = 'atelier:challenge-session-lock';

export class TabLockManager {
  private static instance: TabLockManager;
  private tabId: string;
  private channel: BroadcastChannel | null = null;
  private heldLocks: Map<string, number> = new Map(); // challengeId -> acquiredAt
  private remoteLocks: Map<string, { tabId: string; timestamp: number }> = new Map();
  private conflictListeners: Map<string, Set<(info: LockConflictInfo) => void>> = new Map();
  private releaseListeners: Map<string, Set<() => void>> = new Map();
  private initialized = false;

  private constructor() {
    this.tabId = typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `tab_${Math.random().toString(36).substring(2, 11)}_${Date.now()}`;
    this.init();
  }

  public static getInstance(): TabLockManager {
    if (!TabLockManager.instance) {
      TabLockManager.instance = new TabLockManager();
    } else if (!TabLockManager.instance.initialized) {
      TabLockManager.instance.init();
    }
    return TabLockManager.instance;
  }

  public getTabId(): string {
    return this.tabId;
  }

  private init(): void {
    if (this.initialized) return;
    this.initialized = true;

    if (typeof BroadcastChannel !== 'undefined') {
      try {
        this.channel = new BroadcastChannel(CHANNEL_NAME);
        this.channel.onmessage = (event: MessageEvent<TabLockMessage>) => {
          this.handleMessage(event.data);
        };
      } catch {
        this.channel = null;
      }
    }

    if (typeof window !== 'undefined') {
      window.addEventListener('beforeunload', () => {
        this.releaseAll();
      });
      window.addEventListener('pagehide', () => {
        this.releaseAll();
      });
    }
  }

  private handleMessage(data: TabLockMessage): void {
    if (!data || data.tabId === this.tabId) return;

    switch (data.type) {
      case 'LOCK_QUERY': {
        // Another tab is asking who holds the lock for this challenge
        if (this.heldLocks.has(data.challengeId)) {
          this.postMessage({
            type: 'LOCK_HEARTBEAT',
            challengeId: data.challengeId,
            tabId: this.tabId,
            timestamp: this.heldLocks.get(data.challengeId) || Date.now(),
          });
        }
        break;
      }

      case 'LOCK_HEARTBEAT':
      case 'LOCK_ACQUIRED': {
        this.remoteLocks.set(data.challengeId, {
          tabId: data.tabId,
          timestamp: data.timestamp,
        });

        const listeners = this.conflictListeners.get(data.challengeId);
        if (listeners) {
          const info: LockConflictInfo = {
            challengeId: data.challengeId,
            holderTabId: data.tabId,
            acquiredAt: data.timestamp,
          };
          listeners.forEach((fn) => fn(info));
        }
        break;
      }

      case 'LOCK_RELEASED': {
        const existing = this.remoteLocks.get(data.challengeId);
        if (existing && existing.tabId === data.tabId) {
          this.remoteLocks.delete(data.challengeId);
          const listeners = this.releaseListeners.get(data.challengeId);
          if (listeners) {
            listeners.forEach((fn) => fn());
          }
        }
        break;
      }
    }
  }

  private postMessage(msg: TabLockMessage): void {
    if (this.channel) {
      try {
        this.channel.postMessage(msg);
      } catch {
        // Channel closed or disconnected
      }
    }
  }

  /**
   * Attempts to acquire an exclusive session lock for the given challenge.
   * Returns true if lock acquired, or false if already held by another tab.
   */
  public async acquireLock(
    challengeId: string,
    options: { timeoutMs?: number } = {}
  ): Promise<boolean> {
    // If this tab already holds it, success
    if (this.heldLocks.has(challengeId)) {
      return true;
    }

    const timeoutMs = options.timeoutMs ?? 150;

    // Check remoteLocks map first
    if (this.remoteLocks.has(challengeId)) {
      return false;
    }

    // Query active tabs
    let conflict = false;
    if (this.channel) {
      this.postMessage({
        type: 'LOCK_QUERY',
        challengeId,
        tabId: this.tabId,
        timestamp: Date.now(),
      });

      // Wait brief window for heartbeat responses
      await new Promise((resolve) => setTimeout(resolve, timeoutMs));

      if (this.remoteLocks.has(challengeId)) {
        conflict = true;
      }
    }

    if (conflict) {
      return false;
    }

    // Try Web Locks API if supported
    if (
      typeof navigator !== 'undefined' &&
      navigator.locks &&
      typeof navigator.locks.request === 'function'
    ) {
      try {
        let lockGranted = false;
        await navigator.locks.request(
          `atelier:quiz-lock:${challengeId}`,
          { mode: 'exclusive', ifAvailable: true },
          async (lock) => {
            if (lock) {
              lockGranted = true;
              const now = Date.now();
              this.heldLocks.set(challengeId, now);
              this.postMessage({
                type: 'LOCK_ACQUIRED',
                challengeId,
                tabId: this.tabId,
                timestamp: now,
              });
            }
          }
        );
        return lockGranted;
      } catch {
        // Fall back to channel-only lock
      }
    }

    // BroadcastChannel lock fallback
    const now = Date.now();
    this.heldLocks.set(challengeId, now);
    this.postMessage({
      type: 'LOCK_ACQUIRED',
      challengeId,
      tabId: this.tabId,
      timestamp: now,
    });
    return true;
  }

  /**
   * Releases the held lock for the given challenge.
   */
  public releaseLock(challengeId: string): void {
    if (this.heldLocks.has(challengeId)) {
      this.heldLocks.delete(challengeId);
      this.postMessage({
        type: 'LOCK_RELEASED',
        challengeId,
        tabId: this.tabId,
        timestamp: Date.now(),
      });
    }
  }

  /**
   * Releases all held locks for this tab.
   */
  public releaseAll(): void {
    for (const challengeId of Array.from(this.heldLocks.keys())) {
      this.releaseLock(challengeId);
    }
  }

  /**
   * Returns true if the challenge is locked by another tab.
   */
  public isLockedByOtherTab(challengeId: string): boolean {
    return this.remoteLocks.has(challengeId) && !this.heldLocks.has(challengeId);
  }

  /**
   * Returns true if this tab currently owns the lock.
   */
  public isHeldByCurrentTab(challengeId: string): boolean {
    return this.heldLocks.has(challengeId);
  }

  /**
   * Subscribes to lock conflict events when another tab holds or acquires this lock.
   */
  public onConflict(
    challengeId: string,
    callback: (info: LockConflictInfo) => void
  ): () => void {
    if (!this.conflictListeners.has(challengeId)) {
      this.conflictListeners.set(challengeId, new Set());
    }
    this.conflictListeners.get(challengeId)!.add(callback);

    if (this.remoteLocks.has(challengeId)) {
      const existing = this.remoteLocks.get(challengeId)!;
      callback({
        challengeId,
        holderTabId: existing.tabId,
        acquiredAt: existing.timestamp,
      });
    }

    return () => {
      const set = this.conflictListeners.get(challengeId);
      if (set) {
        set.delete(callback);
        if (set.size === 0) this.conflictListeners.delete(challengeId);
      }
    };
  }

  /**
   * Subscribes to lock release events when the remote holder frees the lock.
   */
  public onRelease(challengeId: string, callback: () => void): () => void {
    if (!this.releaseListeners.has(challengeId)) {
      this.releaseListeners.set(challengeId, new Set());
    }
    this.releaseListeners.get(challengeId)!.add(callback);

    return () => {
      const set = this.releaseListeners.get(challengeId);
      if (set) {
        set.delete(callback);
        if (set.size === 0) this.releaseListeners.delete(challengeId);
      }
    };
  }

  /**
   * Closes the channel and cleans up memory.
   */
  public destroy(): void {
    this.releaseAll();
    if (this.channel) {
      try {
        this.channel.close();
      } catch {
        // ignore
      }
      this.channel = null;
    }
    this.conflictListeners.clear();
    this.releaseListeners.clear();
    this.remoteLocks.clear();
    this.heldLocks.clear();
    this.initialized = false;
  }
}

export interface UseChallengeTabLockResult {
  isLockedByOtherTab: boolean;
  conflictInfo: LockConflictInfo | null;
  isOwner: boolean;
  tabId: string;
  acquire: () => Promise<boolean>;
  release: () => void;
}

export function useChallengeTabLock(
  challengeId: string,
  autoAcquire = true
): UseChallengeTabLockResult {
  const manager = TabLockManager.getInstance();
  const [isLockedByOtherTab, setIsLockedByOtherTab] = useState(() =>
    manager.isLockedByOtherTab(challengeId)
  );
  const [conflictInfo, setConflictInfo] = useState<LockConflictInfo | null>(null);
  const [isOwner, setIsOwner] = useState(() =>
    manager.isHeldByCurrentTab(challengeId)
  );

  const acquire = useCallback(async () => {
    const success = await manager.acquireLock(challengeId);
    if (success) {
      setIsOwner(true);
      setIsLockedByOtherTab(false);
      setConflictInfo(null);
    } else {
      setIsOwner(false);
      setIsLockedByOtherTab(true);
    }
    return success;
  }, [challengeId, manager]);

  const release = useCallback(() => {
    manager.releaseLock(challengeId);
    setIsOwner(false);
  }, [challengeId, manager]);

  useEffect(() => {
    const unsubscribeConflict = manager.onConflict(challengeId, (info) => {
      setConflictInfo(info);
      setIsLockedByOtherTab(true);
      setIsOwner(false);
    });

    const unsubscribeRelease = manager.onRelease(challengeId, () => {
      setConflictInfo(null);
      setIsLockedByOtherTab(false);
    });

    if (autoAcquire) {
      acquire();
    }

    return () => {
      unsubscribeConflict();
      unsubscribeRelease();
      if (autoAcquire) {
        release();
      }
    };
  }, [challengeId, autoAcquire, manager, acquire, release]);

  return {
    isLockedByOtherTab,
    conflictInfo,
    isOwner,
    tabId: manager.getTabId(),
    acquire,
    release,
  };
}

