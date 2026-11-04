import { useState, useEffect, useRef } from "react";

export interface OnlineStatusResult {
  isOnline: boolean;
  wasOffline: boolean;
}

// The browser can drop an offline/online event (a backgrounded tab, a sleeping laptop, a
// captive network), so the status is also re-read on a short timer and whenever the tab
// comes back. Reading navigator.onLine is free, so this adds no network traffic.
const RESYNC_INTERVAL_MS = 1000;

const readOnline = () =>
  typeof navigator !== "undefined" ? navigator.onLine : true;

export function useOnlineStatus(): OnlineStatusResult {
  const [isOnline, setIsOnline] = useState<boolean>(readOnline);
  // A page that loads while offline should still say "Reconnected" when the network returns.
  const [wasOffline, setWasOffline] = useState<boolean>(() => !readOnline());
  const lastRef = useRef<boolean>(isOnline);

  useEffect(() => {
    const apply = (online: boolean) => {
      if (lastRef.current === online) return;
      lastRef.current = online;
      setIsOnline(online);
      if (!online) setWasOffline(true);
    };

    const handleOnline = () => apply(true);
    const handleOffline = () => apply(false);
    const resync = () => apply(readOnline());
    const resyncWhenVisible = () => {
      if (document.visibilityState === "visible") resync();
    };

    // Catch anything that changed before this effect ran.
    resync();

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    window.addEventListener("focus", resync);
    window.addEventListener("pageshow", resync);
    document.addEventListener("visibilitychange", resyncWhenVisible);
    const timer = window.setInterval(() => {
      if (document.visibilityState !== "hidden") resync();
    }, RESYNC_INTERVAL_MS);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("focus", resync);
      window.removeEventListener("pageshow", resync);
      document.removeEventListener("visibilitychange", resyncWhenVisible);
      window.clearInterval(timer);
    };
  }, []);

  return { isOnline, wasOffline };
}

export default useOnlineStatus;
