import { describe, expect, it } from "vitest";
import {
  getNotificationsWsUrl,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "../lib/notificationsApi";
import {
  notificationSlice,
  markReadLocally,
  markAllReadLocally,
  addNotification,
  setWsUnreadCount,
  fetchNotifications,
} from "../features/notifications/notificationSlice";
import { configureStore } from "@reduxjs/toolkit";

describe("notificationsApi (MSW)", () => {
  it("lists notifications from REST", async () => {
    const items = await listNotifications();
    expect(items).toHaveLength(2);
    expect(items[0]?.id).toBe(1);
    expect(items[0]?.is_read).toBe(false);
    expect(items[1]?.is_read).toBe(true);
  });

  it("marks one notification as read", async () => {
    const updated = await markNotificationRead(1);
    expect(updated?.is_read).toBe(true);
    expect(updated?.id).toBe(1);
  });

  it("marks all notifications as read", async () => {
    const result = await markAllNotificationsRead();
    expect(result.marked_read).toBe(1);
  });

  it("builds ws/notifications URL with JWT query host", () => {
    expect(getNotificationsWsUrl("http://localhost:8000/api")).toBe(
      "ws://localhost:8000/ws/notifications/",
    );
    expect(getNotificationsWsUrl("https://api.example.com/api/")).toBe(
      "wss://api.example.com/ws/notifications/",
    );
  });

  it("loads and updates notification prefs", async () => {
    const { fetchNotificationPrefs, updateNotificationPrefs } =
      await import("../lib/notificationsApi");

    const prefs = await fetchNotificationPrefs();
    expect(prefs).toEqual({ email: true, in_app: true, websocket: true });

    const updated = await updateNotificationPrefs({
      email: false,
      in_app: true,
      websocket: false,
    });
    expect(updated.email).toBe(false);
    expect(updated.websocket).toBe(false);
  });
});

describe("notificationSlice unread sync", () => {
  it("decrements unread only once when marking read locally", () => {
    const state = {
      notifications: [
        {
          id: 1,
          notif_type: "system",
          title: "Hi",
          message: "msg",
          is_read: false,
          created_at: "2026-01-01",
          meta: {},
        },
      ],
      wsUnreadCount: 1,
      isLoading: false,
      nextPage: null,
      count: 1,
    };

    let next = notificationSlice.reducer(state, markReadLocally(1));
    expect(next.notifications[0]?.is_read).toBe(true);
    expect(next.wsUnreadCount).toBe(0);

    next = notificationSlice.reducer(next, markReadLocally(1));
    expect(next.wsUnreadCount).toBe(0);
  });

  it("mark all read clears badge count", () => {
    const state = {
      notifications: [
        {
          id: 1,
          notif_type: "system",
          title: "A",
          message: "a",
          is_read: false,
          created_at: "2026-01-01",
          meta: {},
        },
        {
          id: 2,
          notif_type: "system",
          title: "B",
          message: "b",
          is_read: false,
          created_at: "2026-01-01",
          meta: {},
        },
      ],
      wsUnreadCount: 2,
      isLoading: false,
      nextPage: null,
      count: 2,
    };

    const next = notificationSlice.reducer(state, markAllReadLocally());
    expect(next.notifications.every((n) => n.is_read)).toBe(true);
    expect(next.wsUnreadCount).toBe(0);
  });

  it("addNotification bumps unread for unread payloads", () => {
    const state = notificationSlice.getInitialState();
    const next = notificationSlice.reducer(
      state,
      addNotification({
        id: 9,
        notif_type: "badge",
        title: "Badge",
        message: "earned",
        is_read: false,
        created_at: "2026-01-01",
        meta: {},
      }),
    );
    expect(next.wsUnreadCount).toBe(1);
    expect(next.notifications[0]?.id).toBe(9);
  });

  it("fetchNotifications hydrates list via MSW", async () => {
    const store = configureStore({
      reducer: { notifications: notificationSlice.reducer },
    });
    await store.dispatch(fetchNotifications());
    const slice = store.getState().notifications;
    expect(slice.notifications.length).toBe(2);
    expect(slice.wsUnreadCount).toBe(1);
    expect(slice.isLoading).toBe(false);
  });

  it("setWsUnreadCount updates live badge source", () => {
    const next = notificationSlice.reducer(
      notificationSlice.getInitialState(),
      setWsUnreadCount(4),
    );
    expect(next.wsUnreadCount).toBe(4);
  });
});
