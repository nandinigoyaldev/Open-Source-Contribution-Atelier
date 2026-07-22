import { useState, useEffect } from "react";
import { Menu } from "lucide-react";
import {
  BookOpen,
  BriefcaseBusiness,
  LayoutGrid,
  MessageSquare,
  Search,
  Shield,
  TerminalSquare,
  TrendingUp,
  Trophy,
  X,
  Settings,
  Eye,
  FileText,
  Target,
  FileDiff,
  SearchCode,
  MessageSquareHeart,
  GitMerge,
  FileEdit,
  Key,
  ShoppingBag,
} from "lucide-react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../features/auth/AuthContext";
import { fetchLessonsApi } from "../../lib/lessons";
import api from "../../api";
import LogoutButtonWithConfirm from "./LogoutButtonWithConfirm";
import { SyncStatusIndicator } from "../ui/SyncStatusIndicator";
import { NotificationMenu } from "../ui/NotificationMenu";
import { ThemeToggle } from "../ui/ThemeToggle";

const navGroups = [
  {
    title: "Curriculum",
    items: [
      { to: "/dashboard", label: "Dashboard", icon: LayoutGrid },
      { to: "/learning-path", label: "Lessons", icon: BookOpen },
      { to: "/challenges", label: "Challenges", icon: Trophy },
      { to: "/admin/content-studio", label: "Content Studio", icon: FileEdit },
    ],
  },

  {
    title: "Practice",
    items: [
      { to: "/contributor-sandbox", label: "Playground", icon: TerminalSquare },
      { to: "/a11y-sandbox", label: "A11y Sandbox", icon: Eye },
      { to: "/pr-diff-summarizer", label: "PR Summarizer", icon: FileDiff },
      { to: "/bounties", label: "Bounties", icon: Target },
      {
        to: "/good-first-issues",
        label: "Good First Issues",
        icon: SearchCode,
      },
      {
        to: "/tone-coach",
        label: "Tone Coach",
        icon: MessageSquareHeart,
      },
      {
        to: "/conflict-scenario-builder",
        label: "Conflict Builder",
        icon: GitMerge,
      },
    ],
  },
  {
    title: "Progress",
    items: [
      { to: "/portfolio", label: "Portfolio", icon: FileText },
      { to: "/leaderboard", label: "Leaderboard", icon: TrendingUp },
      { to: "/shop", label: "XP Shop", icon: ShoppingBag },
    ],
  },
  {
    title: "Collaboration",
    items: [
      { to: "/community", label: "Community", icon: BriefcaseBusiness },
      { to: "/chat", label: "Chat", icon: MessageSquare },
      { to: "/peer-review", label: "Peer Review", icon: Shield },
    ],
  },
  {
    title: "Account",
    items: [
      { to: "/profile", label: "Settings", icon: Settings },
      { to: "/settings/connected-apps", label: "Connected Apps", icon: Shield },
      { to: "/admin/oauth-clients", label: "OAuth Apps", icon: Key },
    ],
  },
];

export function Navigation() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<{
    lessons: {
      slug: string;
      title: string;
      description: string;
      summary: string;
    }[];
    challenges: { slug: string; title: string; summary: string }[];
  } | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [lessonsCatalog, setLessonsCatalog] = useState<
    { slug: string; title: string; description: string }[]
  >([]);
  const [mobileOpen, setMobileOpen] = useState(false);

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

        const results = {
          lessons: filteredLessons.map((l) => ({
            ...l,
            summary: l.description,
          })),
          challenges: filteredChallenges,
        };
        setSearchResults(results);
        setIsSearching(false);

        const totalResults = results.lessons.length + results.challenges.length;
        api
          .post("/search/track/", { query, result_count: totalResults })
          .catch(() => {});
      } else {
        setSearchResults(null);
      }
    }, 200);

    return () => clearTimeout(delayDebounceFn);
  }, [searchQuery, lessonsCatalog]);

  return (
    <>
      <aside
        aria-label="Main sidebar"
        className="fixed inset-y-0 left-0 z-40 hidden w-[240px] border-r-4 border-black bg-surface-lowest/95 backdrop-blur-xl lg:flex lg:flex-col dark:bg-[#0f0e0c]/95 dark:border-[#2e2924]"
      >
        <div className="flex h-[72px] flex-col justify-center border-b-4 border-black px-6 dark:border-[#2e2924]">
          <Link
            to="/"
            className="block font-display text-xl font-black tracking-tight text-black dark:text-white uppercase"
          >
            Atelier
          </Link>
          <span className="text-[10px] font-mono uppercase tracking-[0.1em] text-muted dark:text-[#9b8f80]">
            Contribution Console
          </span>
        </div>

        <nav
          aria-label="Sidebar navigation"
          className="flex-1 px-3 py-4 overflow-y-auto space-y-4"
        >
          {navGroups.map((group) => (
            <div key={group.title} className="space-y-1">
              <h3 className="px-3 text-[10px] font-mono uppercase tracking-[0.2em] text-muted/65 dark:text-[#9b8f80]/65">
                {group.title}
              </h3>
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      title={item.label}
                      className={({ isActive }) =>
                        [
                          "flex items-center gap-2.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all duration-200 border-2",
                          isActive
                            ? "bg-[#C3C0FF]/25 border-black dark:border-[#2e2924] text-text shadow-card-sm dark:text-[#f0ebe2]"
                            : "border-transparent text-muted hover:bg-surface-low hover:text-text dark:text-[#c4bbae] dark:hover:bg-[#151411] dark:hover:text-[#f0ebe2]",
                        ].join(" ")
                      }
                    >
                      <Icon size={14} />
                      <span>{item.label}</span>
                    </NavLink>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t-4 border-black px-4 py-3 text-xs text-muted dark:border-[#2e2924] dark:text-[#c4bbae]">
          <div className="flex items-center gap-2 px-2 py-1.5">
            <Shield size={14} />
            <span>Community Safe Mode</span>
          </div>
        </div>
      </aside>

      <header className="fixed inset-x-0 top-0 z-30 h-[72px] border-b-4 border-black bg-white lg:left-[240px] dark:border-[#2e2924] dark:bg-[#0f0e0c]">
        <div className="flex h-full items-center justify-between space-x-4 px-4 sm:px-6 lg:px-8">
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="lg:hidden rounded-lg border-2 border-black p-2 menu-btn"
            aria-expanded={mobileOpen}
            aria-label={mobileOpen ? "Close mobile menu" : "Open mobile menu"}
            aria-controls="mobile-menu"
          >
            <Menu size={22} />
          </button>
          <div className="flex min-w-0 items-center space-x-3 relative grow max-w-md">
            <div className="flex items-center space-x-2 rounded-lg bg-surface-low px-3 py-2 text-muted w-full border-2 border-black dark:border-[#2e2924] shadow-card-sm focus-within:bg-white transition-all dark:bg-[#151411] dark:text-[#c4bbae] dark:focus-within:bg-[#0f0e0c]">
              <Search size={15} className="shrink-0" />
              <input
                type="text"
                placeholder="Search lessons, issues..."
                aria-label="Search lessons and issues"
                className="bg-transparent border-none outline-none text-sm w-full text-text placeholder:text-muted/75 dark:text-[#f0ebe2] dark:placeholder:text-[#c4bbae]/75"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  aria-label="Clear search"
                  className="p-0.5 rounded hover:bg-gray-200 dark:hover:bg-[#2e2924] hover:text-text"
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
          <div className="flex items-center space-x-3">
            <Link
              to="/dashboard"
              className="hidden rounded-lg px-3 py-2 text-sm font-medium text-primary md:inline-flex"
            >
              Dashboard
            </Link>
            <SyncStatusIndicator />
            <ThemeToggle />
            {user && !user.is_staff && <NotificationMenu />}
            {user ? (
              <div className="flex items-center space-x-2">
                <Link
                  to="/profile"
                  className="font-bold text-sm text-text bg-white px-3 py-2 rounded-lg border-2 border-black dark:bg-[#151411] dark:text-[#f0ebe2] dark:border-[#2e2924] flex items-center gap-1.5 shadow-card-sm hover:bg-surface-low transition-colors dark:hover:bg-[#1f1c18]"
                  title="Profile Settings"
                >
                  👤{" "}
                  <span className="max-w-[80px] truncate">{user.username}</span>
                  {user.is_staff && (
                    <span className="font-black text-[9px] bg-[#ff665c] text-white px-1.5 py-0.5 rounded border border-black dark:border-none">
                      ADMIN
                    </span>
                  )}
                </Link>
                <LogoutButtonWithConfirm />
              </div>
            ) : (
              <div className="flex items-center space-x-3">
                <Link
                  to="/login"
                  className="rounded-xl bg-white border-2 border-black px-4 py-2 text-sm font-bold text-text shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 transition-all dark:bg-[#151411] dark:text-[#f0ebe2] dark:border-[#2e2924]"
                >
                  Log In
                </Link>
                <Link
                  to="/signup"
                  className="rounded-xl bg-[#C3C0FF] border-2 border-black px-4 py-2 text-sm font-black text-black shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 transition-all dark:bg-[#C3C0FF] dark:border-white"
                >
                  Sign Up
                </Link>
              </div>
            )}
          </div>
        </div>
      </header>
      {mobileOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/50 lg:hidden"
          onClick={() => setMobileOpen(false)}
          onKeyDown={(e) => e.key === "Escape" && setMobileOpen(false)}
          aria-hidden="true"
        >
          <div
            id="mobile-menu"
            className="absolute left-0 top-0 h-full w-72 bg-white dark:bg-[#151411] p-6"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="Mobile Navigation"
          >
            <div className="space-y-2">
              {navGroups.map((group) => (
                <div key={group.title} className="space-y-1">
                  <h3 className="px-3 text-[10px] font-mono uppercase tracking-[0.2em] text-muted/65 dark:text-[#9b8f80]/65">
                    {group.title}
                  </h3>
                  <div className="space-y-0.5">
                    {group.items.map((item) => {
                      const Icon = item.icon;
                      return (
                        <NavLink
                          key={item.to}
                          to={item.to}
                          onClick={() => setMobileOpen(false)}
                          className="flex items-center gap-3 rounded-lg px-4 py-3 hover:bg-gray-100 dark:hover:bg-[#1f1c18]"
                        >
                          <Icon size={18} />
                          {item.label}
                        </NavLink>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default Navigation;
