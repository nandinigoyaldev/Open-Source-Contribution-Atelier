import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TabLockManager, TabLockMessage } from '../lib/tabLock';

describe('TabLockManager', () => {
  let managerA: TabLockManager;
  let mockChannels: MockBroadcastChannel[] = [];

  class MockBroadcastChannel {
    name: string;
    onmessage: ((event: MessageEvent<TabLockMessage>) => void) | null = null;

    constructor(name: string) {
      this.name = name;
      mockChannels.push(this);
    }

    postMessage(data: TabLockMessage) {
      mockChannels.forEach((ch) => {
        if (ch !== this && ch.onmessage) {
          ch.onmessage({ data } as MessageEvent<TabLockMessage>);
        }
      });
    }

    close() {
      const idx = mockChannels.indexOf(this);
      if (idx !== -1) mockChannels.splice(idx, 1);
    }
  }

  beforeEach(() => {
    mockChannels = [];
    vi.stubGlobal('BroadcastChannel', MockBroadcastChannel);
    managerA = TabLockManager.getInstance();
    managerA.destroy();
    managerA = TabLockManager.getInstance();
  });

  afterEach(() => {
    managerA.destroy();
    vi.unstubAllGlobals();
    vi.clearAllTimers();
  });

  it('successfully acquires and holds a single session lock', async () => {
    const challengeId = 'quiz-101';
    const acquired = await managerA.acquireLock(challengeId, { timeoutMs: 10 });
    expect(acquired).toBe(true);
    expect(managerA.isHeldByCurrentTab(challengeId)).toBe(true);
    expect(managerA.isLockedByOtherTab(challengeId)).toBe(false);
  });

  it('releases lock cleanly and updates state', async () => {
    const challengeId = 'quiz-102';
    await managerA.acquireLock(challengeId, { timeoutMs: 10 });
    expect(managerA.isHeldByCurrentTab(challengeId)).toBe(true);

    managerA.releaseLock(challengeId);
    expect(managerA.isHeldByCurrentTab(challengeId)).toBe(false);
  });

  it('notifies conflict listener when remote tab acquires the lock', async () => {
    const challengeId = 'quiz-103';
    let conflictNotified = false;

    managerA.onConflict(challengeId, (info) => {
      conflictNotified = true;
      expect(info.challengeId).toBe(challengeId);
      expect(info.holderTabId).toBe('remote-tab-999');
    });

    // Simulate remote tab broadcasting LOCK_ACQUIRED
    mockChannels.forEach((ch) => {
      if (ch.onmessage) {
        ch.onmessage({
          data: {
            type: 'LOCK_ACQUIRED',
            challengeId,
            tabId: 'remote-tab-999',
            timestamp: Date.now(),
          },
        } as MessageEvent<TabLockMessage>);
      }
    });

    expect(conflictNotified).toBe(true);
    expect(managerA.isLockedByOtherTab(challengeId)).toBe(true);
  });

  it('rejects lock acquisition when remote tab already holds the lock', async () => {
    const challengeId = 'quiz-104';

    // Simulate remote tab acquiring lock
    mockChannels.forEach((ch) => {
      if (ch.onmessage) {
        ch.onmessage({
          data: {
            type: 'LOCK_ACQUIRED',
            challengeId,
            tabId: 'remote-tab-777',
            timestamp: Date.now(),
          },
        } as MessageEvent<TabLockMessage>);
      }
    });

    const acquired = await managerA.acquireLock(challengeId, { timeoutMs: 10 });
    expect(acquired).toBe(false);
    expect(managerA.isHeldByCurrentTab(challengeId)).toBe(false);
    expect(managerA.isLockedByOtherTab(challengeId)).toBe(true);
  });

  it('clears remote lock when remote tab broadcasts LOCK_RELEASED', async () => {
    const challengeId = 'quiz-105';
    let releaseNotified = false;

    managerA.onRelease(challengeId, () => {
      releaseNotified = true;
    });

    // Remote tab acquires
    mockChannels.forEach((ch) => {
      if (ch.onmessage) {
        ch.onmessage({
          data: {
            type: 'LOCK_ACQUIRED',
            challengeId,
            tabId: 'remote-tab-888',
            timestamp: Date.now(),
          },
        } as MessageEvent<TabLockMessage>);
      }
    });
    expect(managerA.isLockedByOtherTab(challengeId)).toBe(true);

    // Remote tab releases
    mockChannels.forEach((ch) => {
      if (ch.onmessage) {
        ch.onmessage({
          data: {
            type: 'LOCK_RELEASED',
            challengeId,
            tabId: 'remote-tab-888',
            timestamp: Date.now(),
          },
        } as MessageEvent<TabLockMessage>);
      }
    });

    expect(releaseNotified).toBe(true);
    expect(managerA.isLockedByOtherTab(challengeId)).toBe(false);
  });
});
