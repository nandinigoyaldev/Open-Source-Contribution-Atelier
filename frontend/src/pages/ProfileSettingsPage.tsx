import React, { useState, useEffect } from "react";
import { ProfileSettingsForm } from "../features/auth/ProfileSettingsForm";
import { useAuth } from "../features/auth/AuthContext";
import { getMediaUrl } from "../lib/api";
import {
  Github,
  Linkedin,
  Twitter,
  Calendar,
  MapPin,
  Copy,
  Check,
  Eye,
} from "lucide-react";

export function ProfileSettingsPage() {
  const { user } = useAuth();
  const [previewData, setPreviewData] = useState<any>({});
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [coverPreview, setCoverPreview] = useState<string | null>(null);
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

  // Manage cover object URL for previewing unsaved files
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

      {/* ================= HEADER ================= */}

      <div className="mb-8">
        <h1 className="text-4xl font-black tracking-tight text-black dark:text-white">
          Profile Settings
        </h1>

        <p className="mt-2 text-gray-600 dark:text-gray-400">
=======
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* HEADER SECTION */}
      <div className="mb-8">
        <h1 className="text-4xl font-black text-black dark:text-white uppercase tracking-tight">
          Profile Settings
        </h1>
        <p className="mt-2 text-lg font-medium text-muted"
          Update your account information and preview your public profile live.
        </p>
      </div>


      {/* ================= MAIN GRID ================= */}

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">

        {/* ================= SETTINGS FORM ================= */}

        <div className="xl:col-span-5">

          <div className="rounded-3xl border-2 border-gray-200 dark:border-neutral-700 bg-white dark:bg-[#181818] shadow-lg p-8 h-full">

            <div className="flex items-center gap-3 mb-6">

              <div className="text-3xl">
                ⚙️
              </div>

              <div>

                <h2 className="text-2xl font-bold">
                  Settings
                </h2>

                <p className="text-sm text-gray-500">
                  Manage your profile information
                </p>

              </div>

            </div>

            <ProfileSettingsForm />

          </div>

        </div>

        {/* ================= LIVE PREVIEW ================= */}

        <div className="xl:col-span-4">

          <div className="rounded-3xl border-2 border-blue-200 dark:border-blue-700 bg-gradient-to-br from-blue-50 to-white dark:from-[#1b2433] dark:to-[#151515] shadow-lg p-8 sticky top-6">

            <h2 className="text-2xl font-bold mb-6">
              👀 Live Preview
            </h2>

            {/* Cover */}

            <div className="h-36 rounded-2xl bg-gradient-to-r from-sky-400 via-cyan-400 to-blue-500 flex items-center justify-center text-white font-bold text-lg">

              {user?.cover_image_url ? (
                <img
                  src={user.cover_image_url}
                  className="w-full h-full object-cover rounded-2xl"
                />
              ) : (
                "No Cover Image"
              )}

            </div>

            {/* Avatar */}

            <div className="flex justify-center -mt-10">

              <div className="h-24 w-24 rounded-full bg-white shadow-xl border-4 border-white overflow-hidden">

                {user?.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-3xl font-bold bg-gray-200">
                    {user?.username?.charAt(0)?.toUpperCase() || "G"}
                  </div>
                )}

              </div>

            </div>

            <div className="text-center mt-4">
              <h3 className="font-bold text-xl">
                {user?.username || "gauri9368gupta"}
              </h3>
              <p className="text-gray-500">
                {user?.email || "gauri9368gupta@gmail.com"}
              </p>
            </div>

            {/* Share Link */}

            <div className="mt-6 rounded-2xl border border-blue-200 dark:border-blue-700 bg-blue-50 dark:bg-[#1b2433] p-4">

              <div className="flex items-center justify-between">

                <div>

                  <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                    🔗 Share Profile
                  </p>

                  <p className="mt-1 text-xs text-gray-500 break-all">
                    {`${window.location.origin}/u/${user?.username || "gauri9368gupta"}`}
                  </p>

                </div>

                <button
                  type="button"
                  onClick={() => {
                    navigator.clipboard.writeText(
                      `${window.location.origin}/u/${user?.username || "gauri9368gupta"}`
                    );
                  }}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700"
                >
                  Copy
                </button>

              </div>

            </div>

            <div className="mt-6 space-y-3">
              <div className="rounded-xl bg-white dark:bg-[#202020] p-3 shadow">
                🌍 Timezone
                <div className="font-semibold">
                  UTC
                </div>
              </div>
              <div className="rounded-xl bg-white dark:bg-[#202020] p-3 shadow">
                📅 Joined
                <div className="font-semibold">
                  Today
                </div>
              </div>

              <div className="rounded-xl bg-white dark:bg-[#202020] p-3 shadow">

                📝 Bio

                <div className="mt-2 text-sm text-gray-500">

                  No bio added yet.

                </div>

              </div>

            </div>

          </div>

        </div>

        {/* ================= SECURITY ================= */}

        <div className="xl:col-span-3">

          <div className="rounded-3xl border-2 border-gray-200 dark:border-neutral-700 bg-white dark:bg-[#181818] shadow-lg p-8">

            <h2 className="text-2xl font-bold mb-6">

              🔒 Security

            </h2>

            <div className="space-y-4">

              <div className="rounded-xl bg-gray-100 dark:bg-[#242424] p-4">

                <div className="font-semibold">

                  Password

                </div>

                <div className="text-sm text-gray-500">

                  Last changed 2 weeks ago

                </div>

              </div>

              <div className="rounded-xl bg-gray-100 dark:bg-[#242424] p-4">

                🔔 Notifications

              </div>

              <div className="rounded-xl bg-gray-100 dark:bg-[#242424] p-4">

                🔐 Privacy

              </div>

              <div className="rounded-xl bg-gray-100 dark:bg-[#242424] p-4">

                📦 Download My Data

              </div>

            </div>

          </div>

        </div>

      </div>

      {/* ================= ACTIVITY ================= */}

      <div className="mt-8 rounded-3xl border-2 border-gray-200 dark:border-neutral-700 bg-white dark:bg-[#181818] p-8 shadow-lg">

        <h2 className="text-2xl font-bold mb-6">

          📈 Activity

        </h2>

        <ActivityHeatmap />

=======
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        {/* LEFT COLUMN: Settings Form (3/5 width) */}
        <div className="lg:col-span-3 space-y-6">
          <div className="rounded-xl border-2 border-black bg-[#E8F0FE] p-6 shadow-sm dark:border-[#7790bf] dark:bg-[linear-gradient(145deg,#254478,#182235_62%,#171411)]">
            <h2 className="mb-4 text-lg font-bold uppercase tracking-tight text-black dark:text-white flex items-center gap-2">
              <span className="text-xl">⚙️</span> Settings Form
            </h2>
            <ProfileSettingsForm onChange={setPreviewData} />
          </div>
        </div>

        {/* RIGHT COLUMN: Live Profile Preview (2/5 width) */}
        <div className="lg:col-span-2 space-y-6">
          <div className="sticky top-28 rounded-xl border-2 border-black bg-white p-5 shadow-sm dark:bg-[#121218] dark:border-[#3a3a45] flex flex-col">
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-dashed border-gray-250 dark:border-gray-800">
              <h3 className="text-sm font-bold uppercase text-black dark:text-white flex items-center gap-1.5">
                <Eye size={16} className="text-primary" /> Live Preview
              </h3>
              {user?.username && (
                <button
                  onClick={handleCopyLink}
                  className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-bold border border-black rounded-md bg-surface hover:bg-black hover:text-white transition-all dark:bg-[#1c1c24] dark:border-[#3a3a45]"
                  title="Copy public profile link"
                >
                  {copied ? (
                    <Check size={10} className="text-green-500" />
                  ) : (
                    <Copy size={10} />
                  )}
                  <span>{copied ? "Copied!" : "Share Link"}</span>
                </button>
              )}
            </div>

            {/* COVER IMAGE */}
            <div className="h-24 w-full border-2 border-black rounded-lg overflow-hidden bg-slate-100 mb-4 relative">
              {coverPreview ? (
                <img
                  src={coverPreview}
                  alt="Cover preview"
                  className="w-full h-full object-cover"
                />
              ) : user?.cover_image_url ? (
                <img
                  src={getMediaUrl(user.cover_image_url) || ""}
                  alt="User cover"
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 opacity-60 flex items-center justify-center font-bold text-white text-[10px] uppercase tracking-wider">
                  No Cover Image
                </div>
              )}
            </div>

            {/* AVATAR */}
            <div className="flex justify-center mb-4">
              <div className="h-20 w-20 rounded-xl border-2 border-black bg-slate-50 overflow-hidden shadow-sm dark:border-[#3a3a45] dark:bg-[#1c1c24] flex items-center justify-center">
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
                  <span className="text-3xl font-black uppercase text-black dark:text-white">
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
              <p className="text-sm font-bold text-muted mt-1">
                {previewData.email || user?.email}
              </p>

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
              <h5 className="text-xs font-black uppercase text-slate-400 mb-2">
                Bio Preview
              </h5>
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
              {!previewData.github_url &&
                !previewData.linkedin_url &&
                !previewData.twitter_url && (
                  <span className="text-xs font-bold text-slate-400 italic">
                    No social links configured
                  </span>
                )}
            </div>
          </div>
        </div>
      </div>

    </div>
  );

}
=======
}

export default ProfileSettingsPage;

