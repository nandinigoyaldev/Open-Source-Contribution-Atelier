import { useMemo, useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";
import { fallbackLessons, SEVEN_LEVELS, fetchLessonsApi, Lesson } from "../lib/lessons";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Flame,
  GitBranch,
  GitPullRequest,
  Lock,
  Play,
  SearchCode,
  Sparkles,
  Star,
  Target,
  Terminal,
  Trophy,
  Zap,
} from "lucide-react";

export function DashboardPage() {
  const { user } = useAuth();
  const [lessons, setLessons] = useState<Lesson[]>(fallbackLessons);
  const [completedSlugs, setCompletedSlugs] = useState<Set<string>>(new Set());

  // Load completed lessons from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("completed_lesson_slugs");
    if (saved) {
      try {
        setCompletedSlugs(new Set(JSON.parse(saved)));
      } catch {}
    }
  }, []);

  useEffect(() => {
    fetchLessonsApi().then((data) => {
      if (data && data.length > 0) {
        setLessons(data);
      }
    });
  }, []);

  // Determine current active lesson for "Continue Learning"
  const nextLesson = useMemo(() => {
    const firstIncomplete = lessons.find((l) => !completedSlugs.has(l.slug));
    return firstIncomplete || lessons[0];
  }, [lessons, completedSlugs]);

  const completedCount = completedSlugs.size;
  const totalCount = lessons.length || 13;
  const progressPercent = Math.min(100, Math.round((completedCount / totalCount) * 100));

  const totalXP = completedCount * 25 + (completedCount > 0 ? 50 : 0);
  const currentStreak = completedCount > 0 ? Math.min(completedCount, 5) : 0;

  // Badges calculation
  const badges = [
    {
      id: "first-commit",
      title: "First Commit",
      desc: "Created your first Git snapshot",
      icon: "🌱",
      unlocked: completedCount >= 1,
    },
    {
      id: "git-explorer",
      title: "Git Explorer",
      desc: "Mastered branching and status commands",
      icon: "⚡",
      unlocked: completedCount >= 3,
    },
    {
      id: "issue-detective",
      title: "Issue Detective",
      desc: "Triaged repository issues and labels",
      icon: "🔍",
      unlocked: completedCount >= 6,
    },
    {
      id: "pr-apprentice",
      title: "PR Apprentice",
      desc: "Crafted Pull Requests with issue links",
      icon: "📝",
      unlocked: completedCount >= 8,
    },
    {
      id: "code-reviewer",
      title: "Code Reviewer",
      desc: "Resolved merge conflicts & review feedback",
      icon: "🛡️",
      unlocked: completedCount >= 10,
    },
    {
      id: "oss-contributor",
      title: "Open Source Contributor",
      desc: "Completed full 10-step contribution lifecycle",
      icon: "🏆",
      unlocked: completedCount >= 12,
    },
  ];

  return (
    <div className="min-h-screen bg-[#FDFBF7] dark:bg-[#0E0D0B] text-slate-900 dark:text-[#F0EBE2] p-4 sm:p-8 font-sans space-y-8 max-w-6xl mx-auto">
      {/* Welcome & Continue Learning Hero Card */}
      <section className="bg-white dark:bg-[#151411] border-4 border-black dark:border-[#2E2924] rounded-3xl p-6 sm:p-10 shadow-card flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-3 max-w-xl">
          <div className="flex items-center gap-2">
            <span className="text-xs font-black uppercase tracking-wider bg-amber-400 text-black px-3 py-1 rounded-full border border-black/30">
              AI Mentor Learning Path
            </span>
            <span className="text-xs font-mono text-slate-400">
              {progressPercent}% Complete
            </span>
          </div>

          <h1 className="text-2xl sm:text-4xl font-black text-slate-950 dark:text-white tracking-tight">
            Welcome back{user?.username ? `, ${user.username}` : ""}! 🚀
          </h1>

          <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
            Your personalized open-source mentor is ready. Next up: <strong className="text-slate-900 dark:text-white">{nextLesson.title}</strong> ({nextLesson.category}).
          </p>

          {/* Quick Progress Bar */}
          <div className="w-full bg-slate-100 dark:bg-[#1E1C18] h-3 rounded-full overflow-hidden border border-black/10 dark:border-[#2E2924] mt-2">
            <div
              className="bg-amber-400 h-full transition-all duration-500 rounded-full"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* Primary Call to Action */}
        <div className="flex flex-col sm:flex-row md:flex-col gap-3 flex-shrink-0">
          <Link
            to={`/learn/${nextLesson.slug}`}
            className="px-8 py-4 bg-amber-400 hover:bg-amber-300 text-black font-black text-sm rounded-2xl border-2 border-black shadow-card-sm hover:-translate-y-0.5 transition-all flex items-center justify-center gap-2"
          >
            <Play className="w-4 h-4 fill-black" />
            <span>Continue Learning</span>
            <ArrowRight className="w-4 h-4" />
          </Link>

          <Link
            to="/simulate"
            className="px-6 py-3.5 bg-slate-100 dark:bg-[#1E1C18] hover:bg-slate-200 text-slate-800 dark:text-slate-200 font-bold text-xs rounded-2xl border border-black/20 text-center transition-colors"
          >
            ⚡ Open-Source Simulation
          </Link>
        </div>
      </section>

      {/* Gamification Stats Overview */}
      <section className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-[#151411] border-2 border-black/10 dark:border-[#2E2924] rounded-2xl p-5 text-center space-y-1">
          <div className="w-8 h-8 rounded-full bg-amber-100 dark:bg-amber-950 text-amber-600 mx-auto flex items-center justify-center font-bold">
            <Zap className="w-4 h-4 fill-amber-500 text-amber-500" />
          </div>
          <p className="text-2xl font-black">{totalXP}</p>
          <p className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">Total XP Earned</p>
        </div>

        <div className="bg-white dark:bg-[#151411] border-2 border-black/10 dark:border-[#2E2924] rounded-2xl p-5 text-center space-y-1">
          <div className="w-8 h-8 rounded-full bg-rose-100 dark:bg-rose-950 text-rose-600 mx-auto flex items-center justify-center font-bold">
            <Flame className="w-4 h-4 fill-rose-500 text-rose-500" />
          </div>
          <p className="text-2xl font-black">{currentStreak} Days</p>
          <p className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">Learning Streak</p>
        </div>

        <div className="bg-white dark:bg-[#151411] border-2 border-black/10 dark:border-[#2E2924] rounded-2xl p-5 text-center space-y-1">
          <div className="w-8 h-8 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-600 mx-auto flex items-center justify-center font-bold">
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <p className="text-2xl font-black">{completedCount}/{totalCount}</p>
          <p className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">Lessons Mastered</p>
        </div>

        <div className="bg-white dark:bg-[#151411] border-2 border-black/10 dark:border-[#2E2924] rounded-2xl p-5 text-center space-y-1">
          <div className="w-8 h-8 rounded-full bg-purple-100 dark:bg-purple-950 text-purple-600 mx-auto flex items-center justify-center font-bold">
            <Trophy className="w-4 h-4 text-purple-500" />
          </div>
          <p className="text-2xl font-black">{badges.filter((b) => b.unlocked).length}/{badges.length}</p>
          <p className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">Milestone Badges</p>
        </div>
      </section>

      {/* Core Learning Pillars */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Pillar 1: 7-Level Learning Path */}
        <div className="bg-white dark:bg-[#151411] border-2 border-black/10 dark:border-[#2E2924] rounded-2xl p-6 shadow-sm space-y-4 flex flex-col justify-between">
          <div className="space-y-2">
            <div className="w-10 h-10 rounded-xl bg-amber-400/20 text-amber-600 flex items-center justify-center font-black">
              <BookOpen className="w-5 h-5" />
            </div>
            <h3 className="font-black text-base text-slate-900 dark:text-white">
              7-Level Learning Path
            </h3>
            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
              Step-by-step beginner journey covering open source concepts, Git mechanics, GitHub remotes, PR workflows, and maintainership.
            </p>
          </div>
          <Link
            to="/learn"
            className="text-xs font-black text-amber-600 dark:text-amber-400 hover:underline flex items-center gap-1 pt-2"
          >
            <span>Explore Curriculum</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {/* Pillar 2: Open-Source Simulation */}
        <div className="bg-white dark:bg-[#151411] border-2 border-black/10 dark:border-[#2E2924] rounded-2xl p-6 shadow-sm space-y-4 flex flex-col justify-between">
          <div className="space-y-2">
            <div className="w-10 h-10 rounded-xl bg-emerald-400/20 text-emerald-600 flex items-center justify-center font-black">
              <GitPullRequest className="w-5 h-5" />
            </div>
            <h3 className="font-black text-base text-slate-900 dark:text-white">
              Contribution Simulator
            </h3>
            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
              Practice the complete 10-step contribution lifecycle on repository <code>TaskTracker</code>: issue claiming, branching, fixing code, testing, and PR review.
            </p>
          </div>
          <Link
            to="/simulate"
            className="text-xs font-black text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-1 pt-2"
          >
            <span>Launch Simulation</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {/* Pillar 3: Issue Triage Practice */}
        <div className="bg-white dark:bg-[#151411] border-2 border-black/10 dark:border-[#2E2924] rounded-2xl p-6 shadow-sm space-y-4 flex flex-col justify-between">
          <div className="space-y-2">
            <div className="w-10 h-10 rounded-xl bg-blue-400/20 text-blue-600 flex items-center justify-center font-black">
              <SearchCode className="w-5 h-5" />
            </div>
            <h3 className="font-black text-base text-slate-900 dark:text-white">
              Issue Triage Sandbox
            </h3>
            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
              Diagnose community bug reports, apply label filters, evaluate severity, and formulate maintainer replies.
            </p>
          </div>
          <Link
            to="/triage"
            className="text-xs font-black text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1 pt-2"
          >
            <span>Practice Triage</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </section>

      {/* Meaningful Badges Shelf */}
      <section className="bg-white dark:bg-[#151411] border-2 border-black/10 dark:border-[#2E2924] rounded-3xl p-6 sm:p-8 space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-black text-slate-900 dark:text-white flex items-center gap-2">
              <Trophy className="w-5 h-5 text-amber-500" />
              <span>Milestone Badges</span>
            </h2>
            <p className="text-xs text-slate-500">
              Earned by mastering practical open-source contribution milestones.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {badges.map((b) => (
            <div
              key={b.id}
              className={`p-4 rounded-2xl border-2 text-center space-y-2 transition-all ${
                b.unlocked
                  ? "bg-amber-50 dark:bg-[#1A1815] border-amber-400 shadow-sm"
                  : "bg-slate-50 dark:bg-[#12110E] border-black/10 opacity-50"
              }`}
            >
              <div className="text-3xl">{b.icon}</div>
              <p className="text-xs font-black text-slate-900 dark:text-white leading-tight">
                {b.title}
              </p>
              <p className="text-[10px] text-slate-500 leading-relaxed font-mono">
                {b.desc}
              </p>
              {b.unlocked ? (
                <span className="inline-block text-[10px] font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-950/60 px-2 py-0.5 rounded-full">
                  Unlocked
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-[10px] font-mono text-slate-400">
                  <Lock className="w-3 h-3" /> Locked
                </span>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
