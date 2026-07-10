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
    <div className="max-w-7xl mx-auto px-4 pt-24 pb-12 space-y-10">
      <OnboardingTour run={showOnboarding} onFinish={handleFinishOnboarding} />
      <NotesWidget />
      {/* 1. Header Banner */}
      <section className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
        <div
          id="tour-welcome"
          className="rounded-[2.5rem] border-4 border-black bg-tertiary p-8 sm:p-10 shadow-card relative overflow-hidden dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none flex flex-col justify-between min-h-[260px]"
        >
          <div className="relative z-10">
            <span className="font-black text-sm bg-white text-black px-4 py-2 rounded-full border-2 border-black rotate-[-2deg] inline-block shadow-card-sm mb-4 dark:bg-[#151411] dark:text-[#f0ebe2] dark:border-[#2e2924]">
              LEVEL{" "}
              {completedLessonsCount === totalLessonsCount
                ? "MAX 🎓"
                : Math.floor(completedLessonsCount / 3) + 1}{" "}
              LEARNER
            </span>
            <div className="flex items-center justify-between gap-4 mb-4">
              <h1 className="text-4xl sm:text-5xl font-black text-white drop-shadow-[3.5px_3.5px_0_#000] dark:text-[#f0ebe2] dark:drop-shadow-none">
                Welcome to the Atelier, {user?.username}.
              </h1>
              <button
                onClick={() => setShowAchievementCard(true)}
                className="hidden sm:flex items-center gap-2 px-4 py-2 bg-[#ffebc2] text-black font-bold border-2 border-black rounded-xl hover:-translate-y-0.5 hover:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transition-all shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] whitespace-nowrap"
              >
                <Sparkles className="w-4 h-4 text-primary" />
                Share Card
              </button>
            </div>

            {/* --- NEW BIO RENDERER START --- */}
            {user?.bio_html && (
              <div
                className="prose prose-sm prose-invert mb-6 text-white dark:text-[#f0ebe2] max-w-2xl bg-black/20 p-4 rounded-xl border-2 border-white/20 shadow-inner"
                dangerouslySetInnerHTML={{ __html: user.bio_html }}
              />
            )}
            {/* --- NEW BIO RENDERER END --- */}

            <p className="text-lg font-bold text-black bg-white/95 p-4 rounded-lg border-4 border-black shadow-card-sm inline-block max-w-xl leading-relaxed dark:bg-[#151411] dark:border-[#2e2924] dark:text-[#f0ebe2]"></p>
            <p className="text-lg font-bold text-black bg-white/95 p-4 rounded-lg border-4 border-black shadow-card-sm inline-block max-w-xl leading-relaxed dark:bg-[#151411] dark:border-[#2e2924] dark:text-[#f0ebe2]">
              You have completed {completedLessonsCount} of {totalLessonsCount}{" "}
              course modules, earning{" "}
              <span className="text-primary font-black">
                {personal_stats.total_xp} XP
              </span>
              .
            </p>
          </div>
          <div className="absolute -right-6 -bottom-6 text-[10rem] opacity-20 rotate-12 pointer-events-none">
            🚀
          </div>
        </div>

        <StatsCards
          personalStats={personal_stats}
          completedLessonsCount={completedLessonsCount}
        />
      </section>

      {/* 2. Fact of the Day, Quote, and Certificate Unlock */}
      {/* Updated to grid-cols-3 to fit the new widget nicely */}
      <section className="grid gap-6 md:grid-cols-[1fr_1fr_0.8fr]">
        <div
          id="tour-fact"
          className="rounded-2xl border-4 border-black bg-surface-low p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none flex items-start gap-4"
        >
          <div className="bg-white p-3 rounded-2xl border-2 border-black flex-shrink-0 text-2xl dark:bg-[#151411] dark:border-[#2e2924]">
            💡
          </div>
          <div>
            <h4 className="font-mono text-xs text-primary uppercase tracking-wider font-black mb-1">
              Fact of the Day
            </h4>
            <p className="font-bold text-sm text-text leading-relaxed dark:text-[#c4bbae]">
              {factOfDay}
            </p>
          </div>
        </div>

        {/* --- NEW DAILY QUOTE WIDGET --- */}
        <DailyQuoteWidget />

        {/* Certificate Card */}
        <div
          id="tour-certificate"
          className="rounded-2xl border-4 border-black bg-white p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none flex flex-col justify-between"
        >
          <div className="flex items-center gap-2">
            <span className="text-2xl">🎓</span>
            <div>
              <h4 className="font-black text-sm text-text dark:text-[#f0ebe2]">
                Completion Certificate
              </h4>
              <p className="text-xs text-muted dark:text-[#c4bbae]">
                Unlocked at 100% curriculum score
              </p>
            </div>
          </div>
          {completionPercentage === 100 ? (
            <button
              onClick={() => setShowCertificate(true)}
              className="mt-4 w-full flex items-center justify-center gap-2 rounded-lg bg-green-500 text-black font-black py-3 border-4 border-black shadow-card-sm hover:-translate-y-0.5 transition-all cursor-pointer uppercase tracking-wider text-xs"
            >
              <Download size={14} /> Download Certificate
            </button>
          ) : (
            <div className="mt-4 text-xs font-black text-muted bg-surface-low p-3 rounded-lg border-2 border-dashed border-black/35 text-center dark:bg-[#151411] dark:border-[#2e2924]">
              🔒 Locked ({completionPercentage}% progress)
            </div>
          )}
          <button
            id="tour-progress-report"
            onClick={() => setShowProgressReport(true)}
            className="mt-2 w-full flex items-center justify-center gap-2 rounded-lg bg-white text-text font-black py-2.5 border-2 border-black shadow-card-sm hover:-translate-y-0.5 transition-all cursor-pointer uppercase tracking-wider text-[10px] dark:bg-[#151411] dark:text-[#f0ebe2] dark:border-[#2e2924]"
          >
            <Download size={12} /> Export Progress as PDF
          </button>
        </div>
      </section>

      {/* Personalized Next Step Widget */}
      {learningPathData?.next_step && (
        <section className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none space-y-6">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div className="flex items-start gap-4">
              <div className="bg-[#ffcc00] p-3 rounded-2xl border-2 border-black flex-shrink-0 text-2xl dark:bg-[#ffcc00]/20 dark:text-[#ffcc00]">
                🎯
              </div>
              <div>
                <h3 className="font-black text-2xl dark:text-[#f0ebe2] flex items-center gap-2">
                  Your Personalized Next Step
                  <span className="font-mono text-xs bg-black text-white px-2 py-0.5 rounded-full uppercase dark:bg-[#2e2924]">
                    {learningPathData.next_step.id}
                  </span>
                </h3>
                <p className="font-bold text-sm text-muted dark:text-[#c4bbae] mt-1">
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
              className="w-full md:w-auto rounded-lg bg-accent text-black border-2 border-black px-4 py-2 text-xs font-black hover:-translate-y-0.5 shadow-card-sm transition-all text-center uppercase tracking-wider"
            >
              View Full Learning Path 🗺️
            </Link>
          </div>

          <div className="grid gap-6 md:grid-cols-[1.5fr_1fr] pt-4 border-t-2 border-dashed border-black/10 dark:border-white/10">
            {/* Left side: description and progress bar */}
            <div className="space-y-4">
              <p className="text-sm font-bold text-text dark:text-[#f0ebe2]">
                {learningPathData.next_step.description}
              </p>
              <div className="space-y-2">
                <div className="flex justify-between text-xs font-black">
                  <span>Module Progress</span>
                  <span>
                    {learningPathData.next_step.completed_lessons_count} /{" "}
                    {learningPathData.next_step.lessons_count} lessons Completed
                  </span>
                </div>
                <div className="w-full h-4 bg-surface-low border-2 border-black rounded-full overflow-hidden dark:bg-[#151411] dark:border-[#2e2924]">
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

            {/* Right side: why this next panel */}
            <div className="border-4 border-black p-4 rounded-xl bg-amber-50 dark:bg-[#1c1915] dark:border-[#2e2924] flex flex-col justify-between gap-3">
              <div className="space-y-1">
                <h4 className="font-black text-xs uppercase text-amber-700 dark:text-amber-400 flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4" /> Why this next?
                </h4>
                <p className="text-xs font-bold text-black/85 dark:text-[#f0ebe2] leading-relaxed">
                  {learningPathData.next_step.explanation}
                </p>
              </div>
              <Link
                to="/learning-path"
                className="w-full text-center text-[10px] font-black text-white bg-tertiary dark:bg-[#ff9500] py-2 rounded uppercase border-2 border-black shadow-card-sm hover:-translate-y-0.5 transition-transform"
              >
                Resume Module 🚀
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* 3. Learning Queue Sidebar & Course Completion Chart */}
      <section className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
        <div
          id="tour-learning-queue"
          className="rounded-2xl border-4 border-black bg-white p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none"
        >
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
            <h2 className="text-3xl font-black flex items-center gap-3">
              <span className="bg-primary text-white w-10 h-10 rounded-full border-2 border-black flex items-center justify-center text-lg dark:bg-primary/20 dark:text-primary">
                📚
              </span>
              Resume Learning Queue
            </h2>
            <label className="flex items-center gap-2 cursor-pointer bg-surface-low px-3 py-1.5 rounded-lg border-2 border-black shadow-card-sm hover:-translate-y-0.5 transition-transform dark:bg-[#151411] dark:border-[#2e2924]">
              <input
                type="checkbox"
                className="w-4 h-4 accent-primary cursor-pointer"
                checked={showOnlyBookmarked}
                onChange={(e) => setShowOnlyBookmarked(e.target.checked)}
              />
              <span className="text-xs font-black uppercase tracking-wider text-text dark:text-[#f0ebe2]">
                Bookmarked Only
              </span>
            </label>
          </div>
          <div className="space-y-4">
            {activeLessonsQueue.length > 0 ? (
              activeLessonsQueue.map((lesson: Lesson) => (
                <Link
                  key={lesson.slug}
                  to={`/lessons/${lesson.slug}`}
                  className="flex flex-col gap-2 p-5 rounded-lg border-4 border-black bg-surface-lowest shadow-card-sm hover:shadow-card hover:-translate-y-1 transition-all cursor-pointer dark:bg-[#151411] dark:border-[#2e2924] dark:hover:bg-[#1f1c18]"
                >
                  <div className="flex justify-between items-end">
                    <h3 className="font-black text-xl dark:text-[#f0ebe2]">
                      {lesson.title}
                    </h3>
                    <span className="font-black text-[9px] bg-black text-white px-2 py-0.5 rounded-full uppercase dark:bg-[#2e2924]">
                      {lesson.difficulty || "beginner"}
                    </span>
                  </div>
                  <p className="font-bold text-sm text-muted dark:text-[#c4bbae]">
                    {lesson.description}
                  </p>
                  <div className="flex justify-between text-xs font-bold text-primary mt-1">
                    <span>⏱️ {lesson.estimatedMinutes || 10} min module</span>
                    <span className="flex items-center gap-1">
                      Start mission <ArrowRight size={12} />
                    </span>
                  </div>
                </Link>
              ))
            ) : (
              <div className="p-8 text-center bg-surface-low rounded-2xl border-4 border-dashed border-black dark:bg-[#0f0e0c] dark:border-[#2e2924]">
                <p className="font-bold text-muted dark:text-[#c4bbae]">
                  All curriculum modules completed! Go fetch your graduation
                  certificate! 🎓🌟
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Circular Progress Gauge */}
        <div className="rounded-2xl border-4 border-black bg-white p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none flex flex-col justify-between">
          <div>
            <h2 className="text-2xl font-black mb-4 flex items-center gap-2">
              <span>🎯</span> Completion Progress
            </h2>
            <div className="h-[180px] sm:h-[220px] w-full flex items-center justify-center relative">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={[
                      { name: "Completed", value: completedLessonsCount },
                      {
                        name: "Remaining",
                        value: Math.max(
                          0,
                          totalLessonsCount - completedLessonsCount,
                        ),
                      },
                    ]}
                    cx="50%"
                    cy="50%"
                    innerRadius="45%"
                    outerRadius="70%"
                    paddingAngle={3}
                    dataKey="value"
                  >
                    <Cell
                      fill={theme === "dark" ? "#ff665c" : "#ff3b30"}
                      stroke={theme === "dark" ? "#1f1c18" : "#000"}
                      strokeWidth={2}
                    />
                    <Cell
                      fill={theme === "dark" ? "#3d2b14" : "#FFEBC2"}
                      stroke={theme === "dark" ? "#1f1c18" : "#000"}
                      strokeWidth={2}
                    />
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-4xl font-black text-text dark:text-[#f0ebe2]">
                  {completionPercentage}%
                </span>
                <span className="text-[10px] uppercase font-bold text-muted dark:text-[#c4bbae]">
                  SOLVED
                </span>
              </div>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-dashed border-muted/20 text-center font-bold text-sm text-muted dark:text-[#c4bbae]">
            📊 Completed {completedLessonsCount} of {totalLessonsCount} total
            learning modules
          </div>
        </div>
      </section>

      {/* Lessons Completed per Day Line Chart */}
      {lessonStats && lessonStats.length > 0 && (
        <section className="rounded-[2.5rem] border-4 border-black bg-white p-6 sm:p-8 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none mt-6">
          <LessonsChart data={lessonStats} />
        </section>
      )}

      {/* Recommended Content */}
      <section className="rounded-[2.5rem] border-4 border-black bg-white p-6 sm:p-8 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none mt-6">
        <h2 className="text-3xl font-black mb-6 flex items-center gap-3">
          <span className="bg-accent text-white w-10 h-10 rounded-full border-2 border-black flex items-center justify-center text-lg">
            ✨
          </span>
          Recommended For You
        </h2>
        <RecommendationsList />
      </section>

      {/* Read Later / Bookmarks */}
      {bookmarks.length > 0 && (
        <section className="rounded-[2.5rem] border-4 border-black bg-surface-low p-6 sm:p-8 shadow-card dark:bg-[#151411] dark:border-[#2e2924] dark:shadow-none mt-6">
          <h2 className="text-3xl font-black mb-6 flex items-center gap-3">
            <span className="bg-[#c3c0ff] text-black w-10 h-10 rounded-full border-2 border-black flex items-center justify-center text-lg">
              <Bookmark className="fill-black" size={20} />
            </span>
            Read Later
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {bookmarks.map((bookmark) => (
              <Link
                key={bookmark.lesson_slug}
                to={`/lessons/${bookmark.lesson_slug}`}
                className="flex flex-col gap-2 p-5 rounded-lg border-4 border-black bg-white shadow-card-sm hover:shadow-card hover:-translate-y-1 transition-all cursor-pointer dark:bg-[#1f1c18] dark:border-[#2e2924]"
              >
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-black text-lg leading-tight dark:text-[#f0ebe2] pr-4">
                    {bookmark.lesson_title}
                  </h3>
                  <button
                    type="button"
                    aria-label="Remove bookmark"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      toggleBookmark.mutate({
                        slug: bookmark.lesson_slug,
                        isBookmarked: true,
                      });
                    }}
                    className="shrink-0"
                  >
                    <Bookmark
                      className="fill-primary text-primary hover:opacity-60 transition-opacity"
                      size={20}
                    />
                  </button>
                </div>
                <div className="flex justify-between items-center mt-auto pt-4">
                  <span className="font-black text-[10px] bg-black text-white px-2 py-0.5 rounded-full uppercase dark:bg-[#2e2924]">
                    {bookmark.lesson_category}
                  </span>
                  <span className="text-xs font-bold text-muted dark:text-[#c4bbae]">
                    {bookmark.lesson_estimated_minutes} min
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* 4. Badges / Achievements Shelf */}
      <section className="mt-6 rounded-[2.5rem] border-4 border-black bg-white p-6 sm:p-8 shadow-card dark:bg-[#151411] dark:border-[#2e2924] dark:shadow-none">
        <h2 className="text-3xl font-black mb-6 flex items-center gap-3">
          <Award className="w-8 h-8 text-primary" />
          Achievements & Badges Drawer
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {BADGES.map((badge) => {
            const isEarned = earnedBadges.includes(badge.id);
            return (
              <div
                key={badge.id}
                className={`relative rounded-2xl border-4 border-black p-5 flex flex-col items-center text-center shadow-card-sm transition-all ${
                  isEarned
                    ? "bg-white dark:bg-[#1f1c18] hover:-translate-y-1"
                    : "bg-surface-low/30 opacity-60 dark:bg-black/20"
                }`}
              >
                <div className={`text-5xl mb-3 ${isEarned ? "" : "grayscale"}`}>
                  {badge.icon}
                </div>
                <h4 className="font-black text-sm mb-1 text-text dark:text-[#f0ebe2]">
                  {badge.name}
                </h4>
                <p className="text-[10px] font-bold text-muted dark:text-[#c4bbae]">
                  {badge.desc}
                </p>
                {isEarned ? (
                  <span className="absolute top-2 right-2 bg-green-100 text-green-700 border-2 border-green-700 text-[8px] font-black px-1.5 py-0.5 rounded-full dark:border-none">
                    UNLOCKED
                  </span>
                ) : (
                  <span className="absolute top-2 right-2 bg-gray-100 text-gray-400 border-2 border-gray-400 text-[8px] font-black px-1.5 py-0.5 rounded-full dark:border-none flex items-center gap-1">
                    <Lock size={10} />
                    LOCKED
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* 5. Contributor Recognition & Assigned Issues */}
      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        {/* Contributor recognition */}
        <div className="rounded-2xl border-4 border-black bg-white p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none">
          <h2 className="text-2xl font-black mb-4 flex items-center gap-2">
            <Users className="w-6 h-6 text-primary" />
            GitHub Contributor Hall of Fame
          </h2>
          <p className="text-xs text-muted mb-6 dark:text-[#c4bbae]">
            Say hello to developers who built this learning ecosystem! Open
            source relies on collaboration.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {gitHubContributors.map((contrib, i) => (
              <a
                key={contrib.login || i}
                href={contrib.html_url}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 p-3 rounded-lg border-2 border-black bg-surface hover:-translate-y-0.5 shadow-card-sm transition-all dark:bg-[#151411] dark:border-[#2e2924]"
              >
                <img
                  src={contrib.avatar_url}
                  alt={contrib.login}
                  className="w-8 h-8 rounded-full border border-black flex-shrink-0"
                />
                <span className="font-black text-xs truncate">
                  @{contrib.login}
                </span>
              </a>
            ))}
          </div>
        </div>

        {/* Local Assigned Issues */}
        <div className="rounded-2xl border-4 border-black bg-[#ffb5e8] p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none flex flex-col justify-between">
          <div>
            <h2 className="text-2xl font-black mb-3 flex items-center gap-2">
              <span>🚨</span> Assigned Issues
            </h2>
            <div className="space-y-3">
              {assigned_issues.length > 0 ? (
                assigned_issues.map(
                  (issue: { id: number; title: string; points: number }) => (
                    <div
                      key={issue.id}
                      className="p-3 bg-white rounded-lg border-2 border-black dark:bg-[#151411] dark:border-[#2e2924]"
                    >
                      <span className="text-[9px] font-black uppercase text-primary">
                        XP Bounty: {issue.points}
                      </span>
                      <h4 className="font-black text-sm mt-1">{issue.title}</h4>
                    </div>
                  ),
                )
              ) : (
                <div className="p-6 text-center bg-white rounded-lg border-2 border-dashed border-black/35 text-xs font-bold text-muted dark:bg-[#151411]">
                  All issues resolved! Go grab a task in the Challenges board.
                </div>
              )}
            </div>
          </div>
          <Link
            to="/challenges"
            className="mt-4 block text-center rounded-lg bg-white border-4 border-black py-2.5 font-black text-xs shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm cursor-pointer dark:bg-[#151411] dark:border-[#2e2924]"
          >
            Browse Issues Board
          </Link>
        </div>
      </section>

      {/* --- MODAL 1: ONBOARDING GUIDED TOUR --- */}
      {showOnboarding && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white rounded-2xl border-4 border-black shadow-card p-6 sm:p-8 space-y-6 relative dark:bg-[#0f0e0c] dark:border-[#2e2924]">
            {onboardingStep === 0 && (
              <div className="space-y-4">
                <div className="text-5xl text-center">👋 Welcome!</div>
                <h3 className="text-2xl font-black text-center">
                  Assemble at the Atelier
                </h3>
                <p className="font-bold text-sm leading-relaxed text-muted dark:text-[#c4bbae] text-center">
                  This platform will take you from code novice to a confident
                  open source contributor. You will write code, solve terminal
                  drills, clear checks, and earn real-world credentials!
                </p>
              </div>
            )}
            {onboardingStep === 1 && (
              <div className="space-y-4">
                <div className="text-5xl text-center">🎮 Play & Earn</div>
                <h3 className="text-2xl font-black text-center">
                  Leveling & Gamification
                </h3>
                <p className="font-bold text-sm leading-relaxed text-muted dark:text-[#c4bbae] text-center">
                  Complete each of our 8 structured course modules to unlock
                  unique badges on your developer dashboard, stack XP points,
                  and unlock your printable graduation certificate.
                </p>
              </div>
            )}
            {onboardingStep === 2 && (
              <div className="space-y-4">
                <div className="text-5xl text-center">
                  🌿 Start Contributing
                </div>
                <h3 className="text-2xl font-black text-center">
                  Ready to Dive In?
                </h3>
                <p className="font-bold text-sm leading-relaxed text-muted dark:text-[#c4bbae] text-center">
                  Begin your adventure now with Module 1: "What is Open Source"
                  to understand basic etiquette and how projects grow through
                  collaboration.
                </p>
              </div>
            )}

            <div className="flex items-center justify-between pt-4 border-t-2 border-dashed border-black/15">
              <span className="font-mono text-xs text-muted">
                Step {onboardingStep + 1} of 3
              </span>
              <div className="flex gap-2">
                {onboardingStep > 0 && (
                  <button
                    onClick={() => setOnboardingStep((prev) => prev - 1)}
                    className="px-4 py-2 border-2 border-black rounded-lg text-xs font-black hover:bg-surface-low"
                  >
                    Back
                  </button>
                )}
                {onboardingStep < 2 ? (
                  <button
                    onClick={() => setOnboardingStep((prev) => prev + 1)}
                    className="px-4 py-2 bg-accent text-black border-2 border-black rounded-lg text-xs font-black shadow-card-sm hover:-translate-y-0.5"
                  >
                    Continue
                  </button>
                ) : (
                  <button
                    onClick={handleFinishOnboarding}
                    className="px-4 py-2 bg-green-500 text-black border-2 border-black rounded-lg text-xs font-black shadow-card-sm hover:-translate-y-0.5"
                  >
                    Let's Go!
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

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
