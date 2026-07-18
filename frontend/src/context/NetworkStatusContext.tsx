// @refresh reset
/**
 * NetworkStatusContext.tsx
 * Provides a boolean `isOnline` flag across the whole app via React context.
 * Listens to native window online/offline events.
 *
 * Usage:
 *  - Wrap your app with <NetworkStatusProvider>
 *  - Consume with useNetworkStatus() from ./useNetworkStatus
 */
import React, { createContext, useEffect, useState, ReactNode } from "react";

export interface NetworkStatusContextValue {
  isOnline: boolean;
}

export const NetworkStatusContext = createContext<NetworkStatusContextValue>({
  isOnline: true,
});

export function NetworkStatusProvider({ children }: { children: ReactNode }) {
  const [isOnline, setIsOnline] = useState<boolean>(
    typeof navigator !== "undefined" ? navigator.onLine : true,
  );

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    // Attempt to ping local server. If reachable, override offline status
    const checkServerReachable = async () => {
      try {
        const response = await fetch("/health/live/");
        if (response.ok) {
          setIsOnline(true);
        }
      } catch (e) {
        // If fetch fails and navigator is offline, match offline status
        if (typeof navigator !== "undefined" && !navigator.onLine) {
          setIsOnline(false);
        }
      }
    };

    checkServerReachable();
    const interval = setInterval(checkServerReachable, 10000);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      clearInterval(interval);
    };
  }, []);

  return (
    <NetworkStatusContext.Provider value={{ isOnline }}>
      {children}
    </NetworkStatusContext.Provider>
  );
}
