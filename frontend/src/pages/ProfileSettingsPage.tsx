import React, { useState, useEffect } from "react";
import { ProfileSettingsForm } from "../features/auth/ProfileSettingsForm";
import { ActivityHeatmap } from "../components/ui/ActivityHeatmap";
import { useAuth } from "../features/auth/AuthContext";
import { getMediaUrl } from "../lib/api";
import { Github, Linkedin, Twitter, Award, BookOpen, Calendar, MapPin, Copy, Check, Eye } from "lucide-react";

export function ProfileSettingsPage() {
  const { user } = useAuth();
  const [previewData, setPreviewData] = useState<any>({});
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Manage avatar object URL for previewing unsaved files
  useEffect(() => {
    if (previewData.avatarFile) {
      const objectUrl = URL.createObjectURL(previewData.avatarFile);
      setAvatarPreview(objectUrl);
      return () => URL.revokeObjectURL(objectUrl);
    } else {
      setAvatarPreview(null);
    }
  }, [previewData.avatarFile]);

  const handleCopyLink = () => {
    const profileLink = `${window.location.origin}/u/${user?.username}`;
    navigator.clipboard.writeText(profileLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* HEADER SECTION */}
      <div className="mb-8">
        <h1 className="text-4xl font-black text-black dark:text-white uppercase tracking-tight">
          Profile Settings
        </h1>
        <p className="mt-2 text-lg font-medium text-muted">
          Update your account information and preview your public profile live.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-5">
        {/* LEFT COLUMN: Settings Form (3/5 width) */}
        <div className="lg:col-span-3 space-y-8">
          <div className="rounded-2xl border-4 border-black bg-[#E8F0FE] p-8 shadow-card dark:border-[#7790bf] dark:bg-[linear-gradient(145deg,#254478,#182235_62%,#171411)]">
            <h2 className="mb-6 text-2xl font-bold uppercase tracking-tight text-black dark:text-white flex items-center gap-3">
              <span className="text-3xl">⚙️</span> Settings Form
            </h2>
            <ProfileSettingsForm onChange={setPreviewData} />
          </div>
        </div>

        {/* RIGHT COLUMN: Live Profile Preview (2/5 width) */}
        <div className="lg:col-span-2 space-y-6">
          <div className="sticky top-28 rounded-2xl border-4 border-black bg-white p-6 shadow-card dark:bg-[#121218] dark:border-[#3a3a45] flex flex-col">
            <div className="flex items-center justify-between mb-6 pb-3 border-b-2 border-dashed border-gray-200 dark:border-gray-800">
              <h3 className="text-lg font-black uppercase text-black dark:text-white flex items-center gap-2">
                <Eye size={20} className="text-primary" /> Live Preview
              </h3>
              {user?.username && (
                <button
                  onClick={handleCopyLink}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold border-2 border-black rounded-lg bg-surface hover:bg-black hover:text-white transition-all dark:bg-[#1c1c24] dark:border-[#3a3a45]"
                  title="Copy public profile link"
                >
                  {copied ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
                  <span>{copied ? "Copied!" : "Share Link"}</span>
                </button>
              )}
            </div>

            {/* AVATAR */}
            <div className="flex justify-center mb-6">
              <div className="h-28 w-28 rounded-2xl border-4 border-black bg-slate-50 overflow-hidden shadow-card dark:border-[#3a3a45] dark:bg-[#1c1c24] flex items-center justify-center">
                {avatarPreview ? (
                  <img
                    src={avatarPreview}
                    alt="Preview"
                    className="h-full w-full object-cover"
                  />
                ) : user?.avatar_url ? (
                  <img
                    src={getMediaUrl(user.avatar_url) || ""}
                    alt={user.username}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <span className="text-4xl font-black uppercase text-black dark:text-white">
                    {user?.username?.charAt(0) || "U"}
                  </span>
                )}
              </div>
            </div>

            {/* DETAILS */}
            <div className="text-center mb-6">
              <h4 className="text-2xl font-black text-black dark:text-white">
                {user?.username}
              </h4>
              <p className="text-sm font-bold text-muted mt-1">{previewData.email || user?.email}</p>
              
              <div className="flex justify-center gap-4 mt-3 text-xs font-bold text-slate-500 dark:text-slate-400">
                {previewData.timezone && (
                  <div className="flex items-center gap-1">
                    <MapPin size={14} />
                    <span>{previewData.timezone}</span>
                  </div>
                )}
                <div className="flex items-center gap-1">
                  <Calendar size={14} />
                  <span>Joined Today</span>
                </div>
              </div>
            </div>

            {/* BIO */}
            <div className="mb-6 p-4 rounded-xl bg-slate-50 dark:bg-[#1a1a24] border-2 border-black dark:border-[#3a3a45]">
              <h5 className="text-xs font-black uppercase text-slate-400 mb-2">Bio Preview</h5>
              <p className="text-sm font-medium leading-relaxed text-black/80 dark:text-[#94a3b8] break-words whitespace-pre-wrap">
                {previewData.bio || "No bio details filled yet."}
              </p>
            </div>

            {/* SOCIALS */}
            <div className="flex justify-center gap-3 pt-4 border-t-2 border-dashed border-gray-200 dark:border-gray-800">
              {previewData.github_url ? (
                <span className="p-2 rounded-lg border border-black bg-slate-100 dark:bg-[#1a1a24] dark:border-[#3a3a45]">
                  <Github size={16} />
                </span>
              ) : null}
              {previewData.linkedin_url ? (
                <span className="p-2 rounded-lg border border-black bg-slate-100 dark:bg-[#1a1a24] dark:border-[#3a3a45]">
                  <Linkedin size={16} />
                </span>
              ) : null}
              {previewData.twitter_url ? (
                <span className="p-2 rounded-lg border border-black bg-slate-100 dark:bg-[#1a1a24] dark:border-[#3a3a45]">
                  <Twitter size={16} />
                </span>
              ) : null}
              {!previewData.github_url && !previewData.linkedin_url && !previewData.twitter_url && (
                <span className="text-xs font-bold text-slate-400 italic">No social links configured</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ACTIVITY HEATMAP SECTION */}
      <div className="max-w-3xl lg:max-w-none mt-8 rounded-2xl border-4 border-black bg-white dark:bg-[#151411] p-8 shadow-card overflow-hidden">
        <ActivityHeatmap />
      </div>
    </div>
  );
}

export default ProfileSettingsPage;
