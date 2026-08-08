import React, { useState, useEffect } from 'react';
import { fetchApi } from '../lib/api';

export function SettingsPage() {
  const [prefs, setPrefs] = useState<Record<string, any>>({
    email: true,
    in_app: true,
    websocket: true,
    receive_weekly_digest: true,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi('/notifications/prefs/')
      .then(data => { setPrefs(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const toggle = async (key: string) => {
    const updated = { ...prefs, [key]: !prefs[key] };
    setPrefs(updated);
    await fetchApi('/notifications/prefs/', {
      method: 'PUT',
      body: JSON.stringify(updated)
    });
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div className="settings-page p-6 max-w-xl mx-auto bg-white dark:bg-[#111] rounded-2xl border border-black/10 dark:border-white/10 shadow-sm">
      <h2 className="text-xl font-black text-black dark:text-white mb-4 flex items-center gap-2">
        🔔 Notification Preferences
      </h2>
      <div className="settings-group flex flex-col gap-3">
        <label className="flex items-center gap-3 text-sm font-bold text-slate-700 dark:text-slate-200 cursor-pointer">
          <input type="checkbox" checked={Boolean(prefs.email)} onChange={() => toggle('email')} className="w-4 h-4 rounded text-indigo-600" />
          📧 Email Notifications
        </label>
        <label className="flex items-center gap-3 text-sm font-bold text-slate-700 dark:text-slate-200 cursor-pointer">
          <input
            type="checkbox"
            checked={Boolean(prefs.receive_weekly_digest ?? prefs.weekly_digest ?? true)}
            onChange={() => toggle('receive_weekly_digest')}
            className="w-4 h-4 rounded text-indigo-600"
          />
          📊 Weekly Learning Progress Digest Email
        </label>
        <label className="flex items-center gap-3 text-sm font-bold text-slate-700 dark:text-slate-200 cursor-pointer">
          <input type="checkbox" checked={Boolean(prefs.in_app)} onChange={() => toggle('in_app')} className="w-4 h-4 rounded text-indigo-600" />
          📱 In-App Alerts
        </label>
        <label className="flex items-center gap-3 text-sm font-bold text-slate-700 dark:text-slate-200 cursor-pointer">
          <input type="checkbox" checked={Boolean(prefs.websocket)} onChange={() => toggle('websocket')} className="w-4 h-4 rounded text-indigo-600" />
          🔄 WebSocket Real-time Updates
        </label>
      </div>
    </div>
  );
}