import { useNotifications as useNotificationContext } from "../features/notifications/NotificationContext";

export function useNotifications() {
  return useNotificationContext();
}
