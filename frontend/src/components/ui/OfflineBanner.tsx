import React, { useState, useEffect } from "react";
import { useNetworkStatus } from "../../context/useNetworkStatus";
import { WifiOff, X } from "lucide-react";

export function OfflineBanner() {
  const { isOnline } = useNetworkStatus();
  const [visible, setVisible] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (isOnline) {
      setVisible(false);
      setDismissed(false);
    } else {
      // Offline banner appears within 2 seconds of network loss
      const timer = setTimeout(() => {
        if (!dismissed) {
          setVisible(true);
        }
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [isOnline, dismissed]);

  if (!visible) return null;

  return (
    <div className="bg-amber-400 text-black border-b-4 border-black font-black px-4 py-3 flex items-center justify-between z-50">
      <div className="flex items-center gap-2 text-sm uppercase">
        <WifiOff size={16} className="animate-pulse" />
        <span>You are offline. Changes will sync when connected.</span>
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="border-2 border-black bg-white hover:bg-gray-100 p-1 rounded-lg transition"
        aria-label="Dismiss offline banner"
      >
        <X size={14} />
      </button>
    </div>
  );
}

export default OfflineBanner;
