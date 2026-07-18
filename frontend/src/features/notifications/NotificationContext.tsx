// @refresh reset
/* eslint-disable react-refresh/only-export-components */
import React, {
  createContext,
  useContext,
  useEffect,
  useCallback,
  useMemo,
  useState,
} from "react";
import Confetti from "react-confetti";
import { useAppDispatch, useAppSelector } from "../../store/hooks";
import { useAuth } from "../auth/AuthContext";
import { useWebSocket } from "../../hooks/useWebSocket";
import { useAccessToken } from "../../hooks/useAccessToken";
import { useBadgeToast } from "../../hooks/useBadgeToast";
import { BADGES } from "../../constants/badges";
import {
  fetchNotifications,
  setWsUnreadCount,
  addNotification,
  markReadLocally,
  markAllReadLocally,
  AppNotification,
} from "./notificationSlice";
import {
  getNotificationsWsUrl,
  markAllNotificationsRead,
  markNotificationRead,
  NOTIFICATION_POLL_INTERVAL_MS,
} from "../../lib/notificationsApi";

export type { AppNotification };

interface NotificationContextType {
  notifications: AppNotification[];
  unreadCount: number;
  isLoading: boolean;
  /** Live Channels connection */
  isWsConnected: boolean;
  /** REST polling active because WS reconnect attempts were exhausted */
  isPollingFallback: boolean;
  markAsRead: (id: number) => Promise<void>;
  markAllAsRead: () => Promise<void>;
  toasts: unknown[];
  dismissToast: (id: string) => void;
  triggerConfetti: () => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(
  undefined,
);

export function NotificationProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user } = useAuth();
  const dispatch = useAppDispatch();
  const { notifications, wsUnreadCount, isLoading } = useAppSelector(
    (state) => state.notifications,
  );
  const { toasts, addToast, addDynamicToast, dismissToast } =
    useBadgeToast(BADGES);

  const [showConfetti, setShowConfetti] = useState(false);
  const triggerConfetti = useCallback(() => {
    setShowConfetti(true);
    setTimeout(() => setShowConfetti(false), 5000);
  }, []);

  // Reactive JWT — reconnects WS when token refreshes
  const token = useAccessToken();
  const canUseRealtime = !!user && !user.is_staff;

  // Initial REST fetch
  useEffect(() => {
    if (canUseRealtime) {
      dispatch(fetchNotifications());
    }
  }, [dispatch, canUseRealtime]);

  const unreadCount = useMemo(() => {
    const fromList = notifications.filter((n) => !n.is_read).length;
    return Math.max(wsUnreadCount, fromList);
  }, [wsUnreadCount, notifications]);

  const handleWsMessage = useCallback(
    (data: unknown) => {
      const msg = data as Record<string, unknown>;

      if (msg?.type === "connection_established") {
        dispatch(
          setWsUnreadCount(
            typeof msg.unread_count === "number" ? msg.unread_count : 0,
          ),
        );
      }

      if (msg?.type === "notification") {
        const notif = msg.notification as AppNotification;
        dispatch(addNotification(notif));

        const notifType = notif?.notif_type;
        if (notifType === "badge") {
          const slug = notif.meta?.badge_slug as string | undefined;
          if (slug) addToast(slug);
          triggerConfetti();
        } else if (notifType === "achievement") {
          if (notif.meta) {
            addDynamicToast({
              id: notif.meta.achievement_slug as string,
              name: notif.title,
              icon: (notif.meta.icon as string) || "🏆",
              desc: notif.message,
            });
            triggerConfetti();
          }
        }
      }

      if (msg?.type === "marked_read") {
        const id = Number(msg.notification_id);
        if (Number.isFinite(id)) {
          dispatch(markReadLocally(id));
        }
      }
    },
    [dispatch, addToast, addDynamicToast, triggerConfetti],
  );

  const { send: sendMessage, isConnected, reconnectExhausted } = useWebSocket({
    url: getNotificationsWsUrl(),
    token: canUseRealtime ? token : null,
    onMessage: handleWsMessage,
  });

  // REST poll while WS is down (covers reconnect window + exhausted fallback)
  const shouldPollRest = canUseRealtime && !isConnected;
  const isPollingFallback = canUseRealtime && reconnectExhausted;

  useEffect(() => {
    if (!shouldPollRest) return;

    const poll = () => {
      dispatch(fetchNotifications());
    };

    poll();
    const id = window.setInterval(poll, NOTIFICATION_POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [shouldPollRest, dispatch]);

  const markAsRead = useCallback(
    async (id: number) => {
      if (!canUseRealtime) return;

      dispatch(markReadLocally(id));

      try {
        const sent = isConnected
          ? sendMessage({ action: "mark_read", notification_id: id })
          : false;

        // Prefer WS when live; always REST when WS send failed / disconnected
        if (!sent) {
          await markNotificationRead(id);
        }
      } catch (error) {
        console.error("Failed to mark notification as read", error);
        dispatch(fetchNotifications());
      }
    },
    [canUseRealtime, isConnected, sendMessage, dispatch],
  );

  const markAllAsRead = useCallback(async () => {
    if (!canUseRealtime) return;

    dispatch(markAllReadLocally());

    try {
      await markAllNotificationsRead();
    } catch (error) {
      console.error("Failed to mark all as read", error);
      dispatch(fetchNotifications());
    }
  }, [canUseRealtime, dispatch]);

  const value: NotificationContextType = {
    notifications,
    unreadCount,
    isLoading,
    isWsConnected: isConnected,
    isPollingFallback,
    markAsRead,
    markAllAsRead,
    toasts,
    dismissToast,
    triggerConfetti,
  };

  return (
    <NotificationContext.Provider value={value}>
      {showConfetti && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            zIndex: 9999,
            pointerEvents: "none",
          }}
        >
          <Confetti
            width={window.innerWidth}
            height={window.innerHeight}
            recycle={false}
            numberOfPieces={400}
          />
        </div>
      )}
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  const context = useContext(NotificationContext);
  if (context === undefined) {
    throw new Error(
      "useNotifications must be used within a NotificationProvider",
    );
  }
  return context;
}
