import { useAuth } from "../../features/auth/AuthContext";
import { BadgeToastContainer } from "./BadgeToast";
import { useNotifications } from "../../features/notifications/NotificationContext";

export function BadgeToastNotifier() {
  const { user } = useAuth();
  const { toasts, dismissToast } = useNotifications();

  if (!user || user.is_staff) return null;

  return <BadgeToastContainer toasts={toasts as any} onDismiss={dismissToast} />;
}

