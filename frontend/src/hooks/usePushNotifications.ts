import { useState, useEffect } from "react";
import { fetchApi } from "../lib/api";

export function usePushNotifications() {
  const [permission, setPermission] = useState<NotificationPermission>(
    typeof window !== "undefined" && "Notification" in window
      ? Notification.permission
      : "default"
  );
  const [subscribed, setSubscribed] = useState(false);
  const [loading, setLoading] = useState(false);

  const isSupported =
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window;

  useEffect(() => {
    if (isSupported && permission === "granted") {
      navigator.serviceWorker.ready.then((registration) => {
        registration.pushManager.getSubscription().then((sub) => {
          setSubscribed(!!sub);
        });
      });
    }
  }, [permission, isSupported]);

  const requestPermissionAndSubscribe = async () => {
    if (!isSupported) return false;
    setLoading(true);
    try {
      const res = await Notification.requestPermission();
      setPermission(res);
      if (res === "granted") {
        const registration = await navigator.serviceWorker.ready;
        const sub = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-Skv69yViEuiBIa",
        });
        const p256dh = sub.getKey ? btoa(String.fromCharCode(...new Uint8Array(sub.getKey("p256dh")!))) : "";
        const auth = sub.getKey ? btoa(String.fromCharCode(...new Uint8Array(sub.getKey("auth")!))) : "";

        await fetchApi("/notifications/push/subscribe/", {
          method: "POST",
          body: JSON.stringify({
            endpoint: sub.endpoint,
            p256dh,
            auth,
          }),
        });
        setSubscribed(true);
        return true;
      }
    } catch (err) {
      console.error("Failed to subscribe to push notifications", err);
    } finally {
      setLoading(false);
    }
    return false;
  };

  const unsubscribe = async () => {
    if (!isSupported) return;
    setLoading(true);
    try {
      const registration = await navigator.serviceWorker.ready;
      const sub = await registration.pushManager.getSubscription();
      if (sub) {
        await sub.unsubscribe();
        await fetchApi("/notifications/push/unsubscribe/", {
          method: "POST",
          body: JSON.stringify({ endpoint: sub.endpoint }),
        });
      }
      setSubscribed(false);
    } catch (err) {
      console.error("Failed to unsubscribe", err);
    } finally {
      setLoading(false);
    }
  };

  return {
    isSupported,
    permission,
    subscribed,
    loading,
    requestPermissionAndSubscribe,
    unsubscribe,
  };
}
