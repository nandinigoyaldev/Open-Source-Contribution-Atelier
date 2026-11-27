import { useState, useEffect } from "react";
import { crdtSyncEngine, type SyncState } from "../lib/crdtSyncEngine";
import { useNetworkStatus } from "../context/useNetworkStatus";
import { eventBus } from "../core/events";

export interface SyncStateHookResult {
  syncState: SyncState;
  pendingCount: number;
  isOnline: boolean;
}

function getStoredPendingCount(): number {
  try {
    const raw = localStorage.getItem("atelier_pending_sync") || "[]";
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.length : 0;
  } catch {
    return 0;
  }
}

export function useSyncState(): SyncStateHookResult {
  const { isOnline } = useNetworkStatus();
  const [syncState, setSyncState] = useState<SyncState>(() =>
    crdtSyncEngine.getSyncState(),
  );
  const [pendingCount, setPendingCount] = useState<number>(() =>
    getStoredPendingCount(),
  );

  useEffect(() => {
    const update = () => {
      crdtSyncEngine.recalculateSyncState();
      setSyncState(crdtSyncEngine.getSyncState());
      setPendingCount(getStoredPendingCount());
    };

    update();

    const unsubscribe = crdtSyncEngine.subscribeSyncState((state) => {
      setSyncState(state);
      setPendingCount(getStoredPendingCount());
    });

    eventBus.on("sync:results", update);
    eventBus.on("sync:conflict", update);
    eventBus.on("sync:success", update);

    const interval = setInterval(update, 2000);

    return () => {
      unsubscribe();
      eventBus.off("sync:results", update);
      eventBus.off("sync:conflict", update);
      eventBus.off("sync:success", update);
      clearInterval(interval);
    };
  }, []);

  return { syncState, pendingCount, isOnline };
}

export default useSyncState;
