import React, { useState, useEffect } from 'react';
import { WifiOff, RefreshCw } from 'lucide-react';

export function SyncStatusIndicator() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Poll local storage for pending syncs
    const checkPending = () => {
      try {
        const pending = JSON.parse(localStorage.getItem('atelier_pending_sync') || '[]');
        setPendingCount(pending.length);
      } catch (e) {
        setPendingCount(0);
      }
    };
    checkPending();
    const interval = setInterval(checkPending, 2000);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      clearInterval(interval);
    };
  }, []);

  if (isOnline && pendingCount === 0) {
    return null;
  }

  return (
    <div className="flex items-center space-x-2 text-sm px-3 py-1 rounded-full border transition-colors bg-gray-900 border-gray-700 text-gray-300 shadow-sm mx-2">
      {isOnline ? (
        <>
          <RefreshCw className="w-4 h-4 text-blue-400 animate-spin" />
          <span className="hidden sm:inline">Syncing {pendingCount} item{pendingCount !== 1 ? 's' : ''}...</span>
        </>
      ) : (
        <>
          <WifiOff className="w-4 h-4 text-yellow-500" />
          <span className="hidden sm:inline">Offline ({pendingCount} pending)</span>
        </>
      )}
    </div>
  );
}
