import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchApi, getMediaUrl } from "../lib/api";
import { ActivityHeatmap } from "../components/ui/ActivityHeatmap";
import {
  Github,
  Linkedin,
  Twitter,
  Award,
  BookOpen,
  Calendar,
  MapPin,
  Copy,
  Check,
} from "lucide-react";

interface UserProfileData {
  user: {
    id: number;
    username: string;
    email: string;
    is_staff: boolean;
    avatar_url: string | null;
    cover_image_url: string | null;
    timezone: string;
    twitter_url: string;
    linkedin_url: string;
    github_url: string;
    bio?: string;
  };
  badges: Array<{
    id: number;
    earned_at: string;
    badge: {
      name: string;
      description: string;
      icon_url?: string;
      slug: string;
    };
  }>;
  total_score: number;
  completed_lessons: number;
}

export function UserProfilePage() {
  const { username } = useParams<{ username: string }>();
  const [profile, setProfile] = useState<UserProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleCopyLink = () => {
    const profileLink = `${window.location.origin}/u/${username}`;
    navigator.clipboard.writeText(profileLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchApi(
          `/accounts/profile/${encodeURIComponent(username || "")}/`,
          {
            requireAuth: false,
          },
        );
        setProfile(data);
      } catch (err: unknown) {
        const errorMsg =
          err instanceof Error ? err.message : "Failed to load profile.";
        setError(errorMsg);
      } finally {
        setLoading(false);
      }
    };

    if (username) {
      fetchProfile();
    }
  }, [username]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface dark:bg-[#0a0a0f]">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-surface p-6 dark:bg-[#0a0a0f]">
        <div className="max-w-md rounded-2xl border-4 border-black bg-white p-8 text-center shadow-card dark:bg-[#121218] dark:border-[#3a3a45]">
          <div className="text-6xl mb-4">🔍</div>
          <h2 className="text-2xl font-black text-black dark:text-white uppercase mb-2">
            Profile Not Found
          </h2>
          <p className="text-muted mb-6">
            {error || "The user you are looking for does not exist."}
          </p>
          <Link
            to="/"
            className="inline-block px-6 py-3 bg-primary text-black font-bold rounded-xl border-4 border-black shadow-card-sm hover:-translate-y-0.5 transition-all"
          >
            Go back Home
          </Link>
        </div>
      </div>
    );
  }

  const { user, badges, total_score, completed_lessons } = profile;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      {/* HEADER WITH SHARE BUTTON */}
      <div className="flex items-center justify-between mb-8 pb-4 border-b border-outline">
        <div>
          <h1 className="text-4xl font-black text-black dark:text-white uppercase tracking-tight">
            User Profile
          </h1>
          <p className="mt-1 text-sm font-medium text-muted">
            Viewing {user.username}'s public stats and badges
          </p>
        </div>
        <button
          onClick={handleCopyLink}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-black border-4 border-black rounded-xl bg-surface hover:bg-black hover:text-white transition-all dark:bg-[#1c1c24] dark:border-[#3a3a45] shadow-card-sm active:translate-y-0 hover:-translate-y-0.5"
          title="Copy profile link"
        >
          {copied ? <Check size={16} className="text-green-500" /> : <Copy size={16} />}
          <span>{copied ? "Copied Link!" : "Share Profile"}</span>
        </button>
      </div>

      {/* USER INFORMATION */}
      <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
        {/* Left Column: Stats & Socials */}
        <div className="space-y-6 md:col-span-1">
          <div className="rounded-3xl border-4 border-black bg-white p-6 shadow-card dark:bg-[#121218] dark:border-[#3a3a45]">
            {/* AVATAR */}
            <div className="flex justify-center mb-6">
              <div className="h-32 w-32 rounded-2xl border-4 border-black bg-slate-50 overflow-hidden shadow-card dark:border-[#3a3a45] dark:bg-[#1c1c24] flex items-center justify-center">
                {user.avatar_url ? (
                  <img
                    src={getMediaUrl(user.avatar_url) || ""}
                    alt={user.username}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <span className="text-5xl font-black uppercase text-black dark:text-white">
                    {user.username.charAt(0)}
                  </span>
                )}
              </div>
            </div>

            <h2 className="text-3xl font-black text-center text-black dark:text-white mb-1">
              {user.username}
            </h2>
            {user.is_staff && (
              <div className="text-center mb-4">
                <span className="inline-block px-2.5 py-0.5 rounded-full text-xs font-black bg-black text-white dark:bg-[#e2e8f0] dark:text-black">
                  STAFF
                </span>
              </div>
            )}

            <div className="space-y-3 mt-4 text-sm font-bold text-muted-foreground">
              <div className="flex items-center gap-2">
                <Calendar size={18} />
                <span>
                  Joined{" "}
                  {new Date(
                    user.timezone
                      ? new Date().toLocaleString("en-US", {
                          timeZone: user.timezone,
                        })
                      : new Date(),
                  ).toLocaleDateString(undefined, {
                    month: "long",
                    year: "numeric",
                  })}
                </span>
              </div>
              {user.timezone && (
                <div className="flex items-center gap-2">
                  <MapPin size={18} />
                  <span>Timezone: {user.timezone}</span>
                </div>
              )}
            </div>

            {/* Social Links */}
            <div className="flex items-center gap-3 mt-6 pt-6 border-t-2 border-dashed border-gray-200 dark:border-gray-800">
              {user.github_url && (
                <a
                  href={user.github_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2.5 rounded-xl border-2 border-black bg-surface hover:bg-black hover:text-white transition-all dark:bg-[#1c1c24] dark:border-[#3a3a45]"
                  aria-label="GitHub Profile"
                >
                  <Github size={20} />
                </a>
              )}
              {user.linkedin_url && (
                <a
                  href={user.linkedin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2.5 rounded-xl border-2 border-black bg-surface hover:bg-[#0077b5] hover:text-white transition-all dark:bg-[#1c1c24] dark:border-[#3a3a45]"
                  aria-label="LinkedIn Profile"
                >
                  <Linkedin size={20} />
                </a>
              )}
              {user.twitter_url && (
                <a
                  href={user.twitter_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2.5 rounded-xl border-2 border-black bg-surface hover:bg-[#1da1f2] hover:text-white transition-all dark:bg-[#1c1c24] dark:border-[#3a3a45]"
                  aria-label="Twitter Profile"
                >
                  <Twitter size={20} />
                </a>
              )}
              {!user.github_url && !user.linkedin_url && !user.twitter_url && (
                <span className="text-xs font-semibold text-muted">
                  No social links set
                </span>
              )}
            </div>
          </div>

          {/* Quick Stats Widget */}
          <div className="rounded-3xl border-4 border-black bg-[#E8F0FE] p-6 shadow-card dark:bg-[#182235] dark:border-[#7790bf]">
            <h3 className="text-lg font-black uppercase text-black dark:text-white mb-4">
              Statistics
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-2xl border-2 border-black bg-white p-4 text-center dark:bg-[#121218] dark:border-[#3a3a45]">
                <BookOpen size={24} className="mx-auto mb-2 text-primary" />
                <div className="text-2xl font-black text-black dark:text-white">
                  {completed_lessons}
                </div>
                <div className="text-xs font-bold text-muted">Lessons</div>
              </div>
              <div className="rounded-2xl border-2 border-black bg-white p-4 text-center dark:bg-[#121218] dark:border-[#3a3a45]">
                <Award size={24} className="mx-auto mb-2 text-accent" />
                <div className="text-2xl font-black text-black dark:text-white">
                  {total_score}
                </div>
                <div className="text-xs font-bold text-muted">XP Points</div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Bio & Badges */}
        <div className="space-y-6 md:col-span-2">
          {/* Bio Section */}
          <div className="rounded-3xl border-4 border-black bg-white p-6 shadow-card dark:bg-[#121218] dark:border-[#3a3a45]">
            <h3 className="text-xl font-black uppercase text-black dark:text-white mb-4">
              About Me
            </h3>
            <p className="text-lg font-medium leading-relaxed text-black/80 dark:text-[#94a3b8]">
              {user.bio ||
                "This user is too busy contributing to write a bio yet."}
            </p>
          </div>

          {/* Achievements / Earned Badges */}
          <div className="rounded-3xl border-4 border-black bg-[#FFF0E5] p-6 shadow-card dark:bg-[#302319] dark:border-[#b47c3f]">
            <h3 className="text-xl font-black uppercase text-black dark:text-white mb-4">
              Achievements
            </h3>
            {badges.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {badges.map((badgeItem) => (
                  <div
                    key={badgeItem.id}
                    className="flex items-center gap-4 rounded-2xl border-2 border-black bg-white p-4 shadow-card-sm dark:bg-[#121218] dark:border-[#3a3a45]"
                  >
                    <div className="text-3xl">🏅</div>
                    <div>
                      <h4 className="font-black text-black dark:text-white text-sm">
                        {badgeItem.badge.name}
                      </h4>
                      <p className="text-xs font-bold text-muted leading-tight">
                        {badgeItem.badge.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-6 bg-white dark:bg-[#121218] rounded-2xl border-2 border-black dark:border-[#3a3a45]">
                <span className="text-4xl">🌟</span>
                <p className="text-sm font-bold text-muted mt-2">
                  No badges earned yet. Keep learning!
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ACTIVITY HEATMAP SECTION */}
      <div className="mt-8 rounded-3xl border-4 border-black bg-white dark:bg-[#121218] dark:border-[#3a3a45] p-8 shadow-card overflow-hidden">
        <ActivityHeatmap username={user.username} />
      </div>
    </div>
  );
}

export default UserProfilePage;
