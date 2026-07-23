import { useCallback, useEffect, useState } from "react";
import { Bell, Loader2 } from "lucide-react";
import {
  fetchNotificationPrefs,
  updateNotificationPrefs,
  type NotificationPrefs,
} from "../../lib/notificationsApi";

const PREF_LABELS: {
  key: keyof NotificationPrefs;
  label: string;
  hint: string;
}[] = [
  {
    key: "email",
    label: "Email notifications",
    hint: "Digest and important alerts by email",
  },
  {
    key: "in_app",
    label: "In-app alerts",
    hint: "Bell menu and toast messages in the app",
  },
  {
    key: "websocket",
    label: "Live WebSocket updates",
    hint: "Realtime inbox updates when connected",
  },
];

const DEFAULT_PREFS: NotificationPrefs = {
  email: true,
  in_app: true,
  websocket: true,
};

/**
 * Minimal load/save toggles for GET/PUT /api/notifications/prefs/.
 */
export function NotificationPrefsToggle({
  className = "",
}: {
  className?: string;
}) {
  const [prefs, setPrefs] = useState<NotificationPrefs>(DEFAULT_PREFS);
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState<keyof NotificationPrefs | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchNotificationPrefs()
      .then((data) => {
        if (!cancelled) setPrefs(data);
      })
      .catch(() => {
        if (!cancelled) {
          setError("Could not load notification preferences. Try again later.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const toggle = useCallback(
    async (key: keyof NotificationPrefs) => {
      const previous = prefs;
      const updated = { ...prefs, [key]: !prefs[key] };
      setPrefs(updated);
      setSavingKey(key);
      setError(null);
      try {
        const saved = await updateNotificationPrefs(updated);
        setPrefs(saved);
      } catch {
        setPrefs(previous);
        setError("Failed to save preference. Your change was reverted.");
      } finally {
        setSavingKey(null);
      }
    },
    [prefs],
  );

  if (loading) {
    return (
      <div
        className={`flex items-center gap-2 rounded-2xl border-4 border-black bg-white p-6 font-bold dark:bg-[#151411] dark:border-[#2e2924] ${className}`}
        data-testid="notification-prefs-loading"
      >
        <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
        Loading notification preferences…
      </div>
    );
  }

  return (
    <section
      className={`rounded-2xl border-4 border-black bg-white p-6 shadow-card-sm dark:bg-[#151411] dark:border-[#2e2924] ${className}`}
      data-testid="notification-prefs-toggle"
      aria-labelledby="notification-prefs-heading"
    >
      <div className="mb-4 flex items-center gap-2">
        <Bell className="h-5 w-5" aria-hidden />
        <h2
          id="notification-prefs-heading"
          className="text-xl font-black uppercase tracking-tight"
        >
          Notification preferences
        </h2>
      </div>

      {error && (
        <p
          role="alert"
          className="mb-4 rounded-xl border-2 border-red-600 bg-red-50 px-3 py-2 text-sm font-bold text-red-800 dark:bg-red-950/40 dark:text-red-200"
        >
          {error}
        </p>
      )}

      <ul className="space-y-3">
        {PREF_LABELS.map(({ key, label, hint }) => (
          <li key={key}>
            <label className="flex cursor-pointer items-start gap-3 rounded-xl border-2 border-black/10 p-3 transition-colors hover:bg-surface-low dark:border-[#2e2924] dark:hover:bg-[#1f1c18]">
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 accent-black"
                checked={prefs[key]}
                disabled={savingKey !== null}
                onChange={() => toggle(key)}
                data-testid={`pref-toggle-${key}`}
              />
              <span className="min-w-0 flex-1">
                <span className="block font-black text-sm uppercase tracking-wide">
                  {label}
                  {savingKey === key && (
                    <Loader2
                      className="ml-2 inline h-3.5 w-3.5 animate-spin"
                      aria-label="Saving"
                    />
                  )}
                </span>
                <span className="mt-0.5 block text-sm font-bold text-muted dark:text-[#c4bbae]">
                  {hint}
                </span>
              </span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** @deprecated Prefer NotificationPrefsToggle — kept for route alias compatibility */
export function SettingsPage() {
  return (
    <div className="mx-auto max-w-xl px-4 py-8">
      <NotificationPrefsToggle />
    </div>
  );
}

export default NotificationPrefsToggle;
