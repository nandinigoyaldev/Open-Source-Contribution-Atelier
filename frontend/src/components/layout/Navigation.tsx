import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  User,
  X,
  Menu,
  ChevronDown,
  Settings,
  Puzzle,
  LayoutGrid,
  BookOpen,
  TerminalSquare,
  Users,
  Award,
  History,
} from "lucide-react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../features/auth/AuthContext";
import LogoutButtonWithConfirm from "./LogoutButtonWithConfirm";
import { ThemeToggle } from "../ui/ThemeToggle";
import { NotificationMenu } from "../ui/NotificationMenu";

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
}

const SETTINGS_ITEMS: NavItem[] = [
  { to: "/profile", label: "Profile", icon: User },
  { to: "/settings/notifications", label: "Notifications", icon: Settings },
  { to: "/settings/billing", label: "Billing", icon: Settings },
  { to: "/settings/invoices", label: "Invoices", icon: Settings },
  { to: "/settings/webhooks", label: "Webhooks", icon: Settings },
  { to: "/settings/connected-apps", label: "Connected Apps", icon: Puzzle },
];

const MOBILE_WORKSPACE_ITEMS: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutGrid },
  { to: "/learning-path", label: "Learning Path", icon: BookOpen },
  { to: "/contributor-sandbox", label: "Sandbox", icon: TerminalSquare },
  { to: "/community", label: "Community", icon: Users },
  { to: "/leaderboard", label: "Leaderboard", icon: Award },
  { to: "/activity", label: "My activity", icon: History },
];

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
  user: {
    username: string;
    email?: string;
    avatar_url?: string | null;
    is_staff: boolean;
    badge_count?: number;
  };
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
      className="relative hidden lg:block"
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={`Open account menu for ${user.username}`}
        className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white/70 px-2 py-1.5 transition-colors hover:border-amber-300 hover:bg-amber-50 dark:border-[#2E2924] dark:bg-white/5 dark:hover:border-amber-400/50 dark:hover:bg-amber-400/10"
      >
        <div className="w-7 h-7 rounded-full bg-amber-400 border-2 border-black flex items-center justify-center">
          <User size={14} className="text-black" />
        </div>
        <span className="hidden lg:inline text-sm font-medium text-slate-700 dark:text-slate-300 max-w-[100px] truncate">
          {user.username}
        </span>
        {typeof user.badge_count === "number" && user.badge_count > 0 && (
          <span
            data-testid="navbar-user-badge-count"
            className="inline-flex min-w-5 items-center justify-center rounded-full bg-amber-400 px-1.5 py-0.5 text-[10px] font-black leading-none text-black"
          >
            {user.badge_count > 99 ? "99+" : user.badge_count}
          </span>
        )}
        {user.is_staff && (
          <span className="hidden items-center rounded-full bg-slate-900 px-1.5 py-0.5 text-[9px] font-black leading-none text-white lg:inline-flex dark:bg-white dark:text-slate-900">
            ADMIN
          </span>
        )}
        <ChevronDown
          size={14}
          className={`hidden lg:block text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.95 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            role="menu"
            aria-label="Account menu"
            className="absolute right-0 top-full z-50 mt-3 w-72 overflow-hidden rounded-2xl border border-slate-200 bg-white p-2 shadow-2xl shadow-slate-900/10 dark:border-[#2E2924] dark:bg-[#1a1915] dark:shadow-black/30"
          >
            <div className="flex items-center gap-3 rounded-xl bg-slate-50 p-3 dark:bg-white/5">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-amber-400 text-sm font-black text-slate-950">
                {user.username.slice(0, 1).toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-slate-900 dark:text-white">
                  {user.username}
                </p>
                <p className="truncate text-xs text-slate-500 dark:text-slate-400">
                  {user.email || "Your contributor account"}
                </p>
              </div>
            </div>

            <div className="py-2">
              <p className="px-3 pb-1 text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Account
              </p>
              {SETTINGS_ITEMS.map((item) => {
                const ItemIcon = item.icon;
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    onClick={() => setOpen(false)}
                    role="menuitem"
                    className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors ${
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

            <div className="border-t border-slate-100 pt-2 dark:border-[#2E2924]">
              <LogoutButtonWithConfirm />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function Navigation() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const isItemActive = useCallback((path: string) => {
    if (typeof window === "undefined") return false;
    return window.location.pathname === path;
  }, []);

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
      <div className="flex items-center justify-between h-14 px-4 sm:px-6 gap-4">
        {/* Left: Mobile menu button */}
        <button
          type="button"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="grid h-10 w-10 place-items-center rounded-xl border border-slate-200 bg-white/70 text-slate-700 transition hover:border-amber-300 hover:bg-amber-50 dark:border-[#2E2924] dark:bg-white/5 dark:text-slate-200 dark:hover:border-amber-400/50 dark:hover:bg-amber-400/10 lg:hidden"
          aria-label={mobileMenuOpen ? "Close mobile menu" : "Open mobile menu"}
          aria-expanded={mobileMenuOpen}
          aria-controls="mobile-navigation"
        >
          {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>

        {/* Center: Search */}
        <div className="flex-1 flex justify-center max-w-xl mx-auto">
          <SearchButton onClick={() => navigate("/dashboard")} />
        </div>

        {/* Right: Theme + User */}
        <div className="flex items-center gap-2 shrink-0">
          <ThemeToggle iconSize={16} buttonClassName="p-2" />
          {user && <NotificationMenu />}
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
      </div>

      {/* Mobile User Menu Drawer */}
      {mobileMenuOpen && (
        <div
          id="mobile-navigation"
          role="dialog"
          aria-modal="true"
          aria-label="Mobile Navigation"
          className="lg:hidden border-t border-slate-200 bg-white dark:border-[#2E2924] dark:bg-[#151411] max-h-[calc(100vh-3.5rem)] overflow-y-auto"
        >
          <div className="px-4 py-3 space-y-1">
            {user && (
              <>
                <div className="mb-4">
                  <p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                    Workspace
                  </p>
                  {MOBILE_WORKSPACE_ITEMS.map((item) => {
                    const Icon = item.icon;
                    return (
                      <NavLink
                        key={item.to}
                        to={item.to}
                        onClick={() => setMobileMenuOpen(false)}
                        className={({ isActive }) =>
                          `flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition-colors ${
                            isActive
                              ? "bg-amber-400/20 text-amber-700 dark:text-amber-300"
                              : "text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-white/5"
                          }`
                        }
                      >
                        <Icon size={18} />
                        <span>{item.label}</span>
                      </NavLink>
                    );
                  })}
                </div>
                <div className="mb-3 flex items-center justify-between rounded-2xl bg-slate-50 px-3 py-3 dark:bg-white/5">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-bold text-slate-900 dark:text-white">
                      {user.username}
                    </p>
                    <p className="truncate text-xs text-slate-500 dark:text-slate-400">
                      {user.email || "Account"}
                    </p>
                  </div>
                  <Link
                    to="/profile"
                    onClick={() => setMobileMenuOpen(false)}
                    className="rounded-lg px-2.5 py-1.5 text-xs font-bold text-amber-700 hover:bg-amber-100 dark:text-amber-300 dark:hover:bg-amber-400/10"
                  >
                    Account
                  </Link>
                </div>

                {SETTINGS_ITEMS.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
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
                      <span>{item.label}</span>
                    </NavLink>
                  );
                })}

                <div className="my-2 border-t border-slate-100 dark:border-[#2E2924]" />
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
