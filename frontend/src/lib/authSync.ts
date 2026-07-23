export type AuthSyncEventType = "LOGIN" | "LOGOUT" | "TOKEN_REFRESHED";

export type AuthSyncEvent = { type: AuthSyncEventType };

const CHANNEL_NAME = "atelier:auth-sync";
const STORAGE_KEY = "atelier:auth-sync";

function getChannel(): BroadcastChannel | null {
  if (typeof BroadcastChannel === "undefined") return null;
  try {
    return new BroadcastChannel(CHANNEL_NAME);
  } catch {
    return null;
  }
}

/**
 * Broadcasts an authentication event to all other tabs.
 *
 * Uses BroadcastChannel when available; falls back to the storage event
 * mechanism for browsers without BroadcastChannel support. The two
 * transports are mutually exclusive to prevent listeners from firing
 * twice per broadcast.
 *
 * Only event types are sent — no tokens or credentials are ever included.
 */
export function broadcastAuthEvent(type: AuthSyncEventType): void {
  const event: AuthSyncEvent = { type };

  const ch = getChannel();
  if (ch) {
    try {
      ch.postMessage(event);
      ch.close();
      return;
    } catch {
      /* channel closed — fall through to storage fallback */
    }
  }

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(event));
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage unavailable */
  }
}

export type AuthSyncListener = (type: AuthSyncEventType) => void;

/**
 * Subscribes to cross-tab authentication events.
 *
 * Returns an unsubscribe function that removes all listeners.
 */
export function onAuthSyncEvent(listener: AuthSyncListener): () => void {
  const cleanupFns: Array<() => void> = [];

  const handleStorageEvent = (e: StorageEvent) => {
    if (e.key !== STORAGE_KEY || !e.newValue) return;
    try {
      const parsed = JSON.parse(e.newValue) as AuthSyncEvent;
      if (parsed.type) listener(parsed.type);
    } catch {
      /* malformed */
    }
  };

  const ch = getChannel();
  if (ch) {
    const handleChannelMessage = (e: MessageEvent<AuthSyncEvent>) => {
      if (e.data?.type) listener(e.data.type);
    };
    ch.addEventListener("message", handleChannelMessage);
    cleanupFns.push(() => {
      ch.removeEventListener("message", handleChannelMessage);
      ch.close();
    });
  } else {
    window.addEventListener("storage", handleStorageEvent);
    cleanupFns.push(() =>
      window.removeEventListener("storage", handleStorageEvent),
    );
  }

  return () => {
    for (const fn of cleanupFns) fn();
  };
}
