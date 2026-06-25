import { useAuth } from "../../features/auth/AuthContext";
import { BadgeToastContainer } from "./BadgeToast";
import { useBadgeToast } from "../../hooks/useBadgeToast";
import { BADGES } from "../../constants/badges";
import { useWebSocket } from "../../hooks/useWebSocket";

function getNotificationsWsUrl(): string {
  const apiBase =
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
  const host = apiBase.replace(/^https?:\/\//, "").replace(/\/api$/, "");
  const scheme = apiBase.startsWith("https") ? "wss" : "ws";
  return `${scheme}://${host}/ws/notifications/`;
}

export function BadgeToastNotifier() {
  const { user } = useAuth();
  const { toasts, addToast, dismissToast } = useBadgeToast(BADGES);

  // Re-use standard approach for getting tokens as in AuthContext.
  let token: string | null = null;
  try {
    token = localStorage.getItem("accessToken");
  } catch {
    /* localStorage unavailable */
  }

  useWebSocket({
    url: getNotificationsWsUrl(),
    token: user && !user.is_staff ? token : null,
    onMessage: (data: unknown) => {
      const msg = data as Record<string, unknown>;
      if (
        msg?.type === "notification" &&
        (msg.notification as Record<string, unknown>)?.notif_type === "badge"
      ) {
        const notif = msg.notification as Record<string, unknown>;
        const meta = notif.meta as Record<string, unknown>;
        const slug = meta?.badge_slug as string | undefined;
        if (slug) {
          addToast(slug);
        }
      }
    },
  });

  if (!user || user.is_staff) return null;

  return <BadgeToastContainer toasts={toasts} onDismiss={dismissToast} />;
}
