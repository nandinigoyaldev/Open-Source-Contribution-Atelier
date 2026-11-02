import React from "react";
import { ProfileSettingsForm } from "../features/auth/ProfileSettingsForm";

export function ProfileSettingsPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="mb-8">
        <h1 className="text-4xl font-black tracking-tight text-black dark:text-white uppercase mb-2">
          Profile Settings
        </h1>
        <p className="text-lg font-bold text-gray-600 dark:text-gray-300">
          Update your display name, bio, avatar and timezone.
        </p>
      </div>
      <ProfileSettingsForm />
    </div>
  );
}

export default ProfileSettingsPage;
