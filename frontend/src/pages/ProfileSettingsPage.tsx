import React, { useState, useEffect } from "react";
import { ProfileSettingsForm } from "../features/auth/ProfileSettingsForm";
import { useAuth } from "../features/auth/AuthContext";
import { ActivityHeatmap } from "../components/ui/ActivityHeatmap";

export function ProfileSettingsPage() {
  const { user } = useAuth();
  const [previewData, setPreviewData] = useState<any>({});
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [coverPreview, setCoverPreview] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (previewData.avatarFile) {
      const objectUrl = URL.createObjectURL(previewData.avatarFile);
      setAvatarPreview(objectUrl);
      return () => URL.revokeObjectURL(objectUrl);
    } else {
      setAvatarPreview(null);
    }
  }, [previewData.avatarFile]);

  useEffect(() => {
    if (previewData.coverFile) {
      const objectUrl = URL.createObjectURL(previewData.coverFile);
      setCoverPreview(objectUrl);
      return () => URL.revokeObjectURL(objectUrl);
    } else {
      setCoverPreview(null);
    }
  }, [previewData.coverFile]);

  const handleCopyLink = () => {
    const profileLink = `${window.location.origin}/u/${user?.username}`;
    navigator.clipboard.writeText(profileLink);
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

    </div>
  );

}
export default ProfileSettingsPage;
