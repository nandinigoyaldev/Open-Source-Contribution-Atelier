import React, { useState, useEffect } from "react";
import { useOnlineStatus } from "../../hooks/useOnlineStatus";
import { WifiOff, CheckCircle2, X } from "lucide-react";

export function OfflineBanner() {
  const { isOnline, wasOffline } = useOnlineStatus();
  const [showReconnected, setShowReconnected] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!isOnline) {
      setShowReconnected(false);
      setDismissed(false);
    } else if (wasOffline) {
      // Dismissing the offline banner must not hide the confirmation that the network is back.
      setDismissed(false);
      setShowReconnected(true);
      const timer = setTimeout(() => {
        setShowReconnected(false);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [isOnline, wasOffline]);

  if (dismissed) return null;

  if (!isOnline) {
    return (
      <div
        role="alert"
        aria-live="assertive"
        className="fixed inset-x-0 top-0 z-50 bg-amber-400 text-black border-b-4 border-black font-black px-4 py-3 flex items-center justify-between shadow-card animate-fadeIn shrink-0"
      >
        <div className="flex items-center gap-2 text-xs sm:text-sm font-black uppercase">
          <WifiOff className="w-4 h-4 shrink-0 animate-pulse text-black" />
          <span>⚡ You are offline. Changes will sync automatically when back online.</span>
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="border-2 border-black bg-white hover:bg-gray-100 p-1 rounded-lg transition-all"
          aria-label="Dismiss offline banner"
        >
          <X className="w-3.5 h-3.5 text-black" />
        </button>
      </div>
    );
  }

  if (showReconnected) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="fixed inset-x-0 top-0 z-50 bg-emerald-400 text-black border-b-4 border-black font-black px-4 py-3 flex items-center justify-between shadow-card animate-fadeIn shrink-0"
      >
        <div className="flex items-center gap-2 text-xs sm:text-sm font-black uppercase">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-black" />
          <span>🟢 Reconnected</span>
        </div>
        <button
          onClick={() => setShowReconnected(false)}
          className="border-2 border-black bg-white hover:bg-gray-100 p-1 rounded-lg transition-all"
          aria-label="Close notification"
        >
          <X className="w-3.5 h-3.5 text-black" />
        </button>
      </div>
    );
  }

  return null;
}

export default OfflineBanner;
