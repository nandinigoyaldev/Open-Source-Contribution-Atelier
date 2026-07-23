import { AdminDashboard } from "../components/dashboard/AdminDashboard";
import { useAuth } from "../features/auth/AuthContext";
import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";
import { mockStudentStats, getTipOfTheDay } from "../lib/dashboardMockData";
import { Link } from "react-router-dom";
import SkeletonCard from "../components/ui/skeletons/SkeletonCard";
import { PRReviewPredictionWidget } from "../components/PRReviewPredictionWidget";
import SkeletonAdminDashboard from "../components/ui/skeletons/SkeletonAdminDashboard";
import { useState, useMemo } from "react";
import { useUserProgress } from "../hooks/useUserProgress";
import { useBookmarks } from "../hooks/useBookmarks";
import { useOfflineReadyLessons } from "../hooks/useOfflineReadyLessons";
import { useCurriculumLessons } from "../hooks/useCurriculum";
import { BADGES } from "../constants/badges";

import {
  Flame,
  ArrowRight,
  Bookmark,
  Lock,
  BookOpen,
  Award,
  Sparkles,
} from "lucide-react";
import { AvailableOfflineBadge } from "../components/ui/AvailableOfflineBadge";
import { CARD_FOCUS_RING } from "../lib/a11yFocus";

export function DashboardPage() {
  const { user } = useAuth();
  const { isLoading: progressLoading, isLessonCompleted } = useUserProgress();
  const { bookmarks, toggleBookmark } = useBookmarks();

  const { lessons, isLoading: lessonsLoading } = useCurriculumLessons();

  const lessonRefs = useMemo(
    () =>
      lessons.map((l) => ({
        slug: l.slug,
        filePath: l.filePath,
      })),
    [lessons],
  );
  const { isOfflineReady } = useOfflineReadyLessons(lessonRefs);

  const lessonQueue = useMemo(() => {
    const incomplete = lessons.filter((l) => !isLessonCompleted(l.slug));
    return incomplete.slice(0, 3).map((l, index) => ({
      number: index + 1,
      title: l.title,
      description: l.description,
      slug: l.slug,
      filePath: l.filePath,
    }));
  }, [lessons, isLessonCompleted]);

  const { isLoading: contributorLoading } = useQuery({
    queryKey: ["contributorStats"],
    queryFn: () =>
      fetchApi("/dashboard/stats/", {
        suppressErrorToast: true,
        timeoutMs: 2000,
      }),
    enabled: !!user && !user.is_staff,
  });

  const showSkeleton = progressLoading || lessonsLoading || contributorLoading;

  const tip = useMemo(() => getTipOfTheDay(), []);

  const [showCertificate, setShowCertificate] = useState(false);
  const [showProgressReport, setShowProgressReport] = useState(false);

  const stats = mockStudentStats;

  const completedLessonsCount = lessons.filter((l) =>
    isLessonCompleted(l.slug),
  ).length;
  const totalLessonsCount = lessons.length;
  const completionPercentage =
    totalLessonsCount > 0
      ? Math.round((completedLessonsCount / totalLessonsCount) * 100)
      : 0;

  const { data: certificateData } = useQuery({
    queryKey: ["userCertificate"],
    queryFn: () =>
      fetchApi("/progress/certificate/", { suppressErrorToast: true }),
    enabled: !!user && !user.is_staff && completionPercentage === 100,
    retry: false,
  });

  if (showSkeleton) {
    if (user?.is_staff) {
      return (
        <div aria-busy="true" role="status">
          <SkeletonAdminDashboard />
          <span className="sr-only">Loading admin dashboard...</span>
        </div>
      );
    }
    return (
      <div className="max-w-4xl mx-auto px-4 pt-28 pb-12 animate-pulse space-y-6">
        <div className="h-20 bg-gray-200 dark:bg-gray-800 rounded-2xl border-4 border-black" />
        <div className="h-32 bg-gray-200 dark:bg-gray-800 rounded-2xl border-4 border-black" />
        <div className="h-48 bg-gray-200 dark:bg-gray-800 rounded-2xl border-4 border-black" />
      </div>
    );
  }

  if (user?.is_staff) {
    return <AdminDashboard />;
  }

  const moduleProgress =
    stats.currentModule.totalLessons > 0
      ? Math.round(
          (stats.currentModule.lessonsCompleted /
            stats.currentModule.totalLessons) *
            100,
        )
      : 0;

  return (
    <div className="max-w-5xl mx-auto px-4 pt-28 pb-12 space-y-8">
      {/* Welcome + Module Progress */}
      <section className="rounded-[2.5rem] border-4 border-black bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-400 p-8 sm:p-10 shadow-card relative overflow-hidden">
        <div className="absolute -right-10 -bottom-10 text-[12rem] opacity-10 select-none">
          📖
        </div>
        <div className="relative z-10">
          <span className="font-black text-xs bg-white/90 text-black px-4 py-2 rounded-full border-2 border-black inline-block shadow-card-sm mb-4">
            Module {stats.currentModule.number} of {stats.totalModules}
          </span>
          <h1 className="text-3xl sm:text-4xl font-black text-white drop-shadow-[2px_2px_0_rgba(0,0,0,0.3)] mb-2">
            Welcome back, {user?.username || "Learner"}!
          </h1>
          <p className="text-white/90 font-bold text-lg mb-4">
            {stats.currentModule.title}
          </p>
          <div className="max-w-lg">
            <div className="flex justify-between text-sm font-bold text-white/80 mb-1">
              <span>
                {stats.currentModule.lessonsCompleted} of{" "}
                {stats.currentModule.totalLessons} lessons done
              </span>
              <span>{moduleProgress}%</span>
            </div>
            <div className="w-full h-4 bg-white/30 border-2 border-black rounded-full overflow-hidden">
              <div
                className="h-full bg-green-400 border-r-2 border-black transition-all duration-500"
                style={{ width: `${moduleProgress}%` }}
              />
            </div>
          </div>
        </div>
      </section>

      {/* PR Review Delay Prediction Widget */}
      <section>
        <PRReviewPredictionWidget />
      </section>

      {/* Next Lesson + Stats Grid */}

      <section className="grid grid-cols-1 gap-6 md:grid-cols-[1.5fr_1fr]">
        {/* Next Lesson CTA */}
        <div className="rounded-[2rem] border-4 border-black bg-white dark:bg-[#1f1c18] dark:border-[#2e2924] p-6 shadow-card hover:-translate-y-0.5 transition-transform">
          <div className="flex items-start gap-4">
            <div className="bg-amber-100 dark:bg-amber-900/30 p-4 rounded-2xl border-2 border-black flex-shrink-0">
              <BookOpen className="w-8 h-8 text-amber-600 dark:text-amber-400" />
            </div>
            <div className="flex-1">
              <p className="font-black text-xs uppercase tracking-wider text-amber-600 dark:text-amber-400 mb-1">
                Continue Learning
              </p>
              <h3 className="text-2xl font-black dark:text-[#f0ebe2] mb-1">
                {lessonQueue[0]?.title || "All done!"}
              </h3>
              <p className="text-sm font-bold text-gray-500 dark:text-[#c4bbae] mb-4">
                {lessonQueue[0]?.description ||
                  "You've completed all lessons. Amazing!"}
              </p>
              <Link
                to={
                  lessonQueue[0]
                    ? `/lessons/${lessonQueue[0].slug}`
                    : "/content"
                }
                aria-label={
                  lessonQueue[0]
                    ? `Start lesson: ${lessonQueue[0].title}`
                    : "Browse all lessons"
                }
                className={`inline-flex items-center gap-2 rounded-full bg-black text-white px-6 py-3 font-black text-sm border-2 border-black hover:bg-gray-800 transition-colors dark:bg-white dark:text-black dark:hover:bg-gray-200 ${CARD_FOCUS_RING}`}
              >
                Start Lesson <ArrowRight size={16} aria-hidden="true" />
              </Link>
            </div>
          </div>
        </div>

        {/* Streak Card */}
        <div className="rounded-[2rem] border-4 border-black bg-gradient-to-br from-orange-50 to-red-50 dark:from-[#2a1f1a] dark:to-[#1f1410] dark:border-[#2e2924] p-6 shadow-card flex flex-col items-center justify-center text-center">
          <Flame className="w-10 h-10 text-orange-500 mb-2" />
          <span className="text-5xl font-black text-orange-500 drop-shadow-[2px_2px_0_rgba(0,0,0,0.2)]">
            {stats.streakDays}
          </span>
          <span className="font-black text-xs uppercase tracking-widest text-gray-500 dark:text-[#c4bbae] mt-1">
            Day Streak
          </span>
          <p className="text-xs font-bold text-gray-400 dark:text-[#8a7f72] mt-2">
            Best: {stats.longestStreak} days
          </p>
        </div>
      </section>

      {/* Concept / Tip of the Day */}
      <section className="rounded-[2rem] border-4 border-black bg-blue-50 dark:bg-[#1a1f2e] dark:border-[#2e2924] p-6 shadow-card">
        <div className="flex items-start gap-4">
          <div className="bg-white dark:bg-[#151411] p-3 rounded-2xl border-2 border-black flex-shrink-0">
            <Sparkles className="w-6 h-6 text-blue-500" />
          </div>
          <div>
            <span className="font-black text-xs uppercase tracking-wider text-blue-600 dark:text-blue-400 mb-1 block">
              Concept of the Day — Explained Simply
            </span>
            <h3 className="text-xl font-black dark:text-[#f0ebe2] mb-2">
              {tip.title}
            </h3>
            <p className="text-sm font-bold text-gray-600 dark:text-[#c4bbae] leading-relaxed">
              {tip.explanation}
            </p>
          </div>
        </div>
      </section>

      {/* Learning Queue */}
      <section className="rounded-[2.5rem] border-4 border-black bg-white dark:bg-[#1f1c18] dark:border-[#2e2924] p-6 sm:p-8 shadow-card">
        <h2 className="text-2xl font-black mb-6 flex items-center gap-3 dark:text-[#f0ebe2]">
          <span className="bg-indigo-100 dark:bg-indigo-900/30 w-10 h-10 rounded-full border-2 border-black flex items-center justify-center text-lg">
            📚
          </span>
          Your Learning Queue
        </h2>
        <div className="space-y-4">
          {lessonQueue.map((lesson) => (
            <Link
              key={lesson.slug}
              to={`/lessons/${lesson.slug}`}
              aria-label={`Open queued lesson ${lesson.number}: ${lesson.title}`}
              className={`flex items-center justify-between p-5 rounded-lg border-4 border-black bg-gray-50 dark:bg-[#151411] dark:border-[#2e2924] shadow-card-sm hover:shadow-card hover:-translate-y-0.5 transition-all ${CARD_FOCUS_RING}`}
            >
              <div className="flex items-center gap-4 min-w-0">
                <span className="w-8 h-8 rounded-full bg-black text-white font-black text-sm flex items-center justify-center flex-shrink-0 dark:bg-[#2e2924]">
                  {lesson.number}
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-black text-lg dark:text-[#f0ebe2]">
                      {lesson.title}
                    </h3>
                    {isOfflineReady(lesson.slug) && <AvailableOfflineBadge />}
                  </div>
                  <p className="text-sm font-bold text-gray-500 dark:text-[#c4bbae]">
                    {lesson.description}
                  </p>
                </div>
              </div>
              <ArrowRight className="w-5 h-5 text-gray-400 flex-shrink-0" />
            </Link>
          ))}
          {lessonQueue.length === 0 && (
            <p className="text-sm font-bold text-gray-500 dark:text-[#c4bbae] text-center py-4">
              All queued lessons complete — browse the full curriculum below.
            </p>
          )}
          <Link
            to="/content"
            aria-label="Browse all curriculum lessons"
            className={`block text-center rounded-lg border-4 border-black bg-gray-100 dark:bg-[#151411] dark:border-[#2e2924] py-3 font-black text-sm hover:-translate-y-0.5 transition-all dark:text-[#f0ebe2] ${CARD_FOCUS_RING}`}
          >
            Browse All Lessons →
          </Link>
        </div>
      </section>

      {/* Bookmarks */}
      {bookmarks.length > 0 && (
        <section className="rounded-[2.5rem] border-4 border-black bg-gray-50 dark:bg-[#151411] dark:border-[#2e2924] p-6 sm:p-8 shadow-card">
          <h2 className="text-2xl font-black mb-6 flex items-center gap-3 dark:text-[#f0ebe2]">
            <Bookmark className="w-6 h-6" />
            Read Later
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {bookmarks.map((bookmark) => (
              <Link
                key={bookmark.lesson_slug}
                to={`/lessons/${bookmark.lesson_slug}`}
                aria-label={`Open bookmarked lesson: ${bookmark.lesson_title}`}
                className={`flex flex-col gap-2 p-5 rounded-lg border-4 border-black bg-white dark:bg-[#1f1c18] dark:border-[#2e2924] shadow-card-sm hover:shadow-card hover:-translate-y-0.5 transition-all ${CARD_FOCUS_RING}`}
              >
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-black text-lg leading-tight dark:text-[#f0ebe2] pr-4">
                    {bookmark.lesson_title}
                  </h3>
                  <button
                    type="button"
                    aria-label={`Remove bookmark for ${bookmark.lesson_title}`}
                    className={`rounded-md p-1 ${CARD_FOCUS_RING}`}
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      toggleBookmark.mutate({
                        slug: bookmark.lesson_slug,
                        isBookmarked: true,
                      });
                    }}
                  >
                    <Bookmark
                      className="fill-primary text-primary hover:opacity-60 transition-opacity"
                      size={20}
                      aria-hidden="true"
                    />
                  </button>
                </div>
                <div className="flex justify-between items-center mt-auto pt-4">
                  <span className="font-black text-[10px] bg-black text-white px-2 py-0.5 rounded-full uppercase dark:bg-[#2e2924]">
                    {bookmark.lesson_category}
                  </span>
                  <span className="text-xs font-bold text-gray-500 dark:text-[#c4bbae]">
                    {bookmark.lesson_estimated_minutes} min
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Achievements */}
      <section className="rounded-[2.5rem] border-4 border-black bg-white dark:bg-[#151411] dark:border-[#2e2924] p-6 sm:p-8 shadow-card">
        <h2 className="text-2xl font-black mb-6 flex items-center gap-3 dark:text-[#f0ebe2]">
          <Award className="w-7 h-7 text-amber-500" />
          Achievements
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
          {BADGES.map((badge) => {
            const isEarned = stats.earnedBadges.includes(badge.id);
            return (
              <div
                key={badge.id}
                className={`relative rounded-2xl border-4 border-black p-4 flex flex-col items-center text-center shadow-card-sm transition-all ${
                  isEarned
                    ? "bg-white dark:bg-[#1f1c18] hover:-translate-y-1"
                    : "bg-gray-50/30 opacity-50 dark:bg-black/20"
                }`}
              >
                <div className={`text-4xl mb-2 ${isEarned ? "" : "grayscale"}`}>
                  {badge.icon}
                </div>
                <h4 className="font-black text-xs mb-1 dark:text-[#f0ebe2]">
                  {badge.name}
                </h4>
                <p className="text-[9px] font-bold text-gray-500 dark:text-[#c4bbae]">
                  {badge.desc}
                </p>
                {isEarned ? (
                  <span className="absolute top-1 right-1 bg-green-100 text-green-700 border-2 border-green-700 text-[7px] font-black px-1.5 py-0.5 rounded-full">
                    ✓
                  </span>
                ) : (
                  <span className="absolute top-1 right-1 text-gray-300">
                    <Lock size={10} />
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* Stats Footer */}
      <section className="rounded-[2rem] border-4 border-black bg-gradient-to-r from-gray-50 to-gray-100 dark:from-[#1f1c18] dark:to-[#151411] dark:border-[#2e2924] p-6 shadow-card">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 text-center">
          <div>
            <span className="text-3xl font-black text-indigo-600 dark:text-indigo-400">
              {completedLessonsCount}
            </span>
            <p className="font-black text-xs uppercase tracking-wider text-gray-500 dark:text-[#c4bbae] mt-1">
              Lessons Done
            </p>
          </div>
          <div>
            <span className="text-3xl font-black text-green-600 dark:text-green-400">
              {stats.xp}
            </span>
            <p className="font-black text-xs uppercase tracking-wider text-gray-500 dark:text-[#c4bbae] mt-1">
              XP Earned
            </p>
          </div>
          <div>
            <span className="text-3xl font-black text-orange-600 dark:text-orange-400">
              {stats.streakDays}
            </span>
            <p className="font-black text-xs uppercase tracking-wider text-gray-500 dark:text-[#c4bbae] mt-1">
              Day Streak
            </p>
          </div>
          <div>
            <span className="text-3xl font-black text-purple-600 dark:text-purple-400">
              {stats.modulesCompleted}/{stats.totalModules}
            </span>
            <p className="font-black text-xs uppercase tracking-wider text-gray-500 dark:text-[#c4bbae] mt-1">
              Modules Done
            </p>
          </div>
        </div>
      </section>

      {/* Certificate / Progress Report */}
      <section className="flex gap-4 justify-center">
        {completionPercentage === 100 && (
          <button
            type="button"
            onClick={() => setShowCertificate(true)}
            className={`rounded-full bg-green-500 text-white border-4 border-black px-8 py-3 font-black text-sm shadow-card-sm hover:-translate-y-0.5 transition-all ${CARD_FOCUS_RING}`}
          >
            🎓 View Certificate
          </button>
        )}
        <button
          type="button"
          onClick={() => setShowProgressReport(true)}
          className={`rounded-full bg-white dark:bg-[#1f1c18] border-4 border-black px-8 py-3 font-black text-sm shadow-card-sm hover:-translate-y-0.5 transition-all dark:text-[#f0ebe2] ${CARD_FOCUS_RING}`}
        >
          📊 View Progress Report
        </button>
      </section>

      {/* Certificate Modal */}
      {showCertificate && (
        <div className="fixed inset-0 bg-black/75 z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white dark:bg-[#1f1c18] rounded-2xl border-4 border-black shadow-card p-8 text-center space-y-4">
            <h2 className="text-3xl font-black dark:text-[#f0ebe2]">
              🎓 Certificate
            </h2>
            <p className="text-sm font-bold text-gray-500 dark:text-[#c4bbae]">
              {certificateData?.certificate?.verification_hash
                ? `Hash: ${certificateData.certificate.verification_hash}`
                : "Complete all lessons to unlock your certificate!"}
            </p>
            <button
              onClick={() => setShowCertificate(false)}
              className="rounded-full bg-black text-white border-4 border-black px-6 py-2 font-black text-sm"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* Progress Report Modal */}
      {showProgressReport && (
        <div className="fixed inset-0 bg-black/75 z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white dark:bg-[#1f1c18] rounded-2xl border-4 border-black shadow-card p-8 space-y-4">
            <h2 className="text-3xl font-black text-center dark:text-[#f0ebe2]">
              📊 Progress
            </h2>
            <div className="space-y-3">
              <div className="flex justify-between font-bold">
                <span>Lessons Completed</span>
                <span>
                  {completedLessonsCount}/{totalLessonsCount}
                </span>
              </div>
              <div className="flex justify-between font-bold">
                <span>Total XP</span>
                <span>{stats.xp}</span>
              </div>
              <div className="flex justify-between font-bold">
                <span>Current Streak</span>
                <span>{stats.streakDays} days</span>
              </div>
              <div className="flex justify-between font-bold">
                <span>Badges Earned</span>
                <span>
                  {stats.earnedBadges.length}/{BADGES.length}
                </span>
              </div>
            </div>
            <button
              onClick={() => window.print()}
              className="w-full rounded-full bg-black text-white border-4 border-black py-3 font-black text-sm hover:-translate-y-0.5 transition-all"
            >
              🖨️ Print Report
            </button>
            <button
              onClick={() => setShowProgressReport(false)}
              className="w-full rounded-full bg-white dark:bg-[#151411] border-4 border-black py-3 font-black text-sm dark:text-[#f0ebe2]"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default DashboardPage;
