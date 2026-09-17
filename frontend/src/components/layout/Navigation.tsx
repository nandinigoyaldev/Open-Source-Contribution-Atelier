import { useState, useRef, useEffect, useCallback } from "react";
import {
  BookOpen,
  GitPullRequest,
  LayoutGrid,
  Menu,
  Search,
  Trophy,
  User,
  X,
  Zap,
  ChevronDown,
  TerminalSquare,
  Shield,
  Settings,
  Users,
  BarChart3,
  Award,
  MessageSquare,
  FileCode,
  GitBranch,
  GitMerge,
  Box,
  Puzzle,
  Globe,
  ExternalLink,
  SearchCode,
} from "lucide-react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../features/auth/AuthContext";
import LogoutButtonWithConfirm from "./LogoutButtonWithConfirm";
import { ThemeToggle } from "../ui/ThemeToggle";

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
}

interface NavDropdown {
  label: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
  items: NavItem[];
}

type NavEntry = NavItem | NavDropdown;

function isDropdown(entry: NavEntry): entry is NavDropdown {
  return "items" in entry;
}

const PRIMARY_NAV: NavEntry[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutGrid },
  {
    label: "Learn",
    icon: BookOpen,
    items: [
      { to: "/learning-path", label: "Learning Path", icon: BookOpen },
      { to: "/pathway", label: "Pathway", icon: Globe },
      { to: "/challenges", label: "Challenges", icon: Trophy },
      { to: "/skill-tree", label: "Skill Tree", icon: Puzzle },
    ],
  },
  {
    label: "Sandbox",
    icon: TerminalSquare,
    items: [
      { to: "/contributor-sandbox", label: "Contributor Sandbox", icon: TerminalSquare },
      { to: "/sandbox", label: "Sandbox", icon: Box },
      { to: "/git-rebase-simulator", label: "Git Rebase Visualizer", icon: GitMerge },
      { to: "/git-bisect-game", label: "Git Bisect Game", icon: GitBranch },
      { to: "/monorepo-visualizer", label: "Monorepo Visualizer", icon: GitBranch },
      { to: "/dockerfile-linter", label: "Dockerfile Linter", icon: FileCode },
    ],
  },
  { to: "/community", label: "Community", icon: Users },
  { to: "/leaderboard", label: "Leaderboard", icon: Award },
];

const ADMIN_ITEMS: NavItem[] = [
  { to: "/admin/content-studio", label: "Content Studio", icon: FileCode },
  { to: "/admin/audit", label: "Audit Log", icon: Shield },
  { to: "/admin/security", label: "Security", icon: Shield },
  { to: "/admin/vulnerabilities", label: "Vulnerabilities", icon: Shield },
  { to: "/admin/performance", label: "API Performance", icon: BarChart3 },
  { to: "/admin/bundle-performance", label: "Bundle Performance", icon: BarChart3 },
  { to: "/admin/backups", label: "Backups", icon: Box },
  { to: "/admin/celery", label: "Celery Tasks", icon: Settings },
  { to: "/admin/oauth-clients", label: "OAuth Clients", icon: Puzzle },
  { to: "/admin/usage-analytics", label: "Usage Analytics", icon: BarChart3 },
];

const SETTINGS_ITEMS: NavItem[] = [
  { to: "/profile", label: "Profile", icon: User },
  { to: "/settings/notifications", label: "Notifications", icon: Settings },
  { to: "/settings/billing", label: "Billing", icon: Settings },
  { to: "/settings/invoices", label: "Invoices", icon: Settings },
  { to: "/settings/webhooks", label: "Webhooks", icon: Settings },
  { to: "/settings/connected-apps", label: "Connected Apps", icon: Puzzle },
];

function NavLinkItem({
  item,
  isActive,
  onClick,
}: {
  item: NavItem;
  isActive: (path: string) => boolean;
  onClick?: () => void;
}) {
  const Icon = item.icon;
  const active = isActive(item.to);
  return (
    <NavLink
      to={item.to}
      onClick={onClick}
      className={({ isActive: linkActive }) =>
        `flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
          linkActive || active
            ? "bg-amber-400/20 text-amber-700 dark:text-amber-300"
            : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5"
        }`
      }
    >
      <Icon size={16} />
      <span>{item.label}</span>
    </NavLink>
  );
}

function DropdownMenu({
  nav,
  isItemActive,
  onClose,
}: {
  nav: NavDropdown;
  isItemActive: (path: string) => boolean;
  onClose?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();

  const handleEnter = useCallback(() => {
    clearTimeout(timeoutRef.current);
    setOpen(true);
  }, []);

  const handleLeave = useCallback(() => {
    timeoutRef.current = setTimeout(() => setOpen(false), 150);
  }, []);

  useEffect(() => {
    return () => clearTimeout(timeoutRef.current);
  }, []);

  const isActive = nav.items.some((item) => isItemActive(item.to));
  const Icon = nav.icon;

  return (
    <div
      ref={ref}
      className="relative"
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      <button
        onClick={() => setOpen(!open)}
        onBlur={() => {
          timeoutRef.current = setTimeout(() => setOpen(false), 150);
        }}
        className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
          isActive
            ? "bg-amber-400/20 text-amber-700 dark:text-amber-300"
            : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5"
        }`}
      >
        <Icon size={16} />
        <span>{nav.label}</span>
        <ChevronDown
          size={14}
          className={`transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 w-56 bg-white dark:bg-[#1a1915] border-2 border-slate-200 dark:border-[#2E2924] rounded-xl shadow-lg py-1 z-50">
          {nav.items.map((item) => {
            const ItemIcon = item.icon;
            return (
              <Link
                key={item.to}
                to={item.to}
                onClick={() => {
                  setOpen(false);
                  onClose?.();
                }}
                className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                  isItemActive(item.to)
                    ? "bg-amber-400/20 text-amber-700 dark:text-amber-300"
                    : "text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5"
                }`}
              >
                <ItemIcon size={16} className="flex-shrink-0" />
                <span className="font-medium">{item.label}</span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SearchButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-400 dark:text-slate-500 bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-[#2E2924] hover:border-slate-300 dark:hover:border-[#3E3934] transition-colors"
      aria-label="Search"
    >
      <Search size={16} />
      <span className="hidden lg:inline">Search...</span>
      <kbd className="hidden lg:inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-mono bg-white dark:bg-[#151411] border border-slate-200 dark:border-[#2E2924] rounded text-slate-400 dark:text-slate-500">
        /
      </kbd>
    </button>
  );
}

function UserDropdown({
  user,
  isItemActive,
}: {
  user: { username: string; avatar?: string };
  isItemActive: (path: string) => boolean;
}) {
  const [open, setOpen] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();

  const handleEnter = useCallback(() => {
    clearTimeout(timeoutRef.current);
    setOpen(true);
  }, []);

  const handleLeave = useCallback(() => {
    timeoutRef.current = setTimeout(() => setOpen(false), 150);
  }, []);

  useEffect(() => {
    return () => clearTimeout(timeoutRef.current);
  }, []);

  return (
    <div
      className="relative"
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-2 py-1.5 rounded-lg border border-slate-200 dark:border-[#2E2924] hover:bg-slate-50 dark:hover:bg-white/5 transition-colors"
      >
        <div className="w-7 h-7 rounded-full bg-amber-400 border-2 border-black flex items-center justify-center">
          <User size={14} className="text-black" />
        </div>
        <span className="hidden lg:inline text-sm font-medium text-slate-700 dark:text-slate-300 max-w-[100px] truncate">
          {user.username}
        </span>
        <ChevronDown
          size={14}
          className={`hidden lg:block text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="absolute top-full right-0 mt-1 w-56 bg-white dark:bg-[#1a1915] border-2 border-slate-200 dark:border-[#2E2924] rounded-xl shadow-lg py-1 z-50">
          <div className="px-4 py-3 border-b border-slate-100 dark:border-[#2E2924]">
            <p className="text-sm font-bold text-slate-900 dark:text-white truncate">
              {user.username}
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              {user.email || "Account"}
            </p>
          </div>

          <div className="py-1">
            <Link
              to="/profile"
              onClick={() => setOpen(false)}
              className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                isItemActive("/profile")
                  ? "bg-amber-400/20 text-amber-700 dark:text-amber-300"
                  : "text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5"
              }`}
            >
              <User size={16} />
              <span className="font-medium">Profile</span>
            </Link>
          </div>

          <div className="py-1 border-t border-slate-100 dark:border-[#2E2924]">
            {SETTINGS_ITEMS.filter((i) => i.to !== "/profile").map((item) => {
              const ItemIcon = item.icon;
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  onClick={() => setOpen(false)}
                  className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                    isItemActive(item.to)
                      ? "bg-amber-400/20 text-amber-700 dark:text-amber-300"
                      : "text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5"
                  }`}
                >
                  <ItemIcon size={16} />
                  <span className="font-medium">{item.label}</span>
                </Link>
              );
            })}
          </div>

          <div className="py-1 border-t border-slate-100 dark:border-[#2E2924]">
            <LogoutButtonWithConfirm />
          </div>
        </div>
      )}
    </div>
  );
}

export function Navigation() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [mobileOpenGroup, setMobileOpenGroup] = useState<string | null>(null);

  const isItemActive = useCallback(
    (path: string) => {
      if (typeof window === "undefined") return false;
      return window.location.pathname === path;
    },
    [],
  );

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "/" && !e.ctrlKey && !e.metaKey) {
        const target = e.target as HTMLElement;
        if (
          target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable
        ) {
          return;
        }
        e.preventDefault();
        navigate("/dashboard");
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [navigate]);

  return (
    <nav className="bg-white/80 dark:bg-[#151411]/80 backdrop-blur-xl border-b-2 border-slate-200 dark:border-[#2E2924] sticky top-0 z-40">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 gap-4">
          {/* Logo */}
          <Link to="/dashboard" className="flex items-center gap-2.5 group shrink-0">
            <div className="w-9 h-9 rounded-xl bg-amber-400 border-2 border-black flex items-center justify-center shadow-card-sm group-hover:-translate-y-0.5 transition-transform">
              <Zap className="w-5 h-5 fill-black" />
            </div>
            <div className="hidden sm:block">
              <span className="font-black text-sm tracking-tight text-slate-900 dark:text-white block leading-tight">
                Open-Source
              </span>
              <span className="text-[10px] font-mono text-amber-600 dark:text-amber-400 uppercase tracking-wider block font-bold">
                AI Mentor
              </span>
            </div>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden lg:flex items-center gap-1 flex-1 justify-center max-w-2xl">
            {PRIMARY_NAV.map((entry) => {
              if (isDropdown(entry)) {
                return (
                  <DropdownMenu
                    key={entry.label}
                    nav={entry}
                    isItemActive={isItemActive}
                  />
                );
              }
              return (
                <NavLinkItem
                  key={entry.to}
                  item={entry}
                  isActive={isItemActive}
                />
              );
            })}

            {user && (
              <DropdownMenu
                nav={{
                  label: "Admin",
                  icon: Shield,
                  items: ADMIN_ITEMS,
                }}
                isItemActive={isItemActive}
              />
            )}
          </div>

          {/* Right Actions */}
          <div className="hidden lg:flex items-center gap-2 shrink-0">
            <SearchButton onClick={() => navigate("/dashboard")} />
            <ThemeToggle iconSize={16} buttonClassName="p-2" />

            {user ? (
              <UserDropdown user={user} isItemActive={isItemActive} />
            ) : (
              <div className="flex items-center gap-2">
                <Link
                  to="/login"
                  className="px-4 py-2 text-sm font-medium text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition-colors"
                >
                  Log In
                </Link>
                <Link
                  to="/signup"
                  className="px-4 py-2 bg-amber-400 hover:bg-amber-300 text-black font-bold text-sm rounded-xl border-2 border-black shadow-card-sm transition-all hover:-translate-y-0.5"
                >
                  Get Started
                </Link>
              </div>
            )}
          </div>

          {/* Mobile: Search + Theme + Hamburger */}
          <div className="flex lg:hidden items-center gap-2 shrink-0">
            <SearchButton onClick={() => navigate("/dashboard")} />
            <ThemeToggle iconSize={16} buttonClassName="p-1.5" />
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg border border-slate-200 dark:border-[#2E2924] text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-t-2 border-slate-200 dark:border-[#2E2924] bg-white dark:bg-[#151411] max-h-[calc(100vh-4rem)] overflow-y-auto">
          <div className="px-4 py-3 space-y-1">
            {PRIMARY_NAV.map((entry) => {
              if (isDropdown(entry)) {
                const isGroupOpen = mobileOpenGroup === entry.label;
                const Icon = entry.icon;
                return (
                  <div key={entry.label}>
                    <button
                      onClick={() =>
                        setMobileOpenGroup(isGroupOpen ? null : entry.label)
                      }
                      className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                        entry.items.some((i) => isItemActive(i.to))
                          ? "bg-amber-400/20 text-amber-700 dark:text-amber-300"
                          : "text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5"
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <Icon size={18} />
                        <span>{entry.label}</span>
                      </div>
                      <ChevronDown
                        size={16}
                        className={`transition-transform ${isGroupOpen ? "rotate-180" : ""}`}
                      />
                    </button>
                    {isGroupOpen && (
                      <div className="ml-4 pl-3 border-l-2 border-slate-200 dark:border-[#2E2924] space-y-0.5 mt-1 mb-2">
                        {entry.items.map((item) => {
                          const ItemIcon = item.icon;
                          return (
                            <NavLink
                              key={item.to}
                              to={item.to}
                              onClick={() => {
                                setMobileMenuOpen(false);
                                setMobileOpenGroup(null);
                              }}
                              className={({ isActive }) =>
                                `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                                  isActive
                                    ? "bg-amber-400/20 text-amber-700 dark:text-amber-300"
                                    : "text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5"
                                }`
                              }
                            >
                              <ItemIcon size={16} />
                              <span>{item.label}</span>
                            </NavLink>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              }

              const Icon = entry.icon;
              return (
                <NavLink
                  key={entry.to}
                  to={entry.to}
                  onClick={() => setMobileMenuOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-amber-400/20 text-amber-700 dark:text-amber-300"
                        : "text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5"
                    }`
                  }
                >
                  <Icon size={18} />
                  <span>{entry.label}</span>
                </NavLink>
              );
            })}

            {user && (
              <>
                <div className="border-t border-slate-100 dark:border-[#2E2924] my-2" />

                <NavLink
                  to="/profile"
                  onClick={() => setMobileMenuOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-amber-400/20 text-amber-700 dark:text-amber-300"
                        : "text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5"
                    }`
                  }
                >
                  <User size={18} />
                  <span>Profile</span>
                </NavLink>

                {SETTINGS_ITEMS.filter((i) => i.to !== "/profile").map(
                  (item) => {
                    const ItemIcon = item.icon;
                    return (
                      <NavLink
                        key={item.to}
                        to={item.to}
                        onClick={() => setMobileMenuOpen(false)}
                        className={({ isActive }) =>
                          `flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                            isActive
                              ? "bg-amber-400/20 text-amber-700 dark:text-amber-300"
                              : "text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5"
                          }`
                        }
                      >
                        <ItemIcon size={18} />
                        <span>{item.label}</span>
                      </NavLink>
                    );
                  },
                )}

                <div className="border-t border-slate-100 dark:border-[#2E2924] my-2" />

                <div className="px-1">
                  <LogoutButtonWithConfirm />
                </div>
              </>
            )}

            {!user && (
              <>
                <div className="border-t border-slate-100 dark:border-[#2E2924] my-2" />
                <div className="flex gap-2 px-1">
                  <Link
                    to="/login"
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex-1 text-center py-2.5 text-sm font-medium bg-slate-100 dark:bg-white/5 rounded-xl text-slate-700 dark:text-slate-300"
                  >
                    Log In
                  </Link>
                  <Link
                    to="/signup"
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex-1 text-center py-2.5 text-sm font-bold bg-amber-400 text-black rounded-xl border-2 border-black"
                  >
                    Get Started
                  </Link>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}

export default Navigation;
