// @refresh reset
/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useEffect, useCallback, useMemo, useState } from "react";
import Confetti from "react-confetti";
import { useAppDispatch, useAppSelector } from "../../store/hooks";
import { useAuth } from "../auth/AuthContext";
import { useWebSocketManager } from "../../hooks/useWebSocketManager";
import { useBadgeToast } from "../../hooks/useBadgeToast";
import { BADGES } from "../../constants/badges";
import { fetchApi } from "../../lib/api";
import { getAccessToken } from "../../lib/authToken";
import { showNotificationToast } from "../../components/notifications/NotificationToast";
import {
  fetchNotifications,
  setWsUnreadCount,
  addNotification,
  markReadLocally,
  markAllReadLocally,
  AppNotification,
} from "./notificationSlice";

export type { AppNotification };

interface NotificationContextType {
  notifications: AppNotification[];
  unreadCount: number;
  isLoading: boolean;
  markAsRead: (id: number) => Promise<void>;
  markAllAsRead: () => Promise<void>;
  toasts: unknown[];
  dismissToast: (id: string) => void;
  triggerConfetti: () => void;
  loadMore: () => void;
  hasMore: boolean;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

function getNotificationsWsUrl(): string {
  const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
  const host = apiBase.replace(/^https?:\/\//, "").replace(/\/api\/?$/, "");
  const scheme = apiBase.startsWith("https") ? "wss" : "ws";
  return `${scheme}://${host}/ws/notifications/`;
}

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const dispatch = useAppDispatch();
  const { notifications, wsUnreadCount, isLoading, nextPage } = useAppSelector((state) => state.notifications);
  const { toasts, addToast, addDynamicToast, dismissToast } = useBadgeToast(BADGES);

  const [showConfetti, setShowConfetti] = useState(false);
  const [page, setPage] = useState(1);

  const triggerConfetti = useCallback(() => {
    setShowConfetti(true);
    setTimeout(() => setShowConfetti(false), 5000);
  }, []);

  // Initial fetch for notifications list
  useEffect(() => {
    if (user && !user.is_staff) {
      setPage(1);
      dispatch(fetchNotifications(1));
    }
  }, [dispatch, user]);

  const loadMore = useCallback(() => {
    if (nextPage && !isLoading) {
      const nextPageNum = page + 1;
      setPage(nextPageNum);
      dispatch(fetchNotifications(nextPageNum));
    }
  }, [dispatch, nextPage, isLoading, page]);

  const hasMore = useMemo(() => !!nextPage, [nextPage]);

  // Calculate unread count
  const unreadCount = useMemo(() => {
    return Math.max(
      wsUnreadCount,
      notifications.filter((n) => !n.is_read).length
    );
  }, [wsUnreadCount, notifications]);

  // Auth token for WS
  const token = getAccessToken();

  const { send: sendMessage } = useWebSocketManager({
    url: getNotificationsWsUrl(),
    token: user && !user.is_staff ? token : null,
    onMessage: (data: unknown) => {
      const msg = data as Record<string, unknown>;
      
      if (msg?.type === "connection_established") {
        dispatch(setWsUnreadCount(typeof msg.unread_count === "number" ? msg.unread_count : 0));
      }
      
      if (msg?.type === "notification") {
        const notif = msg.notification as AppNotification;
        dispatch(addNotification(notif));

        // Toast notifications for high-priority events
        showNotificationToast(notif.title, notif.message, notif.notif_type);

        // Handle full audio-visual celebration for badges/achievements
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
        const id = msg.notification_id as number;
        dispatch(markReadLocally(id));
      }
    },
  });

  const markAsRead = useCallback(async (id: number) => {
    if (!user || user.is_staff) return;
    
    // Optimistic update
    dispatch(markReadLocally(id));

    try {
      // Use WS to mark read if possible, fallback to REST
      sendMessage({ action: "mark_read", notification_id: id });
      await fetchApi(`/notifications/${id}/mark-read/`, {
        method: "PATCH",
      });
    } catch (error) {
      console.error("Failed to mark notification as read", error);
      dispatch(fetchNotifications(1));
    }
  }, [user, sendMessage, dispatch]);

  const markAllAsRead = useCallback(async () => {
    if (!user || user.is_staff) return;
    
    // Optimistic update
    dispatch(markAllReadLocally());

    try {
      await fetchApi(`/notifications/mark-all-read/`, {
        method: "POST",
      });
    } catch (error) {
      console.error("Failed to mark all as read", error);
      dispatch(fetchNotifications(1));
    }
  }, [user, dispatch]);

  const value = {
    notifications,
    unreadCount,
    isLoading,
    markAsRead,
    markAllAsRead,
    toasts,
    dismissToast,
    triggerConfetti,
    loadMore,
    hasMore,
  };

  return (
    <NotificationContext.Provider value={value}>
      {showConfetti && (
        <div style={{ position: "fixed", top: 0, left: 0, width: "100%", height: "100%", zIndex: 9999, pointerEvents: "none" }}>
          <Confetti width={window.innerWidth} height={window.innerHeight} recycle={false} numberOfPieces={400} />
        </div>
      )}
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  const context = useContext(NotificationContext);
  if (context === undefined) {
    throw new Error("useNotifications must be used within a NotificationProvider");
  }
  return context;
}
