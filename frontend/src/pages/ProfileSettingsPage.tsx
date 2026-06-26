import React from "react";
import { ProfileSettingsForm } from "../features/auth/ProfileSettingsForm";
import { ActivityHeatmap } from "../components/ui/ActivityHeatmap";
import { useAuth } from "../features/auth/AuthContext";

export function ProfileSettingsPage() {
  const { user } = useAuth();

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* COVER IMAGE BANNER */}
      {user?.cover_image_url && (
        <div className="mb-8 w-full h-48 rounded-2xl overflow-hidden shadow-card border-4 border-black relative">
          <div
            className="absolute inset-0 bg-cover bg-center"
            style={{ backgroundImage: `url(${user.cover_image_url})` }}
          />
        </div>
      )}

      {/* HEADER SECTION */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-black text-black uppercase tracking-tight">
            Profile Settings
          </h1>
          <p className="mt-2 text-lg font-medium text-muted">
            Update your account information and preferences
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <div className="rounded-2xl border-4 border-black bg-[#E8F0FE] p-8 shadow-card">
          <h2 className="mb-6 text-2xl font-bold uppercase tracking-tight text-black flex items-center gap-3">
            <span className="text-3xl">⚙️</span> Settings
          </h2>
          <ProfileSettingsForm />
        </div>

        {/* Additional information card or future settings */}
        <div className="rounded-2xl border-4 border-black bg-[#FFF0E5] p-8 shadow-card flex flex-col justify-center items-center text-center">
          <div className="text-6xl mb-6">🔒</div>
          <h2 className="text-2xl font-bold uppercase tracking-tight text-black mb-4">
            Security & Privacy
          </h2>
          <p className="text-lg font-medium text-black/80 max-w-md">
            Your data is stored securely. Passwords are cryptographically hashed
            and never stored in plain text.
          </p>
        </div>
      </div>

      {/* ACTIVITY HEATMAP SECTION */}
      <div className="mt-8 rounded-2xl border-4 border-black bg-white dark:bg-[#151411] p-8 shadow-card overflow-hidden">
        <ActivityHeatmap />
      </div>
    </div>
  );
}
