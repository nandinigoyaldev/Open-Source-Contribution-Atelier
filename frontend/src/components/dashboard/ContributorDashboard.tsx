import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Award,
  Bookmark,
  Download,
  Lock,
  Sparkles,
  Users,
} from "lucide-react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import { useAuth } from "../../features/auth/AuthContext";
import { useTheme } from "../../hooks/useTheme";
import { useBookmarks } from "../../hooks/useBookmarks";
import { useUserProgress } from "../../hooks/useUserProgress";
import { fetchApi } from "../../lib/api";
import { fetchLessonsApi, type Lesson } from "../../lib/lessons";
import { BADGES } from "../../constants/badges";
import { DailyQuoteWidget } from "../ui/DailyQuoteWidget";
import { NotesWidget } from "../ui/NotesWidget";
import { OnboardingTour } from "../ui/OnboardingTour";
import { RecommendationsList } from "../ui/RecommendationsList";
import SkeletonContributorDashboard from "../ui/skeletons/SkeletonContributorDashboard";
import { CertificateModal } from "./CertificateModal";
import { ProgressReportModal } from "./ProgressReportModal";
import { StatsCards } from "./StatsCards";
import { AchievementCardModal } from "./AchievementCardModal";
import { LessonsChart } from "../LessonsChart";
import type {
  CertificateResponse,
  ContributorDashboardData,
  GitHubContributor,
  LearningPathData,
  ModuleData,
} from "./types";

const FACTS = [
  "Git was created in 2005 by Linus Torvalds because he was frustrated with the commercial tool they were using for Linux development.",
  "Modern servers run on Linux, browsers run on Chromium, and compilers run on open source languages: the internet is built on OSS.",
  "The term 'Open Source' was officially adopted in 1998 in Palo Alto, California, to make software sharing more business-friendly.",
  "Richard Stallman launched the GNU Project in 1983, publishing the GNU Manifesto to advocate for computer user freedoms.",
  "Spamming duplicate or low-effort pull requests (like formatting comments) wastes maintainers' time and can get you blocked.",
  "The Apache HTTP Server project was founded in 1995 and played a key role in the early expansion of the World Wide Web.",
];

const CONTRIBUTORS_CACHE_KEY = "github_contributors_cache";
const CACHE_EXPIRY = 24 * 60 * 60 * 1000;

interface ContributorsCache {
  data: GitHubContributor[];
  timestamp: number;
}

export function ContributorDashboard() {
  const { user } = useAuth();
  const { theme } = useTheme();
  const { isLessonCompleted } = useUserProgress();
  const { bookmarks, toggleBookmark } = useBookmarks();

  const [curriculumData, setCurriculumData] = useState<ModuleData[]>([]);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [onboardingStep, setOnboardingStep] = useState(0);
  const [showCertificate, setShowCertificate] = useState(false);
  const [showAchievementCard, setShowAchievementCard] = useState(false);
  const [showProgressReport, setShowProgressReport] = useState(false);
  const [gitHubContributors, setGitHubContributors] = useState<
    GitHubContributor[]
  >([]);
  const [showOnlyBookmarked, setShowOnlyBookmarked] = useState(false);

  useEffect(() => {
    fetch("/content/curriculum.json")
      .then((response) => response.json())
      .then((data: { modules?: ModuleData[] }) => {
        if (data.modules) setCurriculumData(data.modules);
      })
      .catch((error) =>
        console.error("Error loading dashboard curriculum:", error),
      );
  }, []);

  const {
    data: contributorData,
    isLoading: isContributorLoading,
    error: contributorError,
  } = useQuery<ContributorDashboardData>({
    queryKey: ["contributorDashboardStats"],
    queryFn: async () =>
      (await fetchApi("/dashboard/contributor/", {
        suppressErrorToast: true,
      })) as ContributorDashboardData,
  });

  const { data: lessons = [], isLoading: isLessonsLoading } = useQuery<
    Lesson[]
  >({
    queryKey: ["lessons"],
    queryFn: fetchLessonsApi,
  });

  const { data: learningPathData } = useQuery<LearningPathData>({
    queryKey: ["learningPath"],
    queryFn: async () =>
      (await fetchApi("/users/me/learning-path/")) as LearningPathData,
  });

  const { data: lessonStats } = useQuery<any>({
    queryKey: ["daily-lesson-stats"],
    queryFn: () => fetchApi("/progress/daily-stats/"),
  });

  const isLoading = isContributorLoading || isLessonsLoading;
  const [showSkeleton, setShowSkeleton] = useState(isLoading);

  useEffect(() => {
    if (isLoading) {
      setShowSkeleton(true);
      return;
    }
    const timer = setTimeout(() => setShowSkeleton(false), 400);
    return () => clearTimeout(timer);
  }, [isLoading]);

  const factOfDay = useMemo(() => {
    const day = new Date().getDate();
    return FACTS[day % FACTS.length];
  }, []);

  useEffect(() => {
    const fallbackContributors: GitHubContributor[] = [
      {
        login: "goyaljiiiiii",
        avatar_url: "https://github.com/goyaljiiiiii.png",
        html_url: "https://github.com/goyaljiiiiii",
      },
      {
        login: "nandini",
        avatar_url: "https://github.com/github.png",
        html_url: "https://github.com",
      },
      {
        login: "antigravity",
        avatar_url: "https://github.com/google.png",
        html_url: "https://github.com",
      },
    ];

    fetch(
      "https://api.github.com/repos/goyaljiiiiii/Open-Source-Contribution-Atelier/contributors",
    )
      .then((response) => {
        if (!response.ok) throw new Error("API Limit");
        return response.json();
      })
      .then((data: GitHubContributor[]) => {
        if (!Array.isArray(data)) return;
        const contributors = data.slice(0, 8);
        setGitHubContributors(contributors);
        localStorage.setItem(
          CONTRIBUTORS_CACHE_KEY,
          JSON.stringify({ data: contributors, timestamp: Date.now() }),
        );
      })
      .catch(() => {
        const cachedData = localStorage.getItem(CONTRIBUTORS_CACHE_KEY);
        if (cachedData) {
          try {
            const parsedCache = JSON.parse(cachedData) as ContributorsCache;
            if (Date.now() - parsedCache.timestamp < CACHE_EXPIRY) {
              setGitHubContributors(parsedCache.data);
              return;
            }
            localStorage.removeItem(CONTRIBUTORS_CACHE_KEY);
          } catch {
            localStorage.removeItem(CONTRIBUTORS_CACHE_KEY);
          }
        }
        setGitHubContributors(fallbackContributors);
      });
  }, []);

  useEffect(() => {
    if (!user?.is_staff) {
      const isBoarded = localStorage.getItem("atelier_onboarded");
      if (!isBoarded) setShowOnboarding(true);
    }
  }, [user]);

  const handleFinishOnboarding = () => {
    localStorage.setItem("atelier_onboarded", "true");
    setShowOnboarding(false);
  };

  const {
    completedLessonsCount,
    totalLessonsCount,
    completionPercentage,
    activeLessonsQueue,
    earnedBadges,
  } = useMemo(() => {
    if (!lessons.length || !curriculumData.length) {
      return {
        completedLessonsCount: 0,
        totalLessonsCount: 0,
        completionPercentage: 0,
        activeLessonsQueue: [] as Lesson[],
        earnedBadges: [] as string[],
      };
    }

    const total = lessons.length;
    const completed = lessons.filter((lesson) =>
      isLessonCompleted(lesson.slug),
    ).length;
    const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;
    let queue = lessons.filter((lesson) => !isLessonCompleted(lesson.slug));
    if (showOnlyBookmarked) {
      const bookmarkedSlugs = new Set(bookmarks.map((b) => b.lesson_slug));
      queue = queue.filter((lesson) => bookmarkedSlugs.has(lesson.slug));
    }
    queue = queue.slice(0, 3);

    const earned = new Set<string>(
      contributorData?.personal_stats?.earned_badges || [],
    );
    curriculumData.forEach((module, index) => {
      if (module.lessons.every((lesson) => isLessonCompleted(lesson.slug))) {
        earned.add(`mod-${index + 1}`);
      }
    });
    if (percentage === 100) earned.add("grad");

    return {
      completedLessonsCount: completed,
      totalLessonsCount: total,
      completionPercentage: percentage,
      activeLessonsQueue: queue,
      earnedBadges: Array.from(earned),
    };
  }, [
    lessons,
    curriculumData,
    isLessonCompleted,
    contributorData,
    showOnlyBookmarked,
    bookmarks,
  ]);

  const { data: certificateData } = useQuery<CertificateResponse>({
    queryKey: ["userCertificate"],
    queryFn: async () =>
      (await fetchApi("/progress/certificate/", {
        suppressErrorToast: true,
      })) as CertificateResponse,
    enabled: completionPercentage === 100,
    retry: false,
  });

  if (showSkeleton) {
    return (
      <div aria-busy="true" role="status">
        <SkeletonContributorDashboard />
        <span className="sr-only">Loading dashboard...</span>
      </div>
    );
  }

  if (contributorError || !contributorData) {
    return (
      <div className="pt-24 max-w-7xl mx-auto px-4">
        <div className="p-8 text-center bg-red-100 rounded-2xl border-4 border-black font-bold">
          Failed to load Contributor stats. Make sure Django backend server is
          running.
        </div>
      </div>
    );
  }

  const { personal_stats, assigned_issues } = contributorData;

  return (
    <div className="max-w-7xl mx-auto px-4 pb-12 space-y-8">
      <OnboardingTour run={showOnboarding} onFinish={handleFinishOnboarding} />
      <NotesWidget />

      {/* 1. Header Banner & Stats */}
      <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div
          id="tour-welcome"
          className="rounded-[24px] border-2 border-black/10 bg-gradient-to-br from-[#c3c0ff]/10 to-[#ffb5e8]/10 dark:bg-gradient-to-br dark:from-[#2e2640]/50 dark:to-[#4d3a60]/30 p-8 shadow-sm relative overflow-hidden flex flex-col justify-between min-h-[220px] dark:border-white/10"
        >
          <div className="relative z-10 space-y-4">
            <span className="font-mono text-[10px] font-black bg-[#C3C0FF] text-black px-3.5 py-1.5 rounded-full border border-black/10 uppercase tracking-widest inline-block dark:bg-[#2e2640] dark:text-[#f0ebe2] dark:border-white/10">
              LEVEL{" "}
              {completedLessonsCount === totalLessonsCount
                ? "MAX 🎓"
                : Math.floor(completedLessonsCount / 3) + 1}{" "}
              CONTRIBUTOR
            </span>
            <div className="space-y-2">
              <h1 className="text-3xl sm:text-4xl font-black text-slate-900 dark:text-white leading-tight">
                Welcome back, {user?.username}.
              </h1>
              <p className="text-sm text-slate-600 dark:text-[#c4bbae] max-w-xl leading-relaxed">
                You have completed <span className="font-extrabold text-slate-800 dark:text-white">{completedLessonsCount}</span> of <span className="font-extrabold text-slate-800 dark:text-white">{totalLessonsCount}</span> learning modules, earning{" "}
                <span className="text-[#8884d8] font-black">{personal_stats.total_xp} XP</span>.
              </p>
            </div>
          </div>
          <div className="mt-6 flex flex-wrap gap-2.5 z-10">
            <button
              onClick={() => setShowAchievementCard(true)}
              className="flex items-center gap-2 px-4 py-2 bg-slate-900 text-white text-xs font-bold border border-slate-800 rounded-xl hover:-translate-y-0.5 transition-all shadow-sm whitespace-nowrap dark:bg-white dark:text-black dark:border-white"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Share Standing Card
            </button>
            <button
              onClick={() => setShowProgressReport(true)}
              className="flex items-center gap-2 px-4 py-2 bg-white text-slate-700 text-xs font-bold border border-slate-200 rounded-xl hover:-translate-y-0.5 transition-all shadow-sm whitespace-nowrap dark:bg-[#1a1a24] dark:text-[#eef2f6] dark:border-slate-800"
            >
              <Download className="w-3.5 h-3.5" /> Export Progress (PDF)
            </button>
          </div>
        </div>

        <StatsCards
          personalStats={personal_stats}
          completedLessonsCount={completedLessonsCount}
        />
      </section>

      {/* 2. Personalized Next Step */}
      {learningPathData?.next_step && (
        <section className="rounded-[24px] border border-black/5 bg-white p-6 shadow-sm dark:bg-[#1f1c18] dark:border-white/5 space-y-5">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div className="flex items-start gap-4">
              <div className="bg-[#ffcc00]/10 p-3 rounded-2xl border border-[#ffcc00]/20 flex-shrink-0 text-2xl dark:bg-[#ffcc00]/20 dark:text-[#ffcc00]">
                🎯
              </div>
              <div className="space-y-1">
                <h3 className="font-black text-xl text-slate-800 dark:text-[#f0ebe2] flex items-center gap-2">
                  Your Personalized Next Step
                  <span className="font-mono text-[9px] bg-slate-100 text-slate-600 px-2.5 py-0.5 rounded-full uppercase dark:bg-slate-800 dark:text-slate-350">
                    {learningPathData.next_step.id}
                  </span>
                </h3>
                <p className="font-bold text-xs text-muted dark:text-[#c4bbae]">
                  Focus Module:{" "}
                  <span className="text-text dark:text-[#f0ebe2] font-black">
                    {learningPathData.next_step.title}
                  </span>{" "}
                  ({learningPathData.next_step.status})
                </p>
              </div>
            </div>
            <Link
              to="/learning-path"
              className="w-full md:w-auto rounded-lg bg-[#C3C0FF] text-black border border-black/5 px-4 py-2 text-xs font-black hover:-translate-y-0.5 shadow-sm transition-all text-center uppercase tracking-wider dark:bg-[#2e2640] dark:text-[#f0ebe2]"
            >
              View Learning Path 🗺️
            </Link>
          </div>

          <div className="grid gap-6 md:grid-cols-[1.4fr_0.6fr] pt-4 border-t border-slate-100 dark:border-slate-850">
            <div className="space-y-4 flex flex-col justify-between">
              <p className="text-xs font-bold text-slate-600 dark:text-[#f0ebe2] leading-relaxed">
                {learningPathData.next_step.description}
              </p>
              <div className="space-y-2">
                <div className="flex justify-between text-[11px] font-black">
                  <span>Module Progress</span>
                  <span>
                    {learningPathData.next_step.completed_lessons_count} /{" "}
                    {learningPathData.next_step.lessons_count} lessons Completed
                  </span>
                </div>
                <div className="w-full h-3 bg-slate-100 border border-slate-200/50 rounded-full overflow-hidden dark:bg-[#151411] dark:border-[#2e2924]">
                  <div
                    className="h-full bg-green-500 transition-all duration-500"
                    style={{
                      width: `${
                        learningPathData.next_step.lessons_count > 0
                          ? (learningPathData.next_step
                              .completed_lessons_count /
                              learningPathData.next_step.lessons_count) *
                            100
                          : 0
                      }%`,
                    }}
                  />
                </div>
              </div>
            </div>

            <div className="border border-slate-100 p-4 rounded-xl bg-slate-50/50 dark:bg-[#1c1915] dark:border-white/5 flex flex-col justify-between gap-3">
              <div className="space-y-1">
                <h4 className="font-black text-[10px] uppercase text-[#ff8000] flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5" /> Recommendation Reason
                </h4>
                <p className="text-[11px] font-bold text-slate-500 dark:text-[#c4bbae] leading-relaxed">
                  {learningPathData.next_step.explanation}
                </p>
              </div>
              <Link
                to="/learning-path"
                className="w-full text-center text-[9px] font-black text-white bg-slate-900 dark:bg-[#ff9500] py-2 rounded uppercase shadow-sm hover:-translate-y-0.5 transition-transform"
              >
                Resume Module 🚀
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* 3. Main Workspace Grid */}
      <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-6">
          {/* Resume Learning Queue */}
          <div
            id="tour-learning-queue"
            className="rounded-[24px] border border-black/5 bg-white p-6 shadow-sm dark:bg-[#1f1c18] dark:border-white/5"
          >
            <div className="flex justify-between items-center mb-5 pb-3 border-b border-slate-100 dark:border-slate-800">
              <h2 className="text-xl font-black flex items-center gap-2.5">
                <span>📚</span> Learning Queue
              </h2>
              <label className="flex items-center gap-2 cursor-pointer bg-slate-50 px-2.5 py-1 rounded-lg border border-slate-200 text-[10px] font-black uppercase tracking-wider dark:bg-[#151411] dark:border-[#2e2924]">
                <input
                  type="checkbox"
                  className="w-3.5 h-3.5 accent-primary cursor-pointer rounded"
                  checked={showOnlyBookmarked}
                  onChange={(e) => setShowOnlyBookmarked(e.target.checked)}
                />
                <span>Bookmarked</span>
              </label>
            </div>
            <div className="space-y-3">
              {activeLessonsQueue.length > 0 ? (
                activeLessonsQueue.map((lesson: Lesson) => (
                  <Link
                    key={lesson.slug}
                    to={`/lessons/${lesson.slug}`}
                    className="flex flex-col gap-1.5 p-4 rounded-xl border border-slate-100 bg-slate-50/20 hover:bg-slate-50 hover:-translate-y-0.5 transition-all cursor-pointer dark:bg-[#151411]/50 dark:border-[#2e2924] dark:hover:bg-[#1f1c18]"
                  >
                    <div className="flex justify-between items-center">
                      <h3 className="font-black text-base text-slate-850 dark:text-[#f0ebe2] truncate pr-4">
                        {lesson.title}
                      </h3>
                      <span className="font-mono text-[9px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded uppercase dark:bg-slate-800 dark:text-slate-300">
                        {lesson.difficulty || "beginner"}
                      </span>
                    </div>
                    <p className="font-bold text-xs text-slate-500 dark:text-[#c4bbae] line-clamp-2 leading-relaxed">
                      {lesson.description}
                    </p>
                    <div className="flex justify-between text-[11px] font-bold text-slate-400 mt-1">
                      <span>⏱️ {lesson.estimatedMinutes || 10} min</span>
                      <span className="flex items-center gap-1 text-[#8884d8] font-black">
                        Start Mission <ArrowRight size={11} />
                      </span>
                    </div>
                  </Link>
                ))
              ) : (
                <div className="p-8 text-center bg-slate-50/50 rounded-xl border-2 border-dashed border-slate-200 dark:bg-[#0f0e0c] dark:border-[#2e2924]">
                  <p className="font-bold text-xs text-muted dark:text-[#c4bbae]">
                    All modules completed! Go download your certificate! 🎓🌟
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Assigned Issues */}
          <div className="rounded-[24px] border border-black/5 bg-white p-6 shadow-sm dark:bg-[#1f1c18] dark:border-white/5">
            <h2 className="text-xl font-black mb-4 flex items-center gap-2.5 pb-3 border-b border-slate-100 dark:border-slate-800">
              <span>🚨</span> Assigned Issues
            </h2>
            <div className="space-y-3">
              {assigned_issues.length > 0 ? (
                assigned_issues.map(
                  (issue: { id: number; title: string; points: number }) => (
                    <div
                      key={issue.id}
                      className="p-4 bg-slate-50/30 rounded-xl border border-slate-100 dark:bg-[#151411] dark:border-[#2e2924] flex justify-between items-center gap-4"
                    >
                      <div>
                        <span className="text-[9px] font-black uppercase text-[#ff8000]">
                          XP Bounty: {issue.points}
                        </span>
                        <h4 className="font-black text-sm mt-0.5 text-slate-800 dark:text-[#f0ebe2]">{issue.title}</h4>
                      </div>
                      <Link
                        to="/challenges"
                        className="flex-shrink-0 px-3 py-1.5 bg-slate-900 text-white rounded-lg text-xs font-bold shadow-sm hover:-translate-y-0.5 transition-transform dark:bg-white dark:text-black"
                      >
                        Solve
                      </Link>
                    </div>
                  ),
                )
              ) : (
                <div className="p-8 text-center bg-slate-50/50 rounded-xl border border-slate-200 border-dashed dark:bg-[#151411]">
                  <p className="text-xs font-bold text-muted">All issues resolved! Grab a new task in Challenges board.</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Sidebar: Completion Progress & Achievements Shelf */}
        <div className="space-y-6">
          {/* Progress Circle Card */}
          <div className="rounded-[24px] border border-black/5 bg-white p-6 shadow-sm dark:bg-[#1f1c18] dark:border-white/5 flex flex-col items-center text-center justify-between min-h-[280px]">
            <h2 className="text-lg font-black flex items-center gap-2 self-start w-full pb-3 border-b border-slate-100 dark:border-slate-800">
              <span>🎯</span> Course Completion
            </h2>
            <div className="my-6 relative flex items-center justify-center">
              {/* SVG circular progress ring */}
              <svg className="w-32 h-32 transform -rotate-90">
                <circle
                  cx="64"
                  cy="64"
                  r="52"
                  stroke="currentColor"
                  strokeWidth="8"
                  fill="transparent"
                  className="text-slate-100 dark:text-slate-800"
                />
                <circle
                  cx="64"
                  cy="64"
                  r="52"
                  stroke="currentColor"
                  strokeWidth="8"
                  fill="transparent"
                  strokeDasharray={2 * Math.PI * 52}
                  strokeDashoffset={2 * Math.PI * 52 * (1 - completionPercentage / 100)}
                  strokeLinecap="round"
                  className="text-[#8884d8]"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-2xl font-black text-slate-800 dark:text-[#f0ebe2]">
                  {completionPercentage}%
                </span>
                <span className="text-[9px] uppercase font-bold text-slate-400">
                  SOLVED
                </span>
              </div>
            </div>
            {completionPercentage === 100 ? (
              <button
                onClick={() => setShowCertificate(true)}
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-green-500 text-black font-black py-2.5 border border-green-600 text-xs shadow-sm hover:-translate-y-0.5 transition-all cursor-pointer uppercase"
              >
                <Download size={13} /> Download Certificate
              </button>
            ) : (
              <div className="w-full text-xs font-black text-slate-400 bg-slate-50 py-2.5 rounded-xl border border-dashed border-slate-200 dark:bg-[#151411] dark:border-[#2e2924]">
                🔒 Certificate Locked
              </div>
            )}
          </div>

          {/* Unlocked Achievements drawer */}
          <div className="rounded-[24px] border border-black/5 bg-white p-6 shadow-sm dark:bg-[#1f1c18] dark:border-white/5">
            <h2 className="text-lg font-black mb-4 flex items-center gap-2.5 pb-3 border-b border-slate-100 dark:border-slate-800">
              <Award className="w-5 h-5 text-[#8884d8]" /> Earned Badges ({earnedBadges.length})
            </h2>
            {earnedBadges.length > 0 ? (
              <div className="grid grid-cols-2 gap-3">
                {BADGES.filter((badge) => earnedBadges.includes(badge.id)).map((badge) => (
                  <div
                    key={badge.id}
                    className="flex flex-col items-center text-center p-3 rounded-xl border border-slate-100 bg-slate-50/30 dark:bg-slate-800/40 dark:border-slate-700/50"
                  >
                    <span className="text-3xl mb-1">{badge.icon}</span>
                    <span className="text-[10px] font-black text-slate-800 dark:text-[#f0ebe2] leading-tight line-clamp-1">
                      {badge.name}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs font-bold text-muted text-center py-4">No badges earned yet. Complete lessons to unlock!</p>
            )}
          </div>
        </div>
      </section>

      <CertificateModal
        isOpen={showCertificate}
        onClose={() => setShowCertificate(false)}
        username={user?.username}
        certificateData={certificateData}
      />

      <ProgressReportModal
        isOpen={showProgressReport}
        onClose={() => setShowProgressReport(false)}
        username={user?.username}
        completionPercentage={completionPercentage}
        completedLessonsCount={completedLessonsCount}
        totalLessonsCount={totalLessonsCount}
        personalStats={personal_stats}
        earnedBadges={earnedBadges}
        modules={curriculumData}
        isLessonCompleted={isLessonCompleted}
      />

      <AchievementCardModal
        isOpen={showAchievementCard}
        onClose={() => setShowAchievementCard(false)}
        personalStats={personal_stats}
        username={user?.username || "Contributor"}
      />
    </div>
  );
}
