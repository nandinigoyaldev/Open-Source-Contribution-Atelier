import { ProfileSettingsForm } from "../features/auth/ProfileSettingsForm";
import { useAuth } from "../features/auth/AuthContext";
import { ActivityHeatmap } from "../components/ui/ActivityHeatmap";
import { NotificationPrefsToggle } from "../components/ui/NotificationPrefsToggle";
import { useState } from "react";

export function ProfileSettingsPage() {
  const { user } = useAuth();
  const [copied, setCopied] = useState(false);

  const handleCopyLink = () => {
    if (!user?.username) return;
    const profileLink = `${window.location.origin}/u/${user.username}`;
    void navigator.clipboard.writeText(profileLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="mx-auto max-w-[1600px] px-6 py-8">
      <div className="mb-8">
        <h1 className="text-4xl font-black tracking-tight text-black dark:text-white">
          Profile Settings
        </h1>
        <ActivityHeatmap />
      </div>

      <div className="grid gap-8 lg:grid-cols-[1fr_minmax(280px,360px)]">
        <ProfileSettingsForm />
        <div className="space-y-6">
          <NotificationPrefsToggle />
          {user?.username && (
            <div className="rounded-2xl border-4 border-black bg-white p-4 dark:bg-[#151411] dark:border-[#2e2924]">
              <p className="mb-2 text-xs font-black uppercase tracking-wide text-muted">
                Public profile
              </p>
              <button
                type="button"
                onClick={handleCopyLink}
                className="w-full rounded-xl border-2 border-black px-3 py-2 text-sm font-black hover:bg-surface-low dark:border-[#2e2924]"
              >
                {copied ? "Link copied!" : "Copy profile link"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ProfileSettingsPage;
