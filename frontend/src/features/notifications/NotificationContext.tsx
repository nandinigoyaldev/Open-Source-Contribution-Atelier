// @refresh reset
/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useEffect, useCallback, useMemo } from "react";
import { useAppDispatch, useAppSelector } from "../../store/hooks";
import { useAuth } from "../auth/AuthContext";
import { useWebSocket } from "../../hooks/useWebSocket";
import { useBadgeToast } from "../../hooks/useBadgeToast";
import { BADGES } from "../../constants/badges";
import api from "../../api";
import { getAccessToken } from "../../lib/authToken";
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
  const { notifications, wsUnreadCount, isLoading } = useAppSelector((state) => state.notifications);
  const { toasts, addToast, addDynamicToast, dismissToast } = useBadgeToast(BADGES);

  // Initial fetch for notifications list
  useEffect(() => {
    if (user && !user.is_staff) {
      dispatch(fetchNotifications());
    }
  }, [dispatch, user]);

  // Calculate unread count
  const unreadCount = useMemo(() => {
    return Math.max(
      wsUnreadCount,
      notifications.filter((n) => !n.is_read).length
    );
  }, [wsUnreadCount, notifications]);

  // Auth token for WS
  const token = getAccessToken();

  const { send: sendMessage } = useWebSocket({
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

        // Handle toast popups for specific types
        const notifType = notif?.notif_type;
        if (notifType === "badge") {
          const slug = notif.meta?.badge_slug as string | undefined;
          if (slug) addToast(slug);
        } else if (notifType === "achievement") {
          if (notif.meta) {
            addDynamicToast({
              id: notif.meta.achievement_slug as string,
              name: notif.title,
              icon: (notif.meta.icon as string) || "🏆",
              desc: notif.message,
            });
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
      await api.post(`/notifications/${id}/read/`);
    } catch (error) {
      console.error("Failed to mark notification as read", error);
      dispatch(fetchNotifications());
    }
  }, [user, sendMessage, dispatch]);

  const markAllAsRead = useCallback(async () => {
    if (!user || user.is_staff) return;
    
    // Optimistic update
    dispatch(markAllReadLocally());

    try {
      await api.post(`/notifications/mark-all-read/`);
    } catch (error) {
      console.error("Failed to mark all as read", error);
      dispatch(fetchNotifications());
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
  };

  return (
    <NotificationContext.Provider value={value}>
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
