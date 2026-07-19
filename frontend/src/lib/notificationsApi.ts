/**
 * REST helpers for the notification inbox (list / mark-read / prefs).
 * Kept separate from Redux so Vitest + MSW can cover them cleanly.
 */
import api from "../api";
import type { AppNotification } from "../features/notifications/notificationSlice";

export type NotificationPrefs = {
  email: boolean;
  in_app: boolean;
  websocket: boolean;
};

function asPrefs(data: unknown): NotificationPrefs {
  const row = (data ?? {}) as Record<string, unknown>;
  return {
    email: Boolean(row.email ?? true),
    in_app: Boolean(row.in_app ?? true),
    websocket: Boolean(row.websocket ?? true),
  };
}

export async function fetchNotificationPrefs(): Promise<NotificationPrefs> {
  const res = await api.get("/notifications/prefs/");
  return asPrefs(res.data);
}

export async function updateNotificationPrefs(
  prefs: NotificationPrefs,
): Promise<NotificationPrefs> {
  const res = await api.put("/notifications/prefs/", prefs);
  return asPrefs(res.data);
}

export async function listNotifications(): Promise<AppNotification[]> {
  const res = await api.get("/notifications/");
  const data = res.data;
  return Array.isArray(data) ? (data as AppNotification[]) : [];
}

export async function markNotificationRead(
  id: number,
): Promise<AppNotification | null> {
  const res = await api.post(`/notifications/${id}/read/`);
  return (res.data as AppNotification) ?? null;
}

export async function markAllNotificationsRead(): Promise<{
  marked_read: number;
}> {
  const res = await api.post("/notifications/mark-all-read/");
  return (res.data as { marked_read: number }) ?? { marked_read: 0 };
}

/** Build Channels WebSocket URL for notifications (JWT via ?token=). */
export function getNotificationsWsUrl(
  apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api",
): string {
  const cleaned = apiBase.replace(/\/$/, "");
  const host = cleaned.replace(/^https?:\/\//, "").replace(/\/api\/?$/, "");
  const scheme = cleaned.startsWith("https") ? "wss" : "ws";
  return `${scheme}://${host}/ws/notifications/`;
}

export const NOTIFICATION_POLL_INTERVAL_MS = 15_000;
