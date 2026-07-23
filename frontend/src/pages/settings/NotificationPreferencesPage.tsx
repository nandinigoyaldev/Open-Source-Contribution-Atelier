import React from "react";
import { NotificationPreferences } from "../../components/notifications/NotificationPreferences";

export function NotificationPreferencesPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-8">
        <h1 className="text-4xl font-black tracking-tight text-black dark:text-white uppercase mb-2">
          Notification Settings
        </h1>
        <p className="text-gray-500 dark:text-[#c4bbae]">
          Configure your channels and opt-in preferences for contributions, peer
          reviews, and gamification.
        </p>
      </div>

      <NotificationPreferences />
    </div>
  );
}

export default NotificationPreferencesPage;
