import { useState, useEffect, useCallback } from "react";
import { api } from "@/services/api";

function urlBase64ToUint8Array(base64String: string) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding)
    .replace(/-/g, "+")
    .replace(/_/g, "/");

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export function useWebPush() {
  const [isSupported, setIsSupported] = useState(false);
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [permission, setPermission] = useState<NotificationPermission>("default");

  useEffect(() => {
    if ("serviceWorker" in navigator && "PushManager" in window) {
      setIsSupported(true);
      setPermission(Notification.permission);
      checkSubscription();
    }
  }, []);

  const checkSubscription = async () => {
    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      setIsSubscribed(!!subscription);
    } catch (err) {
      console.error("Error checking push subscription:", err);
    }
  };

  const subscribe = useCallback(async () => {
    if (!isSupported) return;

    try {
      const perm = await Notification.requestPermission();
      setPermission(perm);

      if (perm !== "granted") {
        console.warn("Notification permission denied");
        return;
      }

      const registration = await navigator.serviceWorker.ready;
      
      const vapidPublicKey = import.meta.env.VITE_VAPID_PUBLIC_KEY;
      if (!vapidPublicKey) {
        throw new Error("VITE_VAPID_PUBLIC_KEY is not configured.");
      }

      const convertedVapidKey = urlBase64ToUint8Array(vapidPublicKey);

      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: convertedVapidKey,
      });

      const subJson = subscription.toJSON();

      // Send to backend
      await api.post("/notifications/push/subscribe/", {
        endpoint: subJson.endpoint,
        p256dh: subJson.keys?.p256dh,
        auth: subJson.keys?.auth,
      });

      setIsSubscribed(true);
      return true;
    } catch (err) {
      console.error("Failed to subscribe to web push:", err);
      return false;
    }
  }, [isSupported]);

  const unsubscribe = useCallback(async () => {
    if (!isSupported) return;

    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();

      if (subscription) {
        await subscription.unsubscribe();

        // Notify backend
        const subJson = subscription.toJSON();
        await api.post("/notifications/push/unsubscribe/", {
          endpoint: subJson.endpoint,
        });
      }

      setIsSubscribed(false);
      return true;
    } catch (err) {
      console.error("Failed to unsubscribe from web push:", err);
      return false;
    }
  }, [isSupported]);

  return {
    isSupported,
    isSubscribed,
    permission,
    subscribe,
    unsubscribe,
  };
}
