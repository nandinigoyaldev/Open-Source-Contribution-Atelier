import React, { useState, useEffect } from "react";
import { fetchApi } from "../../lib/api";
import { Mail, Bell, RefreshCw, Smartphone, Webhook, Send } from "lucide-react";
import toast from "react-hot-toast";
import { usePushNotifications } from "../../hooks/usePushNotifications";

const NOTIF_TYPES = [
  { id: "badge", label: "Badge Earned" },
  { id: "comment", label: "Peer Review & Comments" },
  { id: "achievement", label: "Achievements" },
  { id: "lesson_completed", label: "Lesson Completion" },
];

const CHANNELS = [
  { id: "in_app", label: "In-App", icon: Bell },
  { id: "email", label: "Email", icon: Mail },
  { id: "push", label: "Push", icon: RefreshCw },
  { id: "sms", label: "SMS", icon: Smartphone },
  { id: "webhook", label: "Webhook", icon: Webhook },
  { id: "slack", label: "Slack", icon: Send },
];

export function NotificationPreferences() {
  const [prefs, setPrefs] = useState<Record<string, any>>({
    email: true,
    in_app: true,
    websocket: true,
    channel_preferences: {},
    webhook_url: "",
    webhook_secret: "",
    phone_number: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const pushHook = usePushNotifications();

  useEffect(() => {
    fetchApi("/notifications/channels/")
      .then((data) => {
        setPrefs(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const savePreferences = async (updated: Record<string, any>) => {
    setSaving(true);
    setPrefs(updated);
    try {
      await fetchApi("/notifications/channels/", {
        method: "PUT",
        body: JSON.stringify(updated),
      });
      toast.success("Notification preferences updated");
    } catch {
      toast.error("Failed to update preferences");
    } finally {
      setSaving(false);
    }
  };

  const toggleChannelForType = (typeId: string, channelId: string) => {
    const currentMatrix = prefs.channel_preferences || {};
    const typeObj = currentMatrix[typeId] || {
      in_app: true,
      email: true,
      push: true,
      sms: false,
      webhook: false,
      slack: false,
    };

    const updatedTypeObj = {
      ...typeObj,
      [channelId]: !typeObj[channelId],
    };

    const updatedMatrix = {
      ...currentMatrix,
      [typeId]: updatedTypeObj,
    };

    savePreferences({
      ...prefs,
      channel_preferences: updatedMatrix,
    });
  };

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((n) => (
          <div
            key={n}
            className="h-16 w-full animate-pulse rounded-2xl bg-gray-200 dark:bg-gray-800"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Push Subscription Card */}
      <div className="rounded-2xl border-4 border-black dark:border-[#2e2924] bg-white dark:bg-[#151411] p-6 shadow-card">
        <h2 className="font-display text-xl font-black uppercase text-black dark:text-white mb-2">
          Browser Push Notifications
        </h2>
        <p className="text-sm text-gray-500 dark:text-[#c4bbae] mb-4">
          Enable instant push notifications even when OSCA is in the background.
        </p>
        <div className="flex items-center justify-between">
          <span className="text-sm font-bold text-black dark:text-white">
            Status:{" "}
            {pushHook.subscribed ? "Subscribed ✅" : "Not Subscribed ❌"}
          </span>
          {pushHook.subscribed ? (
            <button
              onClick={() => pushHook.unsubscribe()}
              disabled={pushHook.loading}
              className="px-4 py-2 bg-red-600 text-white rounded-lg font-bold hover:bg-red-700 transition"
            >
              Unsubscribe
            </button>
          ) : (
            <button
              onClick={() => pushHook.requestPermissionAndSubscribe()}
              disabled={pushHook.loading}
              className="px-4 py-2 bg-primary text-white rounded-lg font-bold hover:opacity-90 transition"
            >
              Enable Browser Push
            </button>
          )}
        </div>
      </div>

      {/* Channel Matrix */}
      <div className="rounded-2xl border-4 border-black dark:border-[#2e2924] bg-white dark:bg-[#151411] p-6 shadow-card">
        <h2 className="font-display text-xl font-black uppercase text-black dark:text-white mb-2">
          Channel Matrix Preferences
        </h2>
        <p className="text-sm text-gray-500 dark:text-[#c4bbae] mb-6">
          Toggle delivery channels individually for each notification category.
        </p>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm border-collapse">
            <thead>
              <tr className="border-b-2 border-gray-200 dark:border-gray-800">
                <th className="py-3 px-4 font-bold text-black dark:text-white">
                  Notification Type
                </th>
                {CHANNELS.map((ch) => {
                  const Icon = ch.icon;
                  return (
                    <th
                      key={ch.id}
                      className="py-3 px-4 font-bold text-center text-black dark:text-white"
                    >
                      <div className="flex flex-col items-center gap-1">
                        <Icon size={16} />
                        <span>{ch.label}</span>
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {NOTIF_TYPES.map((nt) => {
                const typeObj = (prefs.channel_preferences &&
                  prefs.channel_preferences[nt.id]) || {
                  in_app: true,
                  email: true,
                  push: true,
                  sms: false,
                  webhook: false,
                  slack: false,
                };

                return (
                  <tr
                    key={nt.id}
                    className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-900/50"
                  >
                    <td className="py-3 px-4 font-medium text-black dark:text-white">
                      {nt.label}
                    </td>
                    {CHANNELS.map((ch) => (
                      <td key={ch.id} className="py-3 px-4 text-center">
                        <input
                          type="checkbox"
                          checked={!!typeObj[ch.id]}
                          onChange={() => toggleChannelForType(nt.id, ch.id)}
                          disabled={saving}
                          className="w-5 h-5 accent-primary cursor-pointer"
                        />
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Webhook & SMS Endpoint Settings */}
      <div className="rounded-2xl border-4 border-black dark:border-[#2e2924] bg-white dark:bg-[#151411] p-6 shadow-card space-y-4">
        <h2 className="font-display text-xl font-black uppercase text-black dark:text-white mb-2">
          Custom Endpoint Configuration
        </h2>

        <div>
          <label className="block text-sm font-bold text-black dark:text-white mb-1">
            Webhook Target URL
          </label>
          <input
            type="url"
            value={prefs.webhook_url || ""}
            placeholder="https://webhook.site/..."
            onChange={(e) =>
              setPrefs({ ...prefs, webhook_url: e.target.value })
            }
            onBlur={() => savePreferences(prefs)}
            className="w-full p-2.5 rounded-lg border-2 border-black dark:border-[#2e2924] bg-surface-low dark:bg-[#1f1c18] text-black dark:text-white"
          />
        </div>

        <div>
          <label className="block text-sm font-bold text-black dark:text-white mb-1">
            Webhook Secret (for HMAC-SHA256 signature)
          </label>
          <input
            type="password"
            value={prefs.webhook_secret || ""}
            placeholder="whsec_..."
            onChange={(e) =>
              setPrefs({ ...prefs, webhook_secret: e.target.value })
            }
            onBlur={() => savePreferences(prefs)}
            className="w-full p-2.5 rounded-lg border-2 border-black dark:border-[#2e2924] bg-surface-low dark:bg-[#1f1c18] text-black dark:text-white"
          />
        </div>

        <div>
          <label className="block text-sm font-bold text-black dark:text-white mb-1">
            SMS Phone Number (E.164 format)
          </label>
          <input
            type="tel"
            value={prefs.phone_number || ""}
            placeholder="+1234567890"
            onChange={(e) =>
              setPrefs({ ...prefs, phone_number: e.target.value })
            }
            onBlur={() => savePreferences(prefs)}
            className="w-full p-2.5 rounded-lg border-2 border-black dark:border-[#2e2924] bg-surface-low dark:bg-[#1f1c18] text-black dark:text-white"
          />
        </div>
      </div>
    </div>
  );
}
