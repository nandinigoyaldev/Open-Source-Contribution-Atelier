/* eslint-disable @typescript-eslint/no-unused-vars */
import React, { useMemo, useState, useEffect } from "react";
import { useAuth } from "../features/auth/AuthContext";
import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";
import { Link } from "react-router-dom";
import SkeletonCard from "../components/ui/skeletons/SkeletonCard";
import { useRef } from "react";
import { useElementSize } from "../hooks/useElementSize";
import { fetchLessonsApi, Lesson } from "../lib/lessons";
import { useUserProgress } from "../hooks/useUserProgress";
import { BADGES } from "../constants/badges";
import {
  Award,
  Flame,
  CheckCircle2,
  Users,
  Trophy,
  ArrowRight,
  Download,
  Printer,
  Code,
  X,
  Lock,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { OnboardingTour } from "../components/ui/OnboardingTour";

const FACTS = [
  "Git was created in 2005 by Linus Torvalds because he was frustrated with the commercial tool they were using for Linux development.",
  "Modern servers run on Linux, browsers run on Chromium, and compilers run on open source languages: the internet is built on OSS.",
  "The term 'Open Source' was officially adopted in 1998 in Palo Alto, California, to make software sharing more business-friendly.",
  "Richard Stallman launched the GNU Project in 1983, publishing the GNU Manifesto to advocate for computer user freedoms.",
  "Spamming duplicate or low-effort pull requests (like formatting comments) wastes maintainers' time and can get you blocked.",
  "The Apache HTTP Server project was founded in 1995 and played a key role in the early expansion of the World Wide Web.",
];

const CONTRIBUTORS_CACHE_KEY = "github_contributors_cache";
const CACHE_EXPIRY = 24 * 60 * 60 * 1000; // 24 hours

interface ModuleData {
  id: string;
  title: string;
  lessons: { slug: string }[];
}

interface GitHubContributor {
  login: string;
  avatar_url: string;
  html_url: string;
}

interface PendingPR {
  id: number;
  created_at: string;
  title: string;
  contributor: string;
  issue_title: string;
}

interface AssignedIssue {
  id: number;
  points: number;
  title: string;
}

export function DashboardPage() {
  const taskDistRef = useRef<HTMLElement>(null);
  const { width: taskDistWidth } = useElementSize(taskDistRef);
  const completionRef = useRef<HTMLElement>(null);
  const { width: completionWidth } = useElementSize(completionRef);

  const { user } = useAuth();
  const { isLessonCompleted } = useUserProgress();
  const [showScrollTop, setShowScrollTop] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setShowScrollTop(window.scrollY > 300);
    };

    window.addEventListener("scroll", handleScroll);

    return () => {
      window.removeEventListener("scroll", handleScroll);
    };
  }, []);
  // 1. Fetch static modules catalog
  const [curriculumData, setCurriculumData] = useState<ModuleData[]>([]);
  useEffect(() => {
    fetch("/content/curriculum.json")
      .then((res) => res.json())
      .then((data) => {
        if (data && data.modules) {
          setCurriculumData(data.modules);
        }
      })
      .catch((err) =>
        console.error("Error loading dashboard curriculum:", err),
      );
  }, []);

  // 2. Fetch Admin Dashboard stats (only queries if user is staff)
  const {
    data: adminData,
    isLoading: isAdminLoading,
    error: adminError,
  } = useQuery({
    queryKey: ["adminDashboardStats"],
    queryFn: () => fetchApi("/dashboard/admin/"),
    enabled: !!user?.is_staff,
  });

  // 3. Fetch paginated leaderboard for admin chart (only queries if user is staff)
  const { data: leaderboardData, isLoading: isLeaderboardLoading } = useQuery({
    queryKey: ["leaderboard", 1],
    queryFn: () => fetchApi("/leaderboard/"),
    enabled: !!user?.is_staff,
  });

  // 4. Fetch Contributor Dashboard stats (only queries if user is NOT staff)
  const {
    data: contributorData,
    isLoading: isContributorLoading,
    error: contributorError,
  } = useQuery({
    queryKey: ["contributorDashboardStats"],
    queryFn: () => fetchApi("/dashboard/contributor/"),
    enabled: !!user && !user.is_staff,
  });

  // 5. Fetch standard list of lessons via cache
  const { data: lessons = [], isLoading: isLessonsLoading } = useQuery<
    Lesson[]
  >({
    queryKey: ["lessons"],
    queryFn: fetchLessonsApi,
    enabled: !user?.is_staff,
  });

  // Random Fact of the Day
  const factOfDay = useMemo(() => {
    const day = new Date().getDate();
    return FACTS[day % FACTS.length];
  }, []);

  // GitHub Live Contributors list
  const [gitHubContributors, setGitHubContributors] = useState<
    { login: string; avatar_url: string; html_url: string }[]
  >([]);
  useEffect(() => {
    const fallbackContributors = [
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
      .then((res) => {
        if (!res.ok) throw new Error("API Limit");
        return res.json();
      })
      .then((data) => {
        if (Array.isArray(data)) {
          const contributors = data.slice(0, 8);

          setGitHubContributors(contributors);

          localStorage.setItem(
            CONTRIBUTORS_CACHE_KEY,
            JSON.stringify({
              data: contributors,
              timestamp: Date.now(),
            }),
          );
        }
      })
      .catch(() => {
        const cachedData = localStorage.getItem(CONTRIBUTORS_CACHE_KEY);

        if (cachedData) {
          try {
            const parsedCache = JSON.parse(cachedData);

            const isCacheValid =
              Date.now() - parsedCache.timestamp < CACHE_EXPIRY;

            if (isCacheValid) {
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

  // Onboarding Tour state
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [onboardingStep, setOnboardingStep] = useState(0);

  useEffect(() => {
    if (user && !user.is_staff) {
      const isBoarded = localStorage.getItem("atelier_onboarded");
      if (!isBoarded) {
        setShowOnboarding(true);
      }
    }
  }, [user]);

  const handleFinishOnboarding = () => {
    localStorage.setItem("atelier_onboarded", "true");
    setShowOnboarding(false);
  };

  // Certificate Modal state
  const [showCertificate, setShowCertificate] = useState(false);

  // Compute local progress metrics based on frontend curriculum data
  const {
    completedLessonsCount,
    totalLessonsCount,
    completionPercentage,
    activeLessonsQueue,
    earnedBadges,
  } = useMemo(() => {
    if (user?.is_staff || !lessons.length || !curriculumData.length) {
      return {
        completedLessonsCount: 0,
        totalLessonsCount: 0,
        completionPercentage: 0,
        activeLessonsQueue: [],
        earnedBadges: [],
      };
    }

    const total = lessons.length;
    const completed = lessons.filter((l) => isLessonCompleted(l.slug)).length;
    const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;

    // Build the lessons queue (uncompleted ones first, up to 3)
    const queue = lessons.filter((l) => !isLessonCompleted(l.slug)).slice(0, 3);

    // Calculate which badges are earned
    const earned: string[] = [];
    curriculumData.forEach((mod, index) => {
      const allCompleted = mod.lessons.every((les: { slug: string }) =>
        isLessonCompleted(les.slug),
      );
      if (allCompleted) {
        earned.push(`mod-${index + 1}`);
      }
    });

    if (percentage === 100) {
      earned.push("grad");
    }

    return {
      completedLessonsCount: completed,
      totalLessonsCount: total,
      completionPercentage: percentage,
      activeLessonsQueue: queue,
      earnedBadges: earned,
    };
  }, [lessons, curriculumData, isLessonCompleted, user]);

  // Fetch user certificate if course is completed
  const { data: certificateData } = useQuery({
    queryKey: ["userCertificate"],
    queryFn: () => fetchApi("/progress/certificate/"),
    enabled: !!user && !user.is_staff && completionPercentage === 100,
    retry: false,
  });

  if (isAdminLoading || isContributorLoading || isLessonsLoading) {
    return (
      <div
        className="grid gap-6 xl:grid-cols-[1fr_0.8fr] pt-24 max-w-7xl mx-auto px-4"
        aria-busy="true"
      >
        <div className="space-y-6">
          <SkeletonCard />
          <SkeletonCard />
        </div>
        <div className="space-y-6">
          <SkeletonCard />
        </div>
      </div>
    );
  }

  // Admin Dashboard Render
  if (user?.is_staff) {
    if (adminError || !adminData) {
      return (
        <div className="pt-24 max-w-7xl mx-auto px-4">
          <div className="p-8 text-center bg-red-100 rounded-2xl border-4 border-black font-bold">
            Failed to load Maintainer Dashboard. Please run the backend seed
            script.
          </div>
        </div>
      );
    }

    const { system_stats, pending_prs } = adminData;
    const leaderboardResults = leaderboardData?.results || [];
    const issueStatusData = [
      { name: "Open", value: system_stats.open_issues },
      { name: "In Progress", value: system_stats.in_progress_issues },
      { name: "Solved", value: system_stats.solved_issues },
    ];
    const COLORS = ["#ffcc00", "#ff9500", "#ff3b30"];

    return (
      <div className="max-w-7xl mx-auto px-4 pt-24 pb-12 space-y-10">
        {/* Admin Header */}
        <section className="rounded-[2rem] border-4 border-black bg-primary p-8 sm:p-10 shadow-card relative overflow-hidden dark:border-[#2e2924] dark:shadow-none">
          <div className="relative z-10">
            <span className="font-black text-sm bg-white text-black px-4 py-2 rounded-full border-2 border-black rotate-[-2deg] inline-block shadow-card-sm mb-4 dark:bg-[#151411] dark:text-[#f0ebe2] dark:border-[#2e2924]">
              MAINTAINER CONTROL PANEL 🛠️
            </span>
            <h1 className="text-4xl sm:text-5xl font-black text-white drop-shadow-[3px_3px_0_#000] mb-4 dark:drop-shadow-none">
              Project Health & Cohort Monitor
            </h1>
            <p className="text-lg font-bold text-black bg-white/95 p-4 rounded-lg border-4 border-black shadow-card-sm inline-block max-w-lg leading-relaxed dark:bg-[#151411] dark:border-[#2e2924] dark:text-[#f0ebe2]">
              Track triage tasks, review practice codebases, and approve pending
              pull requests.
            </p>
          </div>
          <div className="absolute -right-10 -bottom-10 text-[10rem] opacity-25 rotate-12 pointer-events-none">
            📈
          </div>
        </section>

        {/* Stats Blocks */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card flex flex-col justify-between dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none">
            <div className="flex items-center gap-3">
              <span className="text-4xl">🚨</span>
              <div>
                <h3 className=" text-xs uppercase tracking-widest text-muted dark:text-[#c4bbae]">
                  System Issues
                </h3>
                <p className="text-4xl font-black text-primary drop-shadow-[2px_2px_0_#000] dark:drop-shadow-none">
                  {system_stats.total_issues}
                </p>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-dashed border-muted/20 text-xs font-bold text-muted flex justify-between dark:text-[#c4bbae]">
              <span>Solved: {system_stats.solved_issues}</span>
              <span>Open: {system_stats.open_issues}</span>
            </div>
          </div>

          <div className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card flex flex-col justify-between dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none">
            <div className="flex items-center gap-3">
              <span className="text-4xl">💻</span>
              <div>
                <h3 className=" text-xs uppercase tracking-widest text-muted dark:text-[#c4bbae]">
                  Pull Requests
                </h3>
                <p className="text-4xl font-black text-tertiary drop-shadow-[2px_2px_0_#000] dark:drop-shadow-none">
                  {system_stats.total_prs}
                </p>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-dashed border-muted/20 text-xs font-bold text-muted flex justify-between dark:text-[#c4bbae]">
              <span>Merged: {system_stats.merged_prs}</span>
              <span>Pending: {system_stats.pending_prs}</span>
            </div>
          </div>

          <div className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card flex flex-col justify-between dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none">
            <div className="flex items-center gap-3">
              <span className="text-4xl">👥</span>
              <div>
                <h3 className=" text-xs uppercase tracking-widest text-muted dark:text-[#c4bbae]">
                  Active Contributors
                </h3>
                <p className="text-4xl font-black text-accent drop-shadow-[2px_2px_0_#000] dark:drop-shadow-none">
                  {system_stats.active_contributors}
                </p>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-dashed border-muted/20 text-xs font-bold text-muted dark:text-[#c4bbae]">
              Managing guided sandbox profiles
            </div>
          </div>
        </section>

        {/* Charts & Analytics */}
        <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-2xl border-4 border-black bg-white p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none">
            <h2 className="text-2xl font-black mb-6 flex items-center gap-2">
              <span>📊</span> Active Contributor Activity
            </h2>
            <div className="h-[300px] w-full">
              {isLeaderboardLoading ? (
                <div className="h-full flex items-center justify-center border-4 border-dashed border-black rounded-2xl p-8 dark:border-[#2e2924]">
                  <p className="font-bold text-muted dark:text-[#c4bbae]">
                    Loading contributors...
                  </p>
                </div>
              ) : leaderboardResults.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={leaderboardResults}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                    <XAxis
                      dataKey="username"
                      tick={{ fontStyle: "bold", fill: "#6b5a49" }}
                    />
                    <YAxis tick={{ fontStyle: "bold", fill: "#6b5a49" }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#ffffff",
                        border: "4px solid #000000",
                        borderRadius: "12px",
                        fontWeight: "bold",
                      }}
                    />
                    <Legend wrapperStyle={{ fontWeight: "bold" }} />
                    <Bar
                      dataKey="xp"
                      name="XP Points"
                      fill="#ff9500"
                      stroke="#000000"
                      strokeWidth={2}
                    />
                    <Bar
                      dataKey="prs_merged"
                      name="Merged PRs"
                      fill="#ff3b30"
                      stroke="#000000"
                      strokeWidth={2}
                    />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center border-4 border-dashed border-black rounded-2xl p-8 dark:border-[#2e2924]">
                  <p className="font-bold text-muted dark:text-[#c4bbae]">
                    No contributor logs registered.
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="rounded-2xl border-4 border-black bg-white p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none flex flex-col justify-between">
            <div>
              <h2 className="text-2xl font-black mb-6 flex items-center gap-2">
                <span>🎯</span> Task Distribution
              </h2>
              <div className="h-[180px] sm:h-[220px] w-full flex justify-center items-center">
                {system_stats.total_issues > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={issueStatusData}
                        cx="50%"
                        cy="50%"
                        innerRadius="45%"
                        outerRadius="70%"
                        paddingAngle={5}
                        dataKey="value"
                      >
                        {issueStatusData.map((_, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={COLORS[index % COLORS.length]}
                            stroke="#000"
                            strokeWidth={2}
                          />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#ffffff",
                          border: "4px solid #000000",
                          borderRadius: "12px",
                          fontWeight: "bold",
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="font-bold text-muted dark:text-[#c4bbae]">
                    No records.
                  </p>
                )}
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2 mt-4 text-center">
              {issueStatusData.map((item, index) => (
                <div
                  key={item.name}
                  className="p-2 rounded-lg border-2 border-black"
                  style={{ backgroundColor: `${COLORS[index]}15` }}
                >
                  <span
                    className="block font-black text-xs"
                    style={{ color: COLORS[index] }}
                  >
                    ● {item.name}
                  </span>
                  <span className="font-black text-lg text-text dark:text-[#f0ebe2]">
                    {item.value}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* PR Queue */}
        <section className="rounded-2xl border-4 border-black bg-accent p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none">
          <h2 className="text-3xl font-black mb-6 flex items-center gap-2 text-black dark:text-[#f0ebe2]">
            <span>📬</span> Pending Pull Requests ({pending_prs.length})
          </h2>
          <div className="space-y-4">
            {pending_prs.length > 0 ? (
              pending_prs.map(
                (pr: {
                  id: number;
                  title: string;
                  contributor: string;
                  issue_title: string;
                  created_at: string;
                }) => (
                  <div
                    key={pr.id}
                    className="rounded-2xl border-4 border-black bg-white p-5 shadow-card-sm dark:bg-[#151411] dark:border-[#2e2924] flex flex-col md:flex-row justify-between items-start md:items-center gap-4"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-black text-[9px] bg-black text-white px-2 py-0.5 rounded-full">
                          PENDING REVIEW
                        </span>
                        <span className="text-xs font-bold text-muted dark:text-[#c4bbae]">
                          Opened: {new Date(pr.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      <h3 className="font-black text-xl mt-2 dark:text-[#f0ebe2]">
                        {pr.title}
                      </h3>
                      <p className="text-sm font-bold text-muted mt-1 dark:text-[#c4bbae]">
                        Submitted by:{" "}
                        <span className="text-primary">@{pr.contributor}</span>{" "}
                        · Issue: {pr.issue_title}
                      </p>
                    </div>
                    <div className="flex gap-2 w-full md:w-auto">
                      <button className="grow md:grow-0 rounded-lg bg-surface-low border-2 border-black px-4 py-2 text-xs font-black hover:-translate-y-0.5 shadow-card-sm transition-all dark:bg-[#0f0e0c] dark:text-[#f0ebe2]">
                        Comment
                      </button>
                      <button className="grow md:grow-0 rounded-lg bg-[#c3c0ff] border-2 border-black px-4 py-2 text-xs font-black hover:-translate-y-0.5 shadow-card-sm transition-all">
                        Approve & Merge
                      </button>
                    </div>
                  </div>
                ),
              )
            ) : (
              <div className="p-8 text-center bg-white rounded-2xl border-4 border-dashed border-black dark:bg-[#151411] dark:border-[#2e2924]">
                <p className="font-bold text-muted dark:text-[#c4bbae]">
                  No pending reviews. Working tree clean! 🌟
                </p>
              </div>
            )}
          </div>
        </section>
      </div>
    );
  }

  // Contributor/Student Dashboard Render
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
            <h1 className="text-4xl sm:text-5xl font-black text-white drop-shadow-[3.5px_3.5px_0_#000] mb-4 dark:text-[#f0ebe2] dark:drop-shadow-none">
              Welcome to the Atelier, {user?.username}.
            </h1>
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

        {/* Action / Streaks Box */}
        <div id="tour-stats" className="grid grid-cols-2 gap-4">
          <div className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card flex flex-col justify-center items-center text-center dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none hover:-translate-y-0.5 transition-transform">
            <Flame className="w-12 h-12 text-primary animate-pulse mb-2" />
            <span className="text-4xl font-black text-primary drop-shadow-[2px_2px_0_#000] dark:drop-shadow-none">
              {personal_stats.streak_days}
            </span>
            <span className="font-black text-black uppercase tracking-widest text-[9px] mt-1 dark:text-[#c4bbae]">
              Streak Days
            </span>
          </div>

          <div className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card flex flex-col justify-center items-center text-center dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none hover:-translate-y-0.5 transition-transform">
            <Trophy className="w-12 h-12 text-accent mb-2 animate-bounce" />
            <span className="text-4xl font-black text-accent drop-shadow-[2px_2px_0_#000] dark:drop-shadow-none">
              #{personal_stats.rank}
            </span>
            <span className="font-black text-black uppercase tracking-widest text-[9px] mt-1 dark:text-[#c4bbae]">
              Atelier Rank
            </span>
          </div>

          <div className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card flex flex-col justify-center items-center text-center dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none hover:-translate-y-0.5 transition-transform">
            <Code className="w-12 h-12 text-[#c3c0ff] mb-2" />
            <span className="text-4xl font-black text-text dark:text-[#f0ebe2]">
              {completedLessonsCount}
            </span>
            <span className="font-black text-black uppercase tracking-widest text-[9px] mt-1 dark:text-[#c4bbae]">
              Lessons Solved
            </span>
          </div>

          <div className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card flex flex-col justify-center items-center text-center dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none hover:-translate-y-0.5 transition-transform">
            <CheckCircle2 className="w-12 h-12 text-green-500 mb-2" />
            <span className="text-4xl font-black text-green-600">
              {personal_stats.prs_merged}
            </span>
            <span className="font-black text-black uppercase tracking-widest text-[9px] mt-1 dark:text-[#c4bbae]">
              PRs Merged
            </span>
          </div>
        </div>
      </section>

      {/* 2. Fact of the Day and Certificate Unlock */}
      <section className="grid gap-6 md:grid-cols-[1.3fr_0.7fr]">
        <div
          id="tour-fact"
          className="rounded-2xl border-4 border-black bg-surface-low p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none flex items-start gap-4"
        >
          <div className="bg-white p-3 rounded-2xl border-2 border-black flex-shrink-0 text-2xl dark:bg-[#151411] dark:border-[#2e2924]">
            💡
          </div>
          <div>
            <h4 className="font-mono text-xs text-primary uppercase tracking-wider font-black mb-1">
              Open Source Fact of the Day
            </h4>
            <p className="font-bold text-sm text-text leading-relaxed dark:text-[#c4bbae]">
              {factOfDay}
            </p>
          </div>
        </div>

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
        </div>
      </section>

      {/* 3. Learning Queue Sidebar & Course Completion Chart */}
      <section className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
        <div
          id="tour-learning-queue"
          className="rounded-2xl border-4 border-black bg-white p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none"
        >
          <h2 className="text-3xl font-black mb-6 flex items-center gap-3">
            <span className="bg-primary text-white w-10 h-10 rounded-full border-2 border-black flex items-center justify-center text-lg dark:bg-primary/20 dark:text-primary">
              📚
            </span>
            Resume Learning Queue
          </h2>
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
                    <Cell fill="#ff3b30" stroke="#000" strokeWidth={2} />
                    <Cell fill="#fdfbf7" stroke="#e0e0e0" strokeWidth={2} />
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

      {/* 4. Badges / Achievements Shelf */}
      <section className="rounded-[2.5rem] border-4 border-black bg-white p-6 sm:p-8 shadow-card dark:bg-[#151411] dark:border-[#2e2924] dark:shadow-none">
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

      {/* --- MODAL 2: CERTIFICATE OF COMPLETION (A4 Print Layout) --- */}
      {showCertificate && (
        <div className="fixed inset-0 bg-black/75 z-50 flex items-center justify-center p-4 overflow-y-auto">
          {/* Certificate Container */}
          <div className="w-full max-w-4xl bg-[#FFF9F0] rounded-[2rem] border-8 border-black p-8 sm:p-12 relative flex flex-col justify-between items-center text-center shadow-card bg-dot-grid print:border-none print:shadow-none print:p-0">
            {/* Close Button (Hidden on Print) */}
            <button
              onClick={() => setShowCertificate(false)}
              className="absolute top-4 right-4 bg-white border-2 border-black p-2 rounded-full hover:bg-surface-low transition-colors print:hidden"
            >
              <X size={16} />
            </button>

            {/* Certificate Contents */}
            <div className="space-y-6 w-full border-4 border-dashed border-black/35 rounded-2xl p-6 sm:p-10 relative">
              <div className="text-6xl mb-2">🎓</div>
              <h2 className=" text-4xl sm:text-5xl font-black uppercase tracking-tight text-text">
                Certificate of Completion
              </h2>
              <p className="font-mono text-xs text-primary uppercase tracking-widest font-black">
                The Open Source Contribution Atelier
              </p>

              <div className="py-4">
                <p className="text-sm italic text-muted">
                  This is officially awarded to
                </p>
                <h3 className="text-3xl sm:text-4xl font-black text-text underline decoration-accent decoration-wavy mt-2">
                  {user?.username}
                </h3>
              </div>

              <p className="max-w-xl mx-auto text-sm font-bold leading-relaxed text-text">
                for successfully resolving issues, demonstrating version control
                proficiency, respecting open source etiquette, and completing
                the full 8-module collaborative contribution track.
              </p>

              <div className="grid grid-cols-2 gap-4 max-w-md mx-auto pt-6 text-left border-t border-black/10">
                <div>
                  <span className="block text-[10px] text-muted uppercase font-bold">
                    Verification Hash
                  </span>
                  <span
                    className="font-mono text-xs font-black truncate block"
                    title={
                      certificateData?.certificate?.verification_hash ||
                      "GENERATING..."
                    }
                  >
                    {certificateData?.certificate?.verification_hash ||
                      "GENERATING..."}
                  </span>
                </div>
                <div>
                  <span className="block text-[10px] text-muted uppercase font-bold">
                    Issue Date
                  </span>
                  <span className="font-mono text-xs font-black block">
                    {certificateData?.certificate?.issued_at
                      ? new Date(
                          certificateData.certificate.issued_at,
                        ).toLocaleDateString()
                      : new Date().toLocaleDateString()}
                  </span>
                </div>
              </div>

              {certificateData?.certificate?.verification_hash && (
                <div className="mt-4 text-[10px] text-muted font-bold text-center print:block">
                  Verify authenticity at:{" "}
                  <span className="text-primary underline select-all">
                    {window.location.origin}/verify/
                    {certificateData.certificate.verification_hash}
                  </span>
                </div>
              )}
            </div>

            {/* Print trigger button row */}
            <div className="mt-8 flex gap-3 print:hidden">
              <button
                onClick={() => window.print()}
                className="flex items-center gap-2 rounded-lg bg-primary text-black border-4 border-black px-6 py-3 font-black text-sm shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm cursor-pointer"
              >
                <Printer size={16} /> Print Certificate
              </button>
              <button
                onClick={() => setShowCertificate(false)}
                className="rounded-lg bg-white border-4 border-black px-6 py-3 font-black text-sm shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm cursor-pointer"
              >
                Return to Dashboard
              </button>
            </div>
          </div>
        </div>
      )}
      {showScrollTop && (
        <button
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          aria-label="Scroll to top"
          className="fixed bottom-6 right-6 z-50 rounded-lg bg-primary text-white border-4 border-black px-4 py-3 font-black shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm cursor-pointer"
        >
          ↑ Top
        </button>
      )}
    </div>
  );
}
