import React, { useState, useEffect } from "react";
import { fetchApi } from "../../lib/api";
import { Mail, Bell, RefreshCw } from "lucide-react";
import toast from "react-hot-toast";

export function NotificationPreferences() {
  const [prefs, setPrefs] = useState<Record<string, boolean>>({
    email: true,
    in_app: true,
    websocket: true,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchApi("/notifications/channel-preferences/")
      .then((data) => {
        setPrefs(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const toggle = async (key: string) => {
    if (saving) return;
    setSaving(true);
    const updated = { ...prefs, [key]: !prefs[key] };
    
    // Optimistic Update
    setPrefs(updated);

    try {
      await fetchApi("/notifications/channel-preferences/", {
        method: "PATCH",
        body: JSON.stringify(updated),
      });
      toast.success("Preferences updated successfully");
    } catch {
      // Revert if error
      setPrefs(prefs);
      toast.error("Failed to update preferences");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((n) => (
          <div key={n} className="h-16 w-full animate-pulse rounded-2xl bg-gray-200 dark:bg-gray-800" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border-4 border-black dark:border-[#2e2924] bg-white dark:bg-[#151411] p-6 shadow-card">
        <h2 className="font-display text-xl font-black uppercase text-black dark:text-white mb-4">
          Preferences
        </h2>
        <p className="text-sm text-gray-500 dark:text-[#c4bbae] mb-6">
          Choose how you would like to be notified about badges, achievements, comments, and other notifications.
        </p>

        <div className="space-y-4">
          <label className="flex items-center justify-between p-4 rounded-xl border-2 border-black dark:border-[#2e2924] bg-surface-low dark:bg-[#1f1c18] cursor-pointer hover:bg-white dark:hover:bg-[#151411] transition-all">
            <div className="flex items-center gap-3">
              <Mail className="text-[#4f46e5]" size={20} />
              <div>
                <span className="font-bold text-sm block text-black dark:text-white">Email Notifications</span>
                <span className="text-xs text-gray-500 dark:text-[#c4bbae]">Receive notification digests and alerts in your inbox</span>
              </div>
            </div>
            <input
              type="checkbox"
              checked={prefs.email}
              onChange={() => toggle("email")}
              disabled={saving}
              className="w-5 h-5 accent-primary cursor-pointer"
            />
          </label>

          <label className="flex items-center justify-between p-4 rounded-xl border-2 border-black dark:border-[#2e2924] bg-surface-low dark:bg-[#1f1c18] cursor-pointer hover:bg-white dark:hover:bg-[#151411] transition-all">
            <div className="flex items-center gap-3">
              <Bell className="text-accent" size={20} />
              <div>
                <span className="font-bold text-sm block text-black dark:text-white">In-App Alerts</span>
                <span className="text-xs text-gray-500 dark:text-[#c4bbae]">Show notifications in the global navigation drawer</span>
              </div>
            </div>
            <input
              type="checkbox"
              checked={prefs.in_app}
              onChange={() => toggle("in_app")}
              disabled={saving}
              className="w-5 h-5 accent-primary cursor-pointer"
            />
          </label>

          <label className="flex items-center justify-between p-4 rounded-xl border-2 border-black dark:border-[#2e2924] bg-surface-low dark:bg-[#1f1c18] cursor-pointer hover:bg-white dark:hover:bg-[#151411] transition-all">
            <div className="flex items-center gap-3">
              <RefreshCw className="text-green-500" size={20} />
              <div>
                <span className="font-bold text-sm block text-black dark:text-white">WebSocket Real-Time Updates</span>
                <span className="text-xs text-gray-500 dark:text-[#c4bbae]">Receive real-time popups and badge count updates instantly</span>
              </div>
            </div>
            <input
              type="checkbox"
              checked={prefs.websocket}
              onChange={() => toggle("websocket")}
              disabled={saving}
              className="w-5 h-5 accent-primary cursor-pointer"
            />
          </label>
        </div>
      </div>
    </div>
  );
}
