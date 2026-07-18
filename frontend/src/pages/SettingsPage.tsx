import React, { useState, useEffect } from 'react';
import { fetchApi } from '../lib/api';

export function SettingsPage() {
  const [prefs, setPrefs] = useState<Record<string, boolean>>({ email: true, in_app: true, websocket: true });
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
    <div className="settings-page">
      <h2>🔔 Notification Preferences</h2>
      <div className="settings-group">
        <label>
          <input type="checkbox" checked={prefs.email} onChange={() => toggle('email')} />
          📧 Email Notifications
        </label>
        <label>
          <input type="checkbox" checked={prefs.in_app} onChange={() => toggle('in_app')} />
          📱 In-App Alerts
        </label>
        <label>
          <input type="checkbox" checked={prefs.websocket} onChange={() => toggle('websocket')} />
          🔄 WebSocket Updates
        </label>
      </div>
    </div>
  );
}