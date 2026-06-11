import { useState, useEffect } from "react";
import {
  Bell,
  BookOpen,
  BriefcaseBusiness,
  LayoutGrid,
  Search,
  Shield,
  TerminalSquare,
  Trophy,
  X,
  Sun,
  Moon,
} from "lucide-react";
import { Link, NavLink } from "react-router-dom";
import { fetchApi } from "../../lib/api";
import { useTheme } from "../../hooks/useTheme";
import { useAuth } from "../../features/auth/AuthContext";
import { fetchLessonsApi } from "../../lib/lessons";
import LogoutButtonWithConfirm from "./LogoutButtonWithConfirm";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutGrid },
  { to: "/lessons/what-is-open-source", label: "Lessons", icon: BookOpen },
  { to: "/challenges", label: "Challenges", icon: Trophy },
  { to: "/community", label: "Community", icon: BriefcaseBusiness },
];

export function Navigation() {
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<{
    lessons: any[];
    challenges: any[];
  } | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [lessonsCatalog, setLessonsCatalog] = useState<any[]>([]);

  useEffect(() => {
    fetchLessonsApi().then((data) => setLessonsCatalog(data));
  }, []);

  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      if (searchQuery.trim().length > 1) {
        setIsSearching(true);
        const query = searchQuery.toLowerCase();

        const filteredLessons = lessonsCatalog.filter(
          (lesson) =>
            lesson.title.toLowerCase().includes(query) ||
            lesson.description.toLowerCase().includes(query),
        );

        const mockChallenges = [
          {
            title: "Hacktoberfest Warmup",
            summary:
              "Guide contributors through issue triage, branch naming, and clean commits.",
            slug: "hacktoberfest-warmup",
          },
          {
            title: "Git Recovery Lab",
            summary:
              "Practice safe undo flows, rebases, and fixing a messy working tree.",
            slug: "git-recovery-lab",
          },
        ];
        const filteredChallenges = mockChallenges.filter(
          (ch) =>
            ch.title.toLowerCase().includes(query) ||
            ch.summary.toLowerCase().includes(query),
        );

        setSearchResults({
          lessons: filteredLessons,
          challenges: filteredChallenges,
        });
        setIsSearching(false);
      } else {
        setSearchResults(null);
      }
    }, 200);

    return () => clearTimeout(delayDebounceFn);
  }, [searchQuery, lessonsCatalog]);

  useEffect(() => {
    async function loadBadges() {
      try {
        const badges = await fetchApi("/progress/badges/");
        setBadgeCount(badges.length);
      } catch (error) {
        console.error("Failed to load badges:", error);
      }
    }

    loadBadges();
  }, []);

  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-[280px] border-r border-outline bg-surface-lowest/90 backdrop-blur-xl lg:flex lg:flex-col dark:bg-[#0f0e0c]/90 dark:border-[#2e2924]">
        <div className="border-b border-outline px-6 py-5">
          <Link
            to="/"
            className="block font-display text-lg font-bold tracking-[-0.02em] text-text dark:text-[#f0ebe2]"
          >
            The Maintainer Atelier
          </Link>
          <p className="mt-3 rounded-2xl bg-surface-low px-4 py-3 text-sm text-muted shadow-card dark:bg-[#151411] dark:text-[#c4bbae]">
            <span className="font-mono text-[11px] uppercase tracking-[0.24em] text-primary">
              Open Source Programs
            </span>
            <span className="mt-2 block font-semibold text-text dark:text-[#f0ebe2]">
              Admin console for contributor journeys
            </span>
          </p>
        </div>
        <nav className="flex-1 px-4 py-6">
          <div className="space-y-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    [
                      "flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-all duration-200 ease-in-out hover:scale-102 hover:shadow-card",
                      isActive
                        ? "bg-[linear-gradient(135deg,rgba(79,70,229,0.28),rgba(195,192,255,0.16))] text-text shadow-card dark:text-[#f0ebe2]"
                        : "text-muted hover:bg-surface-low hover:text-text dark:text-[#c4bbae] dark:hover:bg-[#151411] dark:hover:text-[#f0ebe2]",
                    ].join(" ")
                  }
                >
                  <Icon size={16} />
                  {item.label}
                </NavLink>
              );
            })}
          </div>
          <div className="mt-8 rounded-2xl bg-[linear-gradient(135deg,rgba(79,70,229,0.9),rgba(195,192,255,0.45))] p-[1px] shadow-card">
            <div className="rounded-2xl bg-surface-low px-4 py-4 dark:bg-[#151411]">
              <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-tertiary">
                Safe sandbox
              </p>
              <p className="mt-2 text-sm text-muted dark:text-[#c4bbae]">
                Run guided Git practice without exposing the real shell.
              </p>
              <Link
                to="/lessons/what-is-open-source"
                className="mt-4 flex items-center justify-center gap-2 rounded-xl bg-primary-container px-4 py-3 text-sm font-semibold text-white shadow-card"
              >
                <TerminalSquare size={15} />
                Start sandbox
              </Link>
            </div>
          </div>
        </nav>
        <div className="border-t border-outline px-4 py-4 text-sm text-muted dark:border-[#2e2924] dark:text-[#c4bbae]">
          <div className="flex items-center gap-3 rounded-xl px-4 py-3 hover:bg-surface-low dark:hover:bg-[#151411]">
            <Shield size={16} />
            Community-safe workflows
          </div>
        </div>
      </aside>

      <header className="fixed inset-x-0 top-0 z-10 border-b border-outline bg-surface/70 backdrop-blur-xl lg:left-[280px] dark:border-[#2e2924] dark:bg-[#0f0e0c]/70">
        <div className="flex items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3 relative grow max-w-md">
            <div className="flex items-center gap-2 rounded-xl bg-surface-low px-3 py-2 text-muted w-full border-2 border-transparent focus-within:border-primary/50 focus-within:bg-white transition-all shadow-sm dark:bg-[#151411] dark:text-[#c4bbae] dark:focus-within:bg-[#0f0e0c]">
              <Search size={15} />
              <input
                type="text"
                placeholder="Search lessons, issues..."
                className="bg-transparent border-none outline-none text-sm w-full text-text placeholder:text-muted/50 dark:text-[#f0ebe2] dark:placeholder:text-[#c4bbae]/50"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="hover:text-text"
                >
                  <X size={14} />
                </button>
              )}
            </div>

            {/* Search Results Dropdown */}
            {searchResults && searchQuery.length > 1 && (
              <div className="absolute top-full left-0 right-0 mt-2 bg-white border-4 border-black rounded-2xl shadow-card p-4 z-50 max-h-[70vh] overflow-y-auto dark:bg-[#151411] dark:border-[#2e2924]">
                {isSearching ? (
                  <p className="text-sm text-muted animate-pulse dark:text-[#c4bbae]">
                    Searching the Atelier...
                  </p>
                ) : (
                  <div className="space-y-6">
                    {searchResults.lessons.length > 0 && (
                      <div>
                        <h4 className="font-mono text-[10px] uppercase tracking-widest text-primary mb-2">
                          Lessons
                        </h4>
                        <div className="space-y-2">
                          {searchResults.lessons.map((lesson) => (
                            <Link
                              key={lesson.slug}
                              to={`/lessons/${lesson.slug}`}
                              onClick={() => setSearchQuery("")}
                              className="block p-2 rounded-lg hover:bg-surface-low transition group dark:hover:bg-[#1f1c18]"
                            >
                              <p className="font-bold text-sm group-hover:text-primary dark:text-[#f0ebe2]">
                                {lesson.title}
                              </p>
                              <p className="text-xs text-muted truncate dark:text-[#c4bbae]">
                                {lesson.summary}
                              </p>
                            </Link>
                          ))}
                        </div>
                      </div>
                    )}
                    {searchResults.challenges.length > 0 && (
                      <div>
                        <h4 className="font-mono text-[10px] uppercase tracking-widest text-accent mb-2">
                          Issues & Challenges
                        </h4>
                        <div className="space-y-2">
                          {searchResults.challenges.map((challenge) => (
                            <Link
                              key={challenge.slug}
                              to="/challenges"
                              onClick={() => setSearchQuery("")}
                              className="block p-2 rounded-lg hover:bg-surface-low transition group dark:hover:bg-[#1f1c18]"
                            >
                              <p className="font-bold text-sm group-hover:text-accent dark:text-[#f0ebe2]">
                                {challenge.title}
                              </p>
                              <p className="text-xs text-muted truncate dark:text-[#c4bbae]">
                                {challenge.summary}
                              </p>
                            </Link>
                          ))}
                        </div>
                      </div>
                    )}
                    {searchResults.lessons.length === 0 &&
                      searchResults.challenges.length === 0 && (
                        <p className="text-sm text-muted italic dark:text-[#c4bbae]">
                          No matching records found in the Atelier.
                        </p>
                      )}
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/dashboard"
              className="hidden rounded-xl px-3 py-2 text-sm font-medium text-primary md:inline-flex"
            >
              Dashboard
            </Link>
            <button
              className="rounded-xl bg-surface-low p-2 text-muted hover:text-text dark:bg-[#151411] dark:text-[#c4bbae] dark:hover:text-[#f0ebe2]"
              onClick={toggleTheme}
              aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
            >
              {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
            </button>
            <button className="rounded-xl bg-surface-low p-2 text-muted hover:text-text dark:bg-[#151411] dark:text-[#c4bbae] dark:hover:text-[#f0ebe2]">
              <Bell size={16} />
            </button>
            {user ? (
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm text-text bg-white px-3 py-2 rounded-xl border-2 border-black dark:bg-[#151411] dark:text-[#f0ebe2] dark:border-[#2e2924] flex items-center gap-1.5 shadow-card-sm">
                  👤{" "}
                  <span className="max-w-[80px] truncate">{user.username}</span>
                  {user.is_staff && (
                    <span className="font-black text-[9px] bg-primary text-white px-1.5 py-0.5 rounded border border-black dark:border-none">
                      ADMIN
                    </span>
                  )}
                </span>
                <LogoutButtonWithConfirm />
              </div>
            ) : (
              <Link
                to="/login"
                className="rounded-xl bg-[linear-gradient(135deg,#4f46e5,#7c72ff)] px-4 py-2 text-sm font-semibold text-white shadow-card"
              >
                Admin Login
              </Link>
            )}
          </div>
        </div>
      </header>
    </>
  );
}
